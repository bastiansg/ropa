import asyncio
import json
import re
from collections.abc import AsyncIterator, Iterable
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from unicodedata import normalize
from urllib.parse import urljoin, urlparse, urlunparse

import stamina
from aiocache import Cache, cached_stampede
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError
from rich.console import Console
from rich.live import Live
from rich.text import Text
from tqdm import tqdm

from ropa.config import config
from ropa.meta.interfaces import CatalogCollector, CatalogItem

BASE_URL = "https://boliviauniverso.com"
CATALOG_URL = f"{BASE_URL}/inicio/"
PAGINATION_URL = f"{BASE_URL}/ajax/grilla/paginacionAjax.php"
VENDOR = "Bolivia - Divina"
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
CATEGORY_NAMES = {
    "abrigo": "abrigos",
    "bermuda": "bermudas",
    "blazer": "abrigos",
    "boxer": "underwear",
    "buzo": "buzos",
    "camisa": "camisas",
    "campera": "camperas",
    "chomba": "chombas",
    "cinturon": "cinturones",
    "falda": "faldas y shorts",
    "gorro": "accesorios",
    "jean": "denim",
    "media": "medias",
    "musculosa": "remeras",
    "pantalon": "pantalones",
    "remera": "remeras",
    "remeron": "remeras",
    "short": "faldas y shorts",
    "sweater": "sweaters",
    "top": "tops",
    "vestido": "monoprendas y vestidos",
}
PRODUCT_URL_PATTERN = re.compile(
    r"(?:https://boliviauniverso\.com/)?productos/([^/?#\"']+)/?"
)
TAG_PATTERN = re.compile(r"<[^>]+>")
MONEY_PATTERN = re.compile(r"\$\s*([\d.]+(?:,\d+)?)")
ITEM_CATEGORY_PATTERN = re.compile(
    r"['\"]item_category['\"]\s*:\s*['\"]([^'\"]+)"
)

console = Console(stderr=True)


class _TransientHTTPStatusError(Exception):
    pass


class _HTTPRequestError(Exception):
    pass


class _TransportError(Exception):
    pass


class _CatalogHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.product_urls: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "a":
            return

        attributes = dict(attrs)
        href = attributes.get("href") or ""
        if match := PRODUCT_URL_PATTERN.search(href):
            self.product_urls.append(
                f"{BASE_URL}/productos/{match.group(1)}/"
            )


class _ProductHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.description_parts: list[str] = []
        self.sku_parts: list[str] = []
        self.size_parts: list[str] = []
        self.colors: list[str] = []
        self.product_id: int | None = None
        self.image_urls: list[str] = []
        self._capture: str | None = None
        self._sizes_depth = 0
        self._label_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        fitit = attributes.get("data-fitit")

        if fitit in {"title", "description", "sku"}:
            self._capture = fitit

        if fitit == "sizes":
            self._sizes_depth = 1

        if self._sizes_depth and tag == "label":
            self._label_depth = 1

        if self._sizes_depth and tag == "div" and fitit != "sizes":
            self._sizes_depth += 1

        if (
            tag == "a"
            and "active" in classes
            and "btn-otros" in classes
            and (color := attributes.get("title"))
        ):
            self.colors.append(color)

        if (
            tag == "input"
            and attributes.get("id") == "idProducto"
            and (value := attributes.get("value"))
        ):
            self.product_id = int(value)

        if tag in {"img", "source"}:
            image_url = attributes.get("src") or attributes.get("srcset")
            if image_url and "/files/productos/" in image_url:
                self.image_urls.append(image_url)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "p", "span"}:
            self._capture = None

        if self._label_depth and tag == "label":
            self._label_depth = 0

        if self._sizes_depth and tag == "div":
            self._sizes_depth -= 1

    def handle_data(self, data: str) -> None:
        if not (cleaned := " ".join(data.split())):
            return

        if self._capture == "title":
            self.title_parts.append(cleaned)

        if self._capture == "description":
            self.description_parts.append(cleaned)

        if self._capture == "sku":
            self.sku_parts.append(cleaned)

        if self._label_depth:
            self.size_parts.append(cleaned)


