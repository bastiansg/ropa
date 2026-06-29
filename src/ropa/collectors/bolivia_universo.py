import json

from decimal import Decimal
from re import findall
from typing import Any, cast
from unicodedata import normalize

from html import unescape
from http.cookiejar import CookieJar
from html.parser import HTMLParser
from collections.abc import Iterable, Iterator
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

from urllib.request import (
    HTTPCookieProcessor,
    Request,
    build_opener,
)

from pydantic import BaseModel, ConfigDict
from ropa.meta.interfaces import CatalogCollector, CatalogItem


JsonObject = dict[str, Any]
BOLIVIA_UNIVERSO_GENDERS = {
    "man": {
        "hombre",
        "hombres",
    },
    "woman": {
        "mujer",
        "mujeres",
        "dama",
        "damas",
    },
}


class _ListingLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str


class _ProductCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: int
    title: str
    url: str
    image_urls: tuple[str, ...]


class _ProductDetails(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    description: str
    image_urls: tuple[str, ...]
    color: str | None
    price: Decimal | None


def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name: value or "" for name, value in attrs}


def _has_class(attrs: dict[str, str], class_name: str) -> bool:
    return class_name in attrs.get("class", "").split()


def _clean_text(value: str) -> str:
    return " ".join(unescape(value).split())


class _ListingLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[_ListingLink] = []
        self._current_href: str | None = None
        self._current_title: str = ""
        self._current_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "a":
            return

        tag_attrs = _attrs(attrs)
        href = self._catalog_href(tag_attrs.get("href", ""))
        if href is None:
            return

        self._current_href = href
        self._current_title = tag_attrs.get("title", "")
        self._current_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return

        title = _clean_text(self._current_title or "".join(self._current_parts))
        self.links.append(_ListingLink(url=self._current_href, title=title))
        self._current_href = None
        self._current_title = ""
        self._current_parts = []

    def _catalog_href(self, href: str) -> str | None:
        url = urljoin(self.base_url, href)
        parts = urlsplit(url)
        path = parts.path.strip("/")
        is_catalog_path = path == "lo-nuevo" or path.startswith("categorias/")
        if not is_catalog_path:
            return None

        query = urlencode(
            tuple(
                (key, value)
                for key, value in parse_qsl(parts.query)
                if not key.startswith("utm_")
            )
        )

        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


