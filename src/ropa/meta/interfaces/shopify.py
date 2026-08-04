import asyncio
import json
import logging
from collections.abc import Callable, Coroutine, Iterator
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html.parser import HTMLParser
from itertools import batched, chain, groupby
from threading import Thread
from typing import Any, cast
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request

import httpx
import stamina
from aiocache import Cache, cached_stampede
from pydantic import PositiveFloat
from rich.console import Console
from rich.text import Text
from tqdm import tqdm

from ropa.config import config
from ropa.meta.interfaces.catalog import (
    CatalogCollector,
    CatalogItem,
)
from ropa.meta.size_guides import SizeGuideLinkParser

JsonObject = dict[str, Any]
logger = logging.getLogger(__name__)
console = Console(stderr=True)


def _page_progress[T](
    items: tuple[T, ...],
    vendor: str,
    page: int,
    print_header: bool,
) -> Iterator[T]:
    if print_header:
        header = Text(vendor, style="bold white")
        header.append(" // PAGE ", style="dim magenta")
        header.append(str(page), style="bright_cyan")
        console.print(header)

    yield from tqdm(
        items,
        total=len(items),
        unit="item",
        ascii=True,
        colour="#666666",
        ncols=80,
    )


class _RateLimitError(httpx.HTTPStatusError):
    """Shopify rate-limit response eligible for retry."""


