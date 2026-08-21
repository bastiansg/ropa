import asyncio
import json
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urldefrag, urljoin, urlparse

from aiolimiter import AsyncLimiter
from curl_cffi.requests import AsyncSession

from ropa.meta.interfaces import JsonObject, ShopifyCollector

IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}

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


class SizeGuidePageParser(HTMLParser):
    """Extract the first image URL from an AY NOT DEAD size-guide page."""

    def __init__(self, page_url: str) -> None:
        super().__init__()
        self.page_url = page_url
        self.image_url: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "img" or self.image_url is not None:
            return

        tag_attrs = {name: value or "" for name, value in attrs}
        src = tag_attrs.get("src", "")
        self.image_url = urljoin(self.page_url, src) if src else None

    def url(self) -> str | None:
        return self.image_url


class AyNotDeadCollector(ShopifyCollector):
    """Collect AY NOT DEAD products from its public Shopify storefront."""

    base_url = "https://aynotdead.com"
    vendor = "Ay Not Dead"
    cache_namespace = "ay_not_dead:http"

    async def _resolve_size_guide_url(
        self,
        session: AsyncSession,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        size_guide_url: str | None,
    ) -> str | None:
        if size_guide_url is None or self._is_image_url(size_guide_url):
            return size_guide_url

        page_url = urldefrag(size_guide_url).url

        async with semaphore:
            page_json = await self._request_text(
                session,
                limiter,
                f"{page_url}.json",
                "application/json",
            )

        parser = SizeGuidePageParser(page_url)
        parser.feed(str(json.loads(page_json)["page"]["body_html"]))

        return parser.url()

    @staticmethod
    def _is_image_url(url: str) -> bool:
        return PurePosixPath(urlparse(url).path).suffix.casefold() in IMAGE_SUFFIXES

    def gender(self, product: JsonObject) -> str:
        tags = set(self._tags(product))
        has_man = bool(tags & MAN_TAGS)
        has_woman = bool(tags & WOMAN_TAGS)

        if tags & UNISEX_TAGS or has_man and has_woman:
            return "unisex"

        if has_man:
            return "man"

        if has_woman:
            return "woman"

        return "unisex"

    def categories(self, product: JsonObject) -> tuple[str, ...]:
        product_type = str(product.get("product_type") or "").casefold()

        return tuple(
            dict.fromkeys(
                category
                for category in (*self._tags(product), product_type)
                if category in CATEGORY_TAGS
            )
        )
