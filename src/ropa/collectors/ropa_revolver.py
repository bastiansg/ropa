import json
from collections.abc import Iterator
from re import findall
from typing import cast
from unicodedata import normalize
from urllib.parse import urlencode, urljoin
from urllib.request import Request

from ropa.meta.interfaces import ShopifyCollector
from ropa.meta.interfaces.shopify import JsonObject, _request_text, _request_url

BASE_HEADERS = {
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
}
JSON_HEADERS = {"Accept": "application/json", **BASE_HEADERS}
HTML_HEADERS = {"Accept": "text/html,application/xhtml+xml", **BASE_HEADERS}
ROPA_REVOLVER_GENDERS = {
    "man": {"hombre", "hombres"},
    "woman": {"mujer", "mujeres"},
}


class RopaRevolverCollector(ShopifyCollector):
    color_option_names = {"color"}
    size_option_names = {"talle"}

    def __init__(
        self,
        page_size: int = 250,
        timeout_seconds: int = 30,
        max_concurrent_requests: int = 8,
        min_request_interval_seconds: float = 0.5,
    ) -> None:
        super().__init__(
            base_url="https://roparevolver.com",
            vendor="Ropa Revolver",
            page_size=page_size,
            timeout_seconds=timeout_seconds,
            max_concurrent_requests=max_concurrent_requests,
            min_request_interval_seconds=min_request_interval_seconds,
        )

    def _iter_product_categories(self) -> Iterator[tuple[JsonObject, str]]:
        """Yield products from the Shopify products endpoint."""
        yield from (
            (product, self.category(product)) for product in self.iter_products()
        )

    def category(self, product: JsonObject) -> str:
        """Return Ropa Revolver's own product type as the category."""
        return str(product.get("product_type") or "Uncategorized")

    def gender(self, product: JsonObject, categories: tuple[str, ...]) -> str:
        """Infer item gender from Ropa Revolver product text."""
        tokens = self._gender_tokens(
            *categories,
            product.get("title"),
            product.get("handle"),
            " ".join(str(tag) for tag in product.get("tags") or ()),
        )

        return next(
            (
                gender
                for gender, gender_tokens in ROPA_REVOLVER_GENDERS.items()
                if tokens & gender_tokens
            ),
            "unisex",
        )

    def _gender_tokens(self, *values: object) -> set[str]:
        text = " ".join(str(value or "") for value in values)
        ascii_text = normalize("NFKD", text).encode("ascii", "ignore").decode()

        return set(findall(r"[a-zA-Z]+", ascii_text.casefold()))

    def _get_json(self, path: str, params: dict[str, int | str]) -> JsonObject:
        query = urlencode(params)
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        request_url = f"{url}?{query}" if query else url
        request = Request(_request_url(request_url), headers=JSON_HEADERS)

        return cast(
            JsonObject,
            json.loads(
                _request_text(
                    request,
                    self.timeout_seconds,
                    request_started=self._wait_for_request_slot,
                )
            ),
        )

    def _get_text(self, url: str) -> str:
        request = Request(
            _request_url(urljoin(self.base_url, url)),
            headers=HTML_HEADERS,
        )

        return _request_text(
            request,
            self.timeout_seconds,
            request_started=self._wait_for_request_slot,
        )
