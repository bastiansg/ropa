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
from ropa.meta.interfaces import CatalogCollector, CatalogItem
from ropa.meta.size_guides import SizeGuideLinkParser

type JsonObject = dict[str, Any]

BASE_URL = "https://aynotdead.com"
VENDOR = "Ay Not Dead"
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
CATEGORY_TAGS = {
    "abrigos",
    "accesorios",
    "anteojos",
    "billeteras",
    "buzos",
    "camisas",
    "campera",
    "camperas",
    "caps",
    "carteras",
    "carteras y bolsos",
    "cinturones",
    "cuero",
    "jeans",
    "mochilas y bolsos",
    "pantalones",
    "polleras",
    "remeras",
    "shorts",
    "socks",
    "sweaters",
    "tejidos",
    "tops",
    "underwear",
    "vestidos",
    "zapatos",
}
MAN_TAGS = {"hombre", "hombre_fw26", "hombres", "man", "men"}
WOMAN_TAGS = {"mujer", "mujer_fw26", "mujeres", "woman", "women"}
UNISEX_TAGS = {"unisex", "unisex_fw26"}

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
    url: str,
    accept: str,
    _timeout_seconds: int,
) -> str:
    return sha256(f"{url}\0{accept}".encode()).hexdigest()


@cached_stampede(
    cache=Cache.REDIS,
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    pool_max_size=16,
    namespace="ay_not_dead:http",
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


class AyNotDeadCollector(CatalogCollector):
    """Collect AY NOT DEAD products from its public Shopify storefront."""

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
        _render_status("AY NOT DEAD // CATALOG", "OPENING PRODUCT FEED...")
        limiter = AsyncLimiter(1, 1)

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
                products.values(),
            )

        _render_status("NORMALIZING CATALOG", "BUILDING CATALOG ITEMS...")
        items = [
            self._product_to_item(product, size_guide_urls[int(product["id"])])
            for product in products.values()
        ]
        _render_status("CATALOG COMPLETE", f"{len(items)} PRODUCTS READY")

        return items

    async def iter_products(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
    ) -> AsyncIterator[JsonObject]:
        """Yield every product until Shopify returns an empty page."""
        page = 1
        product_count = 0

        with Live(
            _catalog_progress(0, 0),
            console=console,
            refresh_per_second=10,
        ) as progress:
            while True:
                response_text = await _request_text_cached(
                    session,
                    limiter,
                    (
                        f"{BASE_URL}/products.json"
                        f"?limit={self.page_size}&page={page}"
                    ),
                    "application/json",
                    self.timeout_seconds,
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
        sitemap_urls = await self._product_urls_from_sitemap(
            session,
            limiter,
        )
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
            (str(product["handle"]), product) for product in missing_products
        )

    async def _product_urls_from_sitemap(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
    ) -> tuple[str, ...]:
        sitemap_index = ElementTree.fromstring(
            await _request_text_cached(
                session,
                limiter,
                f"{BASE_URL}/sitemap.xml",
                "application/xml",
                self.timeout_seconds,
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
                _request_text_cached(
                    session,
                    limiter,
                    sitemap_url,
                    "application/xml",
                    self.timeout_seconds,
                )
                for sitemap_url in product_sitemaps
            )
        )
        product_urls = (
            element.text
            for sitemap_document in sitemap_documents
            for element in ElementTree.fromstring(sitemap_document).iter()
            if element.tag.endswith("loc")
            if element.text
            if "/products/" in element.text
        )

        return tuple(dict.fromkeys(product_urls))

    async def _fallback_products(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        product_urls: Iterable[str],
    ) -> tuple[JsonObject, ...]:
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        return tuple(
            await asyncio.gather(
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
        )

    async def _fallback_product(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        product_url: str,
    ) -> JsonObject:
        async with semaphore:
            product = json.loads(
                await _request_text_cached(
                    session,
                    limiter,
                    f"{product_url}.js",
                    "application/json",
                    self.timeout_seconds,
                )
            )

        return self._normalize_fallback_product(product)

    @staticmethod
    def _normalize_fallback_product(product: JsonObject) -> JsonObject:
        return {
            **product,
            "body_html": product.get("description") or "",
            "images": tuple(
                {"src": urljoin(BASE_URL, image_url)}
                for image_url in product.get("images") or ()
            ),
            "variants": tuple(
                {
                    **variant,
                    "price": float(variant["price"]) / 100,
                }
                for variant in product.get("variants") or ()
            ),
        }

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
        product_url = f"{BASE_URL}/products/{product['handle']}"

        try:
            async with semaphore:
                html = await _request_text_cached(
                    session,
                    limiter,
                    product_url,
                    "text/html,application/xhtml+xml",
                    self.timeout_seconds,
                )
        except (
            _HTTPRequestError,
            _TransportError,
            _TransientHTTPStatusError,
        ) as error:
            _render_detail(
                "SIZE GUIDE ERROR",
                f"{product_url} // {error}",
            )

            return product_id, None

        parser = SizeGuideLinkParser(BASE_URL, product_url)
        parser.feed(html)

        return product_id, parser.url()

    def _product_to_item(
        self,
        product: JsonObject,
        size_guide_url: str | None,
    ) -> CatalogItem:
        variants = tuple(product.get("variants") or ())
        color_position = self._option_position(product, "color")
        size_position = self._option_position(product, "talle")
        available_variants = tuple(
            variant for variant in variants if variant.get("available")
        )
        priced_variants = available_variants or variants

        return CatalogItem(
            vendor=VENDOR,
            product_id=int(product["id"]),
            title=str(product.get("title") or ""),
            url=f"{BASE_URL}/products/{product['handle']}",
            description=self._description(product),
            image_urls=tuple(
                dict.fromkeys(
                    str(image["src"])
                    for image in product.get("images") or ()
                    if image.get("src")
                )
            ),
            colors=self._variant_options(variants, color_position),
            gender=self._gender(product),
            price=min(
                float(variant["price"])
                for variant in priced_variants
                if variant.get("price") is not None
            ),
            categories=self._categories(product),
            all_sizes=self._variant_options(variants, size_position),
            available_sizes=self._variant_options(
                (variant for variant in variants if variant.get("available")),
                size_position,
            ),
            size_guide_url=size_guide_url,
        )

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

    @classmethod
    def _gender(cls, product: JsonObject) -> str:
        tags = set(cls._tags(product))
        has_man = bool(tags & MAN_TAGS)
        has_woman = bool(tags & WOMAN_TAGS)

        if tags & UNISEX_TAGS or has_man and has_woman:
            return "unisex"

        if has_man:
            return "man"

        if has_woman:
            return "woman"

        return "unisex"

    @classmethod
    def _categories(cls, product: JsonObject) -> tuple[str, ...]:
        product_type = str(product.get("product_type") or "").casefold()

        return tuple(
            dict.fromkeys(
                category
                for category in (*cls._tags(product), product_type)
                if category in CATEGORY_TAGS
            )
        )

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
