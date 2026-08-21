import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from hashlib import sha256
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import stamina
from aiocache import Cache, cached_stampede
from aiolimiter import AsyncLimiter
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError
from rich.console import Console
from rich.live import Live
from rich.text import Text
from tqdm import tqdm

from ropa.config import config
from ropa.meta.interfaces.catalog import CatalogCollector, CatalogItem
from ropa.meta.size_guides import SizeGuideLinkParser

type JsonObject = dict[str, Any]

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

console = Console(stderr=True)


class _TransientHTTPStatusError(Exception):
    """HTTP response eligible for a bounded retry."""


class _HTTPRequestError(Exception):
    """Permanent HTTP response error."""


class _TransportError(Exception):
    """Transient curl transport error."""


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if cleaned := data.strip():
            self.parts.append(cleaned)

    def text(self) -> str:
        return " ".join(self.parts)


def _render_status(label: str, action: str) -> None:
    message = Text()
    message.append("\n┌─[ ", style="dim magenta")
    message.append(label, style="bold white")
    message.append(" ]\n", style="dim magenta")
    message.append("└──> ", style="dim magenta")
    message.append(action, style="dim bright_cyan")
    console.print(message)


def _render_detail(label: str, value: object) -> None:
    detail = Text()
    detail.append(" :: ", style="dim magenta")
    detail.append(label, style="bold white")
    detail.append(" // ", style="dim magenta")
    detail.append(str(value), style="dim white")
    console.print(detail)


def _catalog_progress(page: int, products: int) -> Text:
    return Text.assemble(
        (" :: CATALOG PAGE ", "dim magenta"),
        (f"{page:02}", "bold white"),
        (" // PRODUCTS ", "dim magenta"),
        (str(products), "dim white"),
    )


def _request_cache_key(
    _function: object,
    _session: AsyncSession,
    _limiter: AsyncLimiter,
    cache_namespace: str,
    url: str,
    accept: str,
    _timeout_seconds: int,
) -> str:
    fingerprint = sha256(f"{url}\0{accept}".encode()).hexdigest()

    return f"{cache_namespace}:{fingerprint}"


@cached_stampede(
    cache=Cache.REDIS,
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    pool_max_size=32,
    ttl=None,
    lease=120,
    key_builder=_request_cache_key,
)
@stamina.retry(
    on=(_TransportError, _TransientHTTPStatusError),
    attempts=3,
    timeout=None,
    wait_initial=5,
    wait_max=20,
)
async def _request_text_cached(
    session: AsyncSession,
    limiter: AsyncLimiter,
    cache_namespace: str,
    url: str,
    accept: str,
    timeout_seconds: int,
) -> str:
    async with limiter:
        return await _request_text_uncached(
            session,
            url,
            accept,
            timeout_seconds,
        )


async def _request_text_uncached(
    session: AsyncSession,
    url: str,
    accept: str,
    timeout_seconds: int,
) -> str:
    try:
        response = await session.get(
            url,
            headers={"Accept": accept},
            timeout=timeout_seconds,
        )
    except RequestsError as error:
        raise _TransportError(str(error)) from error

    status_code = response.status_code
    if status_code in TRANSIENT_STATUS_CODES:
        raise _TransientHTTPStatusError(f"GET {url} returned {status_code}")

    if status_code >= 400:
        raise _HTTPRequestError(f"GET {url} returned {status_code}")

    return response.text


