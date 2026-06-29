import json

from re import findall
from unicodedata import normalize
from collections.abc import Iterator
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ropa.meta.interfaces import CatalogItem, ShopifyCollector

from ropa.meta.interfaces.shopify import JsonObject


HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
}
ROPA_REVOLVER_GENDERS = {
    "man": {"hombre", "hombres"},
    "woman": {"mujer", "mujeres"},
}


class RopaRevolverCollector(ShopifyCollector):
    color_option_names = {"color"}
    size_option_names = {"talle"}

    def __init__(self, page_size: int = 250, timeout_seconds: int = 30) -> None:
        super().__init__(
            base_url="https://roparevolver.com",
            vendor="Ropa Revolver",
            page_size=page_size,
            timeout_seconds=timeout_seconds,
        )

    def iter_items(self) -> Iterator[CatalogItem]:
        """Yield products from the stable Shopify products endpoint."""
        items = (
            item
            for product in self.iter_products()
            for item in self.product_to_items(product, self.category(product))
        )

        yield from items

    def category(self, product: JsonObject) -> str:
        """Return Ropa Revolver's own product type as the category."""
        return str(product.get("product_type") or "Uncategorized")

    def gender(self, product: JsonObject, category: str) -> str:
        """Infer item gender from Ropa Revolver product text."""
        tokens = self._gender_tokens(
            category,
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
        request = Request(request_url, headers=HEADERS)

        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)