class _CacheEventLoop:
    """Run all asynchronous cache operations on one event loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coroutine: Coroutine[Any, Any, str]) -> str:
        """Run a cache coroutine from synchronous collector code."""
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result()


def _request_cache_key(
    _function: Callable[..., Any],
    request: Request,
    *_args: object,
    **_kwargs: object,
) -> str:
    headers = tuple(sorted(request.header_items()))
    fingerprint = sha256(
        repr(
            (
                request.get_method(),
                request.full_url,
                headers,
                request.data,
            )
        ).encode()
    ).hexdigest()

    return fingerprint


def _request_url(url: str) -> str:
    """Return an ASCII-safe URL without double-encoding existing escapes."""
    return quote(url, safe=":/?&=%+#")


_CACHE_EVENT_LOOP = _CacheEventLoop()


@cached_stampede(
    cache=Cache.REDIS,
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    pool_max_size=32,
    namespace="shopify:http",
    ttl=None,
    lease=120,
    key_builder=_request_cache_key,
)
@stamina.retry(
    on=_RateLimitError,
    attempts=5,
    timeout=None,
    wait_initial=5,
    wait_max=60,
)
async def _request_text_cached(
    request: Request,
    timeout_seconds: int,
    request_completed: Callable[[], None] | None = None,
) -> str:
    try:
        try:
            response = await asyncio.to_thread(
                httpx.request,
                request.get_method(),
                request.full_url,
                headers=dict(request.header_items()),
                content=request.data,
                timeout=timeout_seconds,
                follow_redirects=True,
            )
        except httpx.RequestError as error:
            logger.error(
                "Shopify request failed: url=%s error_type=%s error=%s",
                request.full_url,
                type(error).__name__,
                error,
            )
            raise

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if response.status_code != 429:
                logger.error(
                    "Shopify request failed: url=%s status=%s error=%s",
                    request.full_url,
                    response.status_code,
                    error,
                )
                raise

            logger.warning(
                "Shopify request rate limited: url=%s status=%s",
                request.full_url,
                response.status_code,
            )
            raise _RateLimitError(
                str(error),
                request=error.request,
                response=error.response,
            ) from error

        return response.text
    finally:
        if request_completed is not None:
            request_completed()


def _request_text(
    request: Request,
    timeout_seconds: int,
    request_completed: Callable[[], None] | None = None,
) -> str:
    return _CACHE_EVENT_LOOP.run(
        _request_text_cached(
            request,
            timeout_seconds,
            request_completed,
        )
    )


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)

    def text(self) -> str:
        return " ".join(self.parts)


class RequestTrackingCollector(CatalogCollector):
    """Catalog collector with Rich request progress reporting."""

    vendor: str

    def _init_request_tracking(self) -> None:
        self._last_progress_page: int | None = None

class ShopifyCollector(RequestTrackingCollector):
    """Collect public catalog data from Shopify storefront JSON endpoints."""

    color_option_names = {"color", "colour"}
    size_option_names = {"size", "talle", "tamaño", "tamano"}

    def __init__(
        self,
        base_url: str,
        vendor: str,
        page_size: int = 250,
        timeout_seconds: int = 30,
        max_concurrent_requests: int = 8,
    ) -> None:
        if not 1 <= page_size <= 250:
            raise ValueError("page_size must be between 1 and 250")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if max_concurrent_requests <= 0:
            raise ValueError("max_concurrent_requests must be greater than zero")

        self.base_url = base_url.rstrip("/")
        self.vendor = vendor
        self.page_size = page_size
        self.timeout_seconds = timeout_seconds
        self.max_concurrent_requests = max_concurrent_requests
        self._size_guide_urls: dict[int, str | None] = {}
        self._init_request_tracking()

    def collect_items(self) -> list[CatalogItem]:
        """Collect one catalog item per product."""
        return list(self.iter_items())

    def iter_items(self) -> Iterator[CatalogItem]:
        """Yield one catalog item per product."""
        self._last_progress_page = None
        yield from self._iter_items_concurrently()

    def _iter_items_concurrently(self) -> Iterator[CatalogItem]:
        """Yield items while enriching products in concurrent batches."""
        products: dict[int, JsonObject] = {}
        categories: dict[int, dict[str, None]] = {}

        for product, category in self._iter_product_categories():
            product_id = int(product["id"])
            products[product_id] = product
            categories.setdefault(product_id, {})[category] = None

        product_groups = (
            (product, tuple(categories[product_id]))
            for product_id, product in products.items()
        )

        with ThreadPoolExecutor(
            max_workers=self.max_concurrent_requests
        ) as executor:
            for product_batch in batched(
                product_groups,
                self.max_concurrent_requests,
            ):
                batch_products = (
                    product for product, _categories in product_batch
                )

                tuple(executor.map(self._load_size_guide_url, batch_products))

                yield from (
                    self.product_to_item(product, product_categories)
                    for product, product_categories in product_batch
                )

    def _iter_product_categories(self) -> Iterator[tuple[JsonObject, str]]:
        """Yield each product and category pair without duplicates."""
        seen_keys: set[tuple[int, str]] = set()
        categorized_product_ids: set[int] = set()

        for collection in self.iter_collections():
            if not collection.get("products_count", 1):
                continue

            category = str(
                collection.get("title") or collection.get("handle") or ""
            )
            collection_handle = str(collection["handle"])
            for product in self.iter_collection_products(collection_handle):
                key = (int(product["id"]), category)
                if key in seen_keys:
                    continue

                seen_keys.add(key)
                categorized_product_ids.add(int(product["id"]))
                yield product, category

        yield from (
            (product, "Uncategorized")
            for product in self.iter_products()
            if int(product["id"]) not in categorized_product_ids
        )

    def iter_products(self) -> Iterator[JsonObject]:
        """Yield all public storefront products."""
        yield from self._paginate_objects("/products.json", "products")

    def iter_collections(self) -> Iterator[JsonObject]:
        """Yield all public storefront collections."""
        yield from self._paginate_objects("/collections.json", "collections")

    def iter_collection_products(
        self, collection_handle: str
    ) -> Iterator[JsonObject]:
        """Yield public products for a collection handle."""
        path = f"/collections/{collection_handle}/products.json"
        yield from self._paginate_objects(path, "products")

    def product_to_item(
        self,
        product: JsonObject,
        categories: tuple[str, ...],
    ) -> CatalogItem:
        """Normalize one Shopify product into one catalog item."""
        color_position = self._option_position(product, self.color_option_names)
        size_position = self._option_position(product, self.size_option_names)
        variant_groups = self._group_variants_by_color(product, color_position)
        variants = tuple(
            variant
            for grouped_variants in variant_groups.values()
            for variant in grouped_variants
        )

        return CatalogItem(
            vendor=self.vendor,
            product_id=int(product["id"]),
            title=str(product.get("title") or ""),
            url=self.product_url(product),
            description=self.description(product),
            image_urls=self.image_urls(product),
            colors=tuple(
                color for color in variant_groups if color is not None
            ),
            gender=self.gender(product, categories),
            price=self._price(variants),
            categories=tuple(category.lower() for category in categories),
            all_sizes=self._all_sizes(variants, size_position),
            available_sizes=self._available_sizes(variants, size_position),
            size_guide_url=self.size_guide_url(product),
        )

    def gender(self, product: JsonObject, categories: tuple[str, ...]) -> str:
        """Return item gender when a collector can infer it."""
        return "unisex"

    def product_url(self, product: JsonObject) -> str:
        """Build the canonical storefront URL for a product."""
        return f"{self.base_url}/products/{product['handle']}"

    def description(self, product: JsonObject) -> str:
        """Return a normalized text description for a Shopify product."""
        parser = _HTMLTextExtractor()
        parser.feed(
            str(product.get("body_html") or product.get("description") or "")
        )

        return parser.text()

    def image_urls(self, product: JsonObject) -> tuple[str, ...]:
        """Return unique Shopify image URLs for a product."""
        featured_image = product.get("image")
        featured_images = (
            (featured_image,) if isinstance(featured_image, dict) else ()
        )

        return tuple(
            dict.fromkeys(
                str(url)
                for image in chain(featured_images, product.get("images") or ())
                if isinstance(image, dict)
                for url in (image.get("src"),)
                if url
            )
        )

    def size_guide_url(self, product: JsonObject) -> str | None:
        """Return the product size-guide URL when the storefront exposes one."""
        product_id = int(product["id"])
        if product_id not in self._size_guide_urls:
            self._load_size_guide_url(product)

        return self._size_guide_urls[product_id]

    def _load_size_guide_url(self, product: JsonObject) -> None:
        """Cache a product's optional size-guide URL."""
        product_id = int(product["id"])
        if product_id in self._size_guide_urls:
            return

        product_url = self.product_url(product)
        parser = SizeGuideLinkParser(self.base_url, product_url)

        try:
            parser.feed(self._get_text(product_url))
        except httpx.HTTPError:
            self._size_guide_urls[product_id] = None
            return

        self._size_guide_urls[product_id] = parser.url()

    def _paginate_objects(self, path: str, key: str) -> Iterator[JsonObject]:
        page = 1

        while True:
            response = self._get_json(
                path, {"limit": self.page_size, "page": page}
            )
            raw_objects = cast(Iterator[JsonObject], response.get(key) or ())
            objects = tuple(raw_objects)
            if not objects:
                return

            page_objects = objects
            if key == "products":
                print_header = page != self._last_progress_page
                self._last_progress_page = page
                page_objects = _page_progress(
                    objects,
                    self.vendor,
                    page,
                    print_header,
                )

            yield from page_objects
            page += 1

    def _get_json(self, path: str, params: dict[str, int | str]) -> JsonObject:
        query = urlencode(params)
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        request_url = f"{url}?{query}" if query else url
        request = Request(
            _request_url(request_url),
            headers={"Accept": "application/json"},
        )

        return cast(
            JsonObject,
            json.loads(
                _request_text(
                    request,
                    self.timeout_seconds,
                )
            ),
        )

    def _get_text(self, url: str) -> str:
        request = Request(
            _request_url(urljoin(self.base_url, url)),
            headers={"Accept": "text/html,application/xhtml+xml"},
        )

        return _request_text(
            request,
            self.timeout_seconds,
        )

    def _option_position(
        self, product: JsonObject, names: set[str]
    ) -> int | None:
        matches = (
            int(option["position"])
            for option in product.get("options", ())
            if str(option.get("name", "")).casefold() in names
        )

        return next(matches, None)

    def _group_variants_by_color(
        self,
        product: JsonObject,
        color_position: int | None,
    ) -> dict[str | None, tuple[JsonObject, ...]]:
        variants = sorted(
            product.get("variants", ()),
            key=lambda variant: (
                self._variant_option(variant, color_position) or ""
            ),
        )

        colors = {
            color: tuple(grouped_variants)
            for color, grouped_variants in groupby(
                variants,
                key=lambda variant: self._variant_option(
                    variant, color_position
                ),
            )
        }

        return colors or {None: tuple()}

    def _all_sizes(
        self, variants: tuple[JsonObject, ...], size_position: int | None
    ) -> tuple[str, ...]:
        sizes = dict.fromkeys(
            size
            for variant in variants
            for size in (self._variant_option(variant, size_position),)
            if size
        )

        return tuple(sizes)

    def _available_sizes(
        self, variants: tuple[JsonObject, ...], size_position: int | None
    ) -> tuple[str, ...]:
        sizes = dict.fromkeys(
            size
            for variant in variants
            if variant.get("available")
            for size in (self._variant_option(variant, size_position),)
            if size
        )

        return tuple(sizes)

    def _price(self, variants: tuple[JsonObject, ...]) -> PositiveFloat:
        prices = (
            float(str(price))
            for variant in chain(
                (variant for variant in variants if variant.get("available")),
                variants,
            )
            for price in (variant.get("price"),)
            if price
        )

        return cast(PositiveFloat, next(prices))

    def _variant_option(
        self, variant: JsonObject, position: int | None
    ) -> str | None:
        if position is None:
            return None

        value = variant.get(f"option{position}")
        if value is None:
            return None

        return str(value)