class ShopifyCollector(CatalogCollector):
    """Collect and normalize a public Shopify storefront catalog."""

    base_url: str
    vendor: str
    cache_namespace: str

    def __init__(
        self,
        page_size: int = 250,
        timeout_seconds: int = 30,
        max_concurrent_requests: int = 3,
    ) -> None:
        if not 1 <= page_size <= 250:
            raise ValueError("page_size must be between 1 and 250")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if max_concurrent_requests <= 0:
            raise ValueError(
                "max_concurrent_requests must be greater than zero"
            )

        self.page_size = page_size
        self.timeout_seconds = timeout_seconds
        self.max_concurrent_requests = max_concurrent_requests

    def collect_items(self) -> list[CatalogItem]:
        """Collect, validate, enrich, and normalize every public product."""
        return asyncio.run(self._collect_items())

    async def _collect_items(self) -> list[CatalogItem]:
        _render_status(
            f"{self.vendor.upper()} // CATALOG",
            "OPENING PRODUCT FEED...",
        )
        limiter = AsyncLimiter(1, 1)

        try:
            async with AsyncSession(
                max_clients=self.max_concurrent_requests,
                impersonate="chrome",
            ) as session:
                products = {
                    str(product["handle"]): product
                    async for product in self.iter_products(session, limiter)
                }
                await self._add_sitemap_products(session, limiter, products)
                size_guide_urls = await self._size_guide_urls(
                    session,
                    limiter,
                    self.products_for_size_guides(products.values()),
                )
        finally:
            await _request_text_cached.cache.close()

        _render_status("NORMALIZING CATALOG", "BUILDING CATALOG ITEMS...")
        items = [
            self.product_to_item(
                product,
                size_guide_urls.get(int(product["id"])),
            )
            for product in products.values()
        ]
        _render_status("CATALOG COMPLETE", f"{len(items)} PRODUCTS READY")

        return items

    async def iter_products(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
    ) -> AsyncIterator[JsonObject]:
        """Yield products until Shopify returns an empty page."""
        page = 1
        product_count = 0

        with Live(
            _catalog_progress(0, 0),
            console=console,
            refresh_per_second=10,
        ) as progress:
            while True:
                response_text = await self._request_text(
                    session,
                    limiter,
                    (
                        f"{self.base_url}/products.json"
                        f"?limit={self.page_size}&page={page}"
                    ),
                    "application/json",
                )
                products = tuple(
                    json.loads(response_text).get("products") or ()
                )

                if not products:
                    return

                product_count += len(products)
                progress.update(_catalog_progress(page, product_count))

                for product in products:
                    yield product

                page += 1

    async def _add_sitemap_products(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        products: dict[str, JsonObject],
    ) -> None:
        _render_status("SITEMAP CHECK", "VERIFYING CATALOG COVERAGE...")
        sitemap_urls = await self._product_urls_from_sitemap(session, limiter)
        missing_urls = tuple(
            url for url in sitemap_urls if self._handle(url) not in products
        )
        _render_detail("SITEMAP PRODUCTS", len(sitemap_urls))
        _render_detail("FEED PRODUCTS", len(products))
        _render_detail("MISSING FROM FEED", len(missing_urls))

        if not missing_urls:
            return

        missing_products = await self._fallback_products(
            session,
            limiter,
            missing_urls,
        )

        products.update(
            (str(product["handle"]), product)
            for product in missing_products
        )

    async def _product_urls_from_sitemap(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
    ) -> tuple[str, ...]:
        sitemap_index = ElementTree.fromstring(
            await self._request_text(
                session,
                limiter,
                f"{self.base_url}/sitemap.xml",
                "application/xml",
            )
        )
        product_sitemaps = (
            element.text
            for element in sitemap_index.iter()
            if element.tag.endswith("loc")
            if element.text
            if "sitemap_products" in element.text
        )
        sitemap_documents = await asyncio.gather(
            *(
                self._request_text(
                    session,
                    limiter,
                    sitemap_url,
                    "application/xml",
                )
                for sitemap_url in product_sitemaps
            )
        )

        return tuple(
            dict.fromkeys(
                url
                for document in sitemap_documents
                for url in self._product_urls_from_sitemap_document(document)
            )
        )

    def _product_urls_from_sitemap_document(
        self,
        document: str,
    ) -> tuple[str, ...]:
        root = ElementTree.fromstring(document)
        urls = (
            next(
                (
                    child.text
                    for child in element
                    if child.tag.endswith("loc") and child.text
                ),
                None,
            )
            for element in root.iter()
            if element.tag.endswith("url")
        )

        return tuple(
            url for url in urls if url and self._is_product_url(url)
        )

    def _is_product_url(self, url: str) -> bool:
        parsed = urlparse(url)
        base_host = urlparse(self.base_url).netloc.casefold()
        path_parts = tuple(part for part in parsed.path.split("/") if part)

        return (
            parsed.scheme in {"http", "https"}
            and parsed.netloc.casefold() == base_host
            and len(path_parts) == 2
            and path_parts[0] == "products"
        )

    async def _fallback_products(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        product_urls: Iterable[str],
    ) -> tuple[JsonObject, ...]:
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        products = await asyncio.gather(
            *(
                self._fallback_product(
                    session,
                    limiter,
                    semaphore,
                    product_url,
                )
                for product_url in product_urls
            )
        )

        return tuple(product for product in products if product is not None)

    async def _fallback_product(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        product_url: str,
    ) -> JsonObject | None:
        try:
            async with semaphore:
                product = json.loads(
                    await self._request_text(
                        session,
                        limiter,
                        f"{product_url}.js",
                        "application/json",
                    )
                )
        except (
            json.JSONDecodeError,
            _HTTPRequestError,
            _TransportError,
            _TransientHTTPStatusError,
        ) as error:
            _render_detail(
                "SITEMAP PRODUCT ERROR",
                f"{product_url} // {error}",
            )

            return None

        return self._normalize_fallback_product(product)

    def _normalize_fallback_product(
        self,
        product: JsonObject,
    ) -> JsonObject:
        options = tuple(product.get("options") or ())

        return {
            **product,
            "body_html": product.get("description") or "",
            "product_type": (
                product.get("product_type") or product.get("type") or ""
            ),
            "images": tuple(
                {"src": urljoin(self.base_url, image_url)}
                for image_url in product.get("images") or ()
            ),
            "options": tuple(
                {
                    "name": (
                        option.get("name")
                        if isinstance(option, dict)
                        else option
                    ),
                    "position": index,
                }
                for index, option in enumerate(options, 1)
            ),
            "variants": tuple(
                {
                    **variant,
                    "price": float(variant["price"]) / 100,
                }
                for variant in product.get("variants") or ()
            ),
        }

    def products_for_size_guides(
        self,
        products: Iterable[JsonObject],
    ) -> Iterable[JsonObject]:
        """Return products whose storefront pages should be inspected."""
        return products

    async def _size_guide_urls(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        products: Iterable[JsonObject],
    ) -> dict[int, str | None]:
        products = tuple(products)
        _render_status(
            "SIZE GUIDES",
            f"INSPECTING {len(products)} PRODUCT PAGES...",
        )
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        urls: dict[int, str | None] = {}
        tasks = tuple(
            asyncio.create_task(
                self._size_guide_url(session, limiter, semaphore, product)
            )
            for product in products
        )

        with tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=" :: SIZE GUIDES",
            unit="page",
            ascii=True,
            colour="#666666",
            ncols=80,
        ) as progress:
            for task in progress:
                product_id, url = await task
                urls[product_id] = url

        _render_detail(
            "SIZE GUIDES FOUND",
            sum(url is not None for url in urls.values()),
        )
        _render_detail(
            "SIZE GUIDES MISSING",
            sum(url is None for url in urls.values()),
        )

        return urls

    async def _size_guide_url(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        product: JsonObject,
    ) -> tuple[int, str | None]:
        product_id = int(product["id"])
        product_url = self.product_url(product)

        try:
            async with semaphore:
                html = await self._request_text(
                    session,
                    limiter,
                    product_url,
                    "text/html,application/xhtml+xml",
                )
        except (
            _HTTPRequestError,
            _TransportError,
            _TransientHTTPStatusError,
        ) as error:
            _render_detail("SIZE GUIDE ERROR", f"{product_url} // {error}")

            return product_id, None

        try:
            parser = SizeGuideLinkParser(self.base_url, product_url)
            parser.feed(html)
            size_guide_url = await self._resolve_size_guide_url(
                session,
                limiter,
                semaphore,
                parser.url(),
            )
        except (
            _HTTPRequestError,
            _TransportError,
            _TransientHTTPStatusError,
        ) as error:
            _render_detail("SIZE GUIDE ERROR", f"{product_url} // {error}")

            return product_id, None

        return product_id, size_guide_url

    async def _resolve_size_guide_url(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        size_guide_url: str | None,
    ) -> str | None:
        return size_guide_url

    async def _request_text(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        url: str,
        accept: str,
    ) -> str:
        return await _request_text_cached(
            session,
            limiter,
            self.cache_namespace,
            url,
            accept,
            self.timeout_seconds,
        )

    def product_to_item(
        self,
        product: JsonObject,
        size_guide_url: str | None,
    ) -> CatalogItem:
        """Normalize one Shopify product into a catalog item."""
        variants = tuple(product.get("variants") or ())
        color_position = self._option_position(product, "color")
        size_position = self._option_position(product, "talle")
        available_variants = tuple(
            variant for variant in variants if variant.get("available")
        )
        priced_variants = available_variants or variants

        return CatalogItem(
            vendor=self.vendor,
            product_id=int(product["id"]),
            title=str(product.get("title") or ""),
            url=self.product_url(product),
            description=self._description(product),
            image_urls=tuple(
                dict.fromkeys(
                    str(image["src"])
                    for image in product.get("images") or ()
                    if image.get("src")
                )
            ),
            colors=self._variant_options(variants, color_position),
            gender=self.gender(product),
            price=min(
                float(variant["price"])
                for variant in priced_variants
                if variant.get("price") is not None
            ),
            categories=self.categories(product),
            all_sizes=self._variant_options(variants, size_position),
            available_sizes=self._variant_options(
                (variant for variant in variants if variant.get("available")),
                size_position,
            ),
            size_guide_url=size_guide_url,
        )

    def product_url(self, product: JsonObject) -> str:
        """Return the canonical product URL."""
        return f"{self.base_url}/products/{product['handle']}"

    def gender(self, product: JsonObject) -> str:
        """Return the provider-specific product gender."""
        return "unisex"

    def categories(self, product: JsonObject) -> tuple[str, ...]:
        """Return the provider-specific product categories."""
        product_type = str(product.get("product_type") or "").casefold()

        return (product_type,) if product_type else ()

    @staticmethod
    def _description(product: JsonObject) -> str:
        parser = _HTMLTextExtractor()
        parser.feed(str(product.get("body_html") or ""))

        return parser.text()

    @staticmethod
    def _tags(product: JsonObject) -> tuple[str, ...]:
        tags = product.get("tags") or ()
        raw_tags = tags.split(",") if isinstance(tags, str) else tags

        return tuple(str(tag).strip().casefold() for tag in raw_tags)

    @staticmethod
    def _handle(product_url: str) -> str:
        return urlparse(product_url).path.rstrip("/").rsplit("/", 1)[-1]

    @staticmethod
    def _option_position(product: JsonObject, name: str) -> int | None:
        positions = (
            int(option["position"])
            for option in product.get("options") or ()
            if str(option.get("name") or "").casefold() == name
        )

        return next(positions, None)

    @staticmethod
    def _variant_options(
        variants: Iterable[JsonObject],
        position: int | None,
    ) -> tuple[str, ...]:
        if position is None:
            return ()

        return tuple(
            dict.fromkeys(
                str(value)
                for variant in variants
                for value in (variant.get(f"option{position}"),)
                if value
            )
        )