class _ProductCardParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.cards: list[_ProductCard] = []
        self._card_depth: int | None = None
        self._product_id: int | None = None
        self._title: str = ""
        self._url: str = ""
        self._image_urls: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag_attrs = _attrs(attrs)
        if tag == "div" and self._card_depth is None:
            if _has_class(tag_attrs, "producto"):
                self._card_depth = 1
                self._product_id = None
                self._title = ""
                self._url = ""
                self._image_urls = []

            return

        if self._card_depth is None:
            return

        if tag == "div":
            self._card_depth += 1
            element_id = tag_attrs.get("id", "")
            if element_id.startswith("swiper-") and self._product_id is None:
                raw_product_id = element_id.removeprefix("swiper-")
                if raw_product_id.isdecimal():
                    self._product_id = int(raw_product_id)

        if tag == "a":
            self._capture_product_link(tag_attrs)

        if tag == "img":
            self._capture_image_url(tag_attrs.get("src", ""))

        if tag == "source":
            self._capture_image_url(tag_attrs.get("srcset", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag != "div" or self._card_depth is None:
            return

        self._card_depth -= 1
        if self._card_depth:
            return

        if self._product_id is not None and self._url:
            self.cards.append(
                _ProductCard(
                    product_id=self._product_id,
                    title=self._title,
                    url=self._url,
                    image_urls=tuple(dict.fromkeys(self._image_urls)),
                )
            )

        self._card_depth = None

    def _capture_product_link(self, attrs: dict[str, str]) -> None:
        href = attrs.get("href", "")
        if "/productos/" not in href:
            return

        self._url = self._url or urljoin(self.base_url, href)
        self._title = self._title or _clean_text(attrs.get("title", ""))

    def _capture_image_url(self, value: str) -> None:
        raw_url = value.split()[0] if value else ""
        if not raw_url:
            return

        self._image_urls.append(urljoin(self.base_url, raw_url))


class _ProductDetailParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.product_data: JsonObject = {}
        self.color: str | None = None
        self._script_depth: int | None = None
        self._script_parts: list[str] = []
        self._colors_depth: int | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag_attrs = _attrs(attrs)
        if tag == "script" and tag_attrs.get("type") == "application/ld+json":
            self._script_depth = 1
            self._script_parts = []
            return

        if self._script_depth is not None:
            self._script_depth += 1
            return

        if tag == "div" and _has_class(tag_attrs, "fitit-colors"):
            self._colors_depth = 1
            return

        if self._colors_depth is not None:
            if tag == "div":
                self._colors_depth += 1

        if self._colors_depth is not None and tag == "a":
            classes = tag_attrs.get("class", "").split()
            if "active" in classes:
                self.color = _clean_text(tag_attrs.get("title", "")) or None

    def handle_data(self, data: str) -> None:
        if self._script_depth is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._script_depth is not None:
            self._script_depth -= 1
            if self._script_depth:
                return

            self._load_product_data()
            self._script_depth = None
            return

        if tag != "div" or self._colors_depth is None:
            return

        self._colors_depth -= 1
        if not self._colors_depth:
            self._colors_depth = None

    def details(self) -> _ProductDetails:
        images = self.product_data.get("image") or ()
        raw_images = (images,) if isinstance(images, str) else images

        return _ProductDetails(
            title=str(self.product_data.get("name") or ""),
            description=str(self.product_data.get("description") or ""),
            image_urls=tuple(
                dict.fromkeys(
                    urljoin(self.base_url, str(image))
                    for image in raw_images
                    if image
                )
            ),
            color=self.color,
            price=self._price(),
        )

    def _load_product_data(self) -> None:
        raw_json = "".join(self._script_parts).strip()
        if not raw_json:
            return

        data = json.loads(raw_json)
        if isinstance(data, dict) and data.get("@type") == "Product":
            self.product_data = data

    def _price(self) -> Decimal | None:
        offers = self.product_data.get("offers") or ()
        raw_offers = (offers,)
        if not isinstance(offers, dict):
            raw_offers = offers

        prices = (
            offer.get("price")
            for offer in raw_offers
            if isinstance(offer, dict) and offer.get("price")
        )

        return next((Decimal(str(price)) for price in prices), None)


class _SizeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sizes: list[str] = []
        self._label_depth: int | None = None
        self._label_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag_attrs = _attrs(attrs)
        if tag != "label" or self._label_depth is not None:
            return

        if "disabled" in tag_attrs.get("class", "").split():
            return

        self._label_depth = 1
        self._label_parts = []

    def handle_data(self, data: str) -> None:
        if self._label_depth is not None:
            self._label_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._label_depth is None:
            return

        if tag != "label":
            return

        value = _clean_text("".join(self._label_parts))
        if value:
            self.sizes.append(value)

        self._label_depth = None
        self._label_parts = []


class BoliviaUniversoCollector(CatalogCollector):
    """Collect public catalog data from Bolivia Universo storefront pages."""

    def __init__(
        self,
        base_url: str = "https://boliviauniverso.com",
        vendor: str = "Bolivia Universo",
        listing_urls: Iterable[str] | None = None,
        timeout_seconds: int = 30,
        max_pages_per_listing: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.vendor = vendor
        self.listing_urls = (
            tuple(listing_urls) if listing_urls is not None else None
        )
        self.timeout_seconds = timeout_seconds
        self.max_pages_per_listing = max_pages_per_listing
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._details: dict[str, _ProductDetails] = {}
        self._sizes: dict[int, tuple[str, ...]] = {}

    def collect_items(self) -> list[CatalogItem]:
        """Collect all public catalog items."""
        return list(self.iter_items())

    def iter_items(self) -> Iterator[CatalogItem]:
        """Yield catalog items from discovered Bolivia Universo listings."""
        seen_keys: set[tuple[int, str | None, str]] = set()

        for link in self.iter_listing_links():
            for card in self.iter_listing_cards(link.url):
                details = self.product_details(card.url)
                category = self.category_name(link)
                color = details.color
                key = (card.product_id, color, category)
                if key in seen_keys:
                    continue

                seen_keys.add(key)
                yield CatalogItem(
                    vendor=self.vendor,
                    product_id=card.product_id,
                    title=details.title or card.title,
                    url=card.url,
                    description=details.description,
                    image_urls=details.image_urls or card.image_urls,
                    color=color,
                    gender=self.gender(
                        category,
                        details.title,
                        card.title,
                        card.url,
                        details.description,
                    ),
                    price=details.price,
                    category=category,
                    available_sizes=self.available_sizes(card.product_id),
                )

    def gender(self, *values: object) -> str:
        """Infer item gender from Bolivia Universo listing and product text."""
        tokens = self._gender_tokens(values)

        return next(
            (
                gender
                for gender, gender_tokens in BOLIVIA_UNIVERSO_GENDERS.items()
                if tokens & gender_tokens
            ),
            "unisex",
        )

    def iter_listing_links(self) -> Iterator[_ListingLink]:
        """Yield configured or discovered listing links."""
        links = (
            (
                _ListingLink(url=urljoin(self.base_url, url), title="")
                for url in self.listing_urls
            )
            if self.listing_urls is not None
            else self.discover_listing_links()
        )

        yield from self._dedupe_links(links)

    def discover_listing_links(self) -> Iterator[_ListingLink]:
        """Discover catalog links from the storefront navigation."""
        parser = _ListingLinkParser(self.base_url)
        parser.feed(self._get_text(self.base_url))

        yield from parser.links

    def iter_listing_cards(self, url: str) -> Iterator[_ProductCard]:
        """Yield product cards from one listing and its AJAX pages."""
        initial_html = self._get_text(url)
        yield from self._product_cards(initial_html)

        page_count = 0
        while self.max_pages_per_listing is None or (
            page_count < self.max_pages_per_listing
        ):
            page_count += 1
            data = self._post_json("/ajax/grilla/paginacionAjax.php", {})
            cards = tuple(self._product_cards(str(data.get("0") or "")))
            if not cards:
                return

            yield from cards
            if not data.get("1"):
                return

    def product_details(self, url: str) -> _ProductDetails:
        """Return cached product details parsed from the product page."""
        if url not in self._details:
            parser = _ProductDetailParser(self.base_url)
            parser.feed(self._get_text(url))
            self._details[url] = parser.details()

        return self._details[url]

    def available_sizes(self, product_id: int) -> tuple[str, ...]:
        """Return cached available sizes from the product variant endpoint."""
        if product_id not in self._sizes:
            data = self._post_json(
                "/ajax/producto/varianteAjax.php",
                {
                    "idProducto": product_id,
                    "idCaracteristicaValor1": 0,
                    "idCaracteristicaValor2": 0,
                },
            )
            parser = _SizeParser()
            parser.feed(str(data.get("1") or ""))
            self._sizes[product_id] = tuple(dict.fromkeys(parser.sizes))

        return self._sizes[product_id]

    def category_name(self, link: _ListingLink) -> str:
        """Build a stable category name from a listing link."""
        path = urlsplit(link.url).path.strip("/")
        if path == "lo-nuevo":
            return link.title or "Lo Nuevo"

        if path.startswith("categorias/"):
            category = path.removeprefix("categorias/")
            return " / ".join(
                _clean_text(unquote(part)) for part in category.split("/")
            )

        return link.title or path or "Uncategorized"

    def _gender_tokens(self, values: tuple[object, ...]) -> set[str]:
        text = " ".join(str(value or "") for value in values)
        ascii_text = normalize("NFKD", text).encode("ascii", "ignore").decode()

        return set(findall(r"[a-zA-Z]+", ascii_text.casefold()))

    def _product_cards(self, html: str) -> Iterator[_ProductCard]:
        parser = _ProductCardParser(self.base_url)
        parser.feed(html)

        yield from parser.cards

    def _get_text(self, url: str) -> str:
        request = Request(urljoin(self.base_url, url), headers=self._headers())
        with self.opener.open(
            request, timeout=self.timeout_seconds
        ) as response:
            return response.read().decode("utf-8", errors="replace")

    def _post_json(self, path: str, data: dict[str, int | str]) -> JsonObject:
        body = urlencode(data).encode()
        request = Request(
            urljoin(f"{self.base_url}/", path.lstrip("/")),
            data=body,
            headers={
                **self._headers(),
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        with self.opener.open(
            request, timeout=self.timeout_seconds
        ) as response:
            return cast(JsonObject, json.load(response))

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "ropa-catalog-collector/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json",
        }

    def _dedupe_links(
        self, links: Iterable[_ListingLink]
    ) -> Iterator[_ListingLink]:
        seen: set[str] = set()

        for link in links:
            if link.url in seen:
                continue

            seen.add(link.url)
            yield link