class _SizeGuideHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.size_guide: dict[str, dict[str, str]] = {}
        self._modal_depth = 0
        self._in_table = False
        self._cell_tag: str | None = None
        self._cell_parts: list[str] = []
        self._row: list[str] = []
        self._headers: list[str] = []
        self._rows: list[list[str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "div" and attributes.get("id") == "medidas":
            self._modal_depth = 1
            return

        if not self._modal_depth:
            return

        if tag == "div":
            self._modal_depth += 1

        if tag == "table":
            self._in_table = True
            self._headers = []
            self._rows = []

        if self._in_table and tag == "tr":
            self._row = []

        if self._in_table and tag in {"th", "td"}:
            self._cell_tag = tag
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if not self._modal_depth:
            return

        if tag == self._cell_tag:
            self._row.append(" ".join(self._cell_parts))
            self._cell_tag = None

        if self._in_table and tag == "tr" and self._row:
            if self._headers:
                self._rows.append(self._row)
            else:
                self._headers = self._row

        if self._in_table and tag == "table":
            self._add_table()
            self._in_table = False

        if tag == "div":
            self._modal_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell_tag and (cleaned := " ".join(data.split())):
            self._cell_parts.append(cleaned)

    def _add_table(self) -> None:
        for index, size in enumerate(self._headers[1:], 1):
            measurements = {
                self._normalize_name(row[0]): row[index]
                for row in self._rows
                if len(row) > index
            }
            self.size_guide.setdefault(size, {}).update(measurements)

    @staticmethod
    def _normalize_name(name: str) -> str:
        ascii_name = normalize("NFKD", name).encode("ascii", "ignore").decode()

        return re.sub(r"[^a-z0-9]+", "_", ascii_name.casefold()).strip("_")


def _render_status(label: str, action: str) -> None:
    message = Text()
    message.append("\n┌─[ ", style="dim magenta")
    message.append(label, style="bold white")
    message.append(" ]\n", style="dim magenta")
    message.append("└──> ", style="dim magenta")
    message.append(action, style="dim bright_cyan")
    console.print(message)


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
    url: str,
    _timeout_seconds: int,
) -> str:
    return sha256(url.encode()).hexdigest()


@cached_stampede(
    cache=Cache.REDIS,
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    pool_max_size=16,
    namespace="bolivia_universo:http",
    ttl=None,
    lease=120,
    key_builder=_request_cache_key,
)
async def _request_product_cached(
    session: AsyncSession,
    url: str,
    timeout_seconds: int,
) -> str:
    return await _request_text(session, url, timeout_seconds)


@stamina.retry(
    on=(_TransportError, _TransientHTTPStatusError),
    attempts=3,
    timeout=None,
    wait_initial=5,
    wait_max=20,
)
async def _request_text(
    session: AsyncSession,
    url: str,
    timeout_seconds: int,
) -> str:
    try:
        response = await session.get(
            url,
            headers={"Accept": "text/html,application/xhtml+xml"},
            timeout=timeout_seconds,
        )
    except RequestsError as error:
        raise _TransportError(str(error)) from error

    _validate_response(url, response.status_code)

    return response.text


async def _request_next_page(
    session: AsyncSession,
    timeout_seconds: int,
) -> str:
    try:
        response = await session.post(
            PAGINATION_URL,
            headers={
                "Accept": "application/json",
                "Referer": CATALOG_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=timeout_seconds,
        )
    except RequestsError as error:
        raise _TransportError(str(error)) from error

    _validate_response(PAGINATION_URL, response.status_code)

    return response.text


def _validate_response(url: str, status_code: int) -> None:
    if status_code in TRANSIENT_STATUS_CODES:
        raise _TransientHTTPStatusError(f"GET {url} returned {status_code}")

    if status_code >= 400:
        raise _HTTPRequestError(f"GET {url} returned {status_code}")


class BoliviaUniversoCollector(CatalogCollector):

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_concurrent_requests: int = 10,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if max_concurrent_requests <= 0:
            raise ValueError(
                "max_concurrent_requests must be greater than zero"
            )

        self.timeout_seconds = timeout_seconds
        self.max_concurrent_requests = max_concurrent_requests

    def collect_items(self) -> list[CatalogItem]:
        return asyncio.run(self._collect_items())

    async def _collect_items(self) -> list[CatalogItem]:
        _render_status(
            "BOLIVIA UNIVERSO // CATALOG",
            "OPENING STOREFRONT...",
        )

        async with AsyncSession(
            max_clients=self.max_concurrent_requests,
            impersonate="chrome",
        ) as session:
            product_urls = tuple(
                dict.fromkeys(
                    [url async for url in self.iter_product_urls(session)]
                )
            )
            items = await self._product_items(session, product_urls)

        _render_status("CATALOG COMPLETE", f"{len(items)} PRODUCTS READY")

        return list(items)

    async def iter_product_urls(
        self,
        session: AsyncSession,
    ) -> AsyncIterator[str]:
        catalog_html = await _request_text(
            session,
            CATALOG_URL,
            self.timeout_seconds,
        )
        has_more = True
        page = 1
        product_count = 0

        with Live(
            _catalog_progress(0, 0),
            console=console,
            refresh_per_second=10,
        ) as progress:
            while True:
                parser = _CatalogHTMLParser()
                parser.feed(catalog_html)
                urls = tuple(dict.fromkeys(parser.product_urls))
                product_count += len(urls)
                progress.update(_catalog_progress(page, product_count))

                for url in urls:
                    yield url

                if not has_more:
                    return

                response = json.loads(
                    await _request_next_page(session, self.timeout_seconds)
                )
                catalog_html = str(response["0"])
                has_more = bool(response["1"])
                page += 1

    async def _product_items(
        self,
        session: AsyncSession,
        product_urls: Iterable[str],
    ) -> tuple[CatalogItem, ...]:
        product_urls = tuple(product_urls)
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        tasks = tuple(
            asyncio.create_task(self._product_item(session, semaphore, url))
            for url in product_urls
        )
        items: list[CatalogItem] = []

        with tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=" :: PRODUCT DETAILS",
            unit="page",
            ascii=True,
            colour="#666666",
            ncols=80,
        ) as progress:
            items.extend([await task for task in progress])

        return tuple(items)

    async def _product_item(
        self,
        session: AsyncSession,
        semaphore: asyncio.Semaphore,
        product_url: str,
    ) -> CatalogItem:
        async with semaphore:
            html = await _request_product_cached(
                session,
                product_url,
                self.timeout_seconds,
            )

        return self._html_to_item(product_url, html)

    @classmethod
    def _html_to_item(cls, product_url: str, html: str) -> CatalogItem:
        parser = _ProductHTMLParser()
        parser.feed(html)
        canonical_url = cls._canonical_url(product_url)
        size_guide_parser = _SizeGuideHTMLParser()
        size_guide_parser.feed(html)
        sku = " ".join(parser.sku_parts)
        title = " ".join(parser.title_parts)

        if parser.product_id is None:
            raise ValueError(f"Missing product id in {product_url}")

        return CatalogItem(
            vendor=VENDOR,
            product_id=parser.product_id,
            title=title,
            url=canonical_url,
            description=" ".join(dict.fromkeys(parser.description_parts)),
            image_urls=cls._product_images(
                parser.image_urls,
                parser.product_id,
            ),
            colors=tuple(dict.fromkeys(parser.colors)),
            gender=cls._gender(sku),
            price=cls._price(html),
            categories=cls._categories(html, title),
            all_sizes=tuple(dict.fromkeys(parser.size_parts)),
            available_sizes=tuple(dict.fromkeys(parser.size_parts)),
            size_guide_url=None,
            size_guide=size_guide_parser.size_guide or None,
        )

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlparse(url)

        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    @classmethod
    def _product_images(
        cls,
        image_urls: Iterable[str],
        product_id: int,
    ) -> tuple[str, ...]:
        product_path = f"/files/productos/{product_id}/"

        return tuple(
            dict.fromkeys(
                cls._canonical_url(urljoin(BASE_URL, image_url))
                for image_url in image_urls
                if product_path in image_url
                if not urlparse(image_url).path.endswith(".webp")
            )
        )

    @staticmethod
    def _price(html: str) -> float:
        price_start = html.find('id="precios"')
        price_html = html[price_start : price_start + 500]
        off_match = re.search(
            r'class="off"[^>]*>\s*\$\s*([\d.]+(?:,\d+)?)',
            price_html,
        )
        match = off_match or MONEY_PATTERN.search(price_html)

        if match is None:
            raise ValueError("Missing product price")

        return float(match.group(1).replace(".", "").replace(",", "."))

    @staticmethod
    def _gender(sku: str) -> str:
        if sku.startswith("D"):
            return "woman"

        if sku.startswith("B"):
            return "man"

        return "unisex"

    @staticmethod
    def _categories(html: str, title: str) -> tuple[str, ...]:
        if match := ITEM_CATEGORY_PATTERN.search(html):
            return (unescape(match.group(1)).casefold(),)

        normalized_title = TAG_PATTERN.sub(" ", unescape(title)).casefold()

        return tuple(
            dict.fromkeys(
                category
                for word, category in CATEGORY_NAMES.items()
                if word in normalized_title
            )
        )
