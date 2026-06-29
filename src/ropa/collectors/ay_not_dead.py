from re import findall
from typing import Literal
from itertools import islice
from unicodedata import normalize

from ropa.config import config  # noqa
from ropa.meta.interfaces import CatalogItem, ShopifyCollector
from ropa.meta.interfaces.shopify import JsonObject


type Gender = Literal["man", "woman"]
AY_NOT_DEAD_GENDERS = {
    "man": {
        "hombre",
        "hombres",
        "man",
        "men",
    },
    "woman": {
        "mujer",
        "mujeres",
        "woman",
        "women",
    },
}


class AyNotDeadCollector(ShopifyCollector):
    def __init__(
        self,
        page_size: int = 250,
        timeout_seconds: int = 30,
    ) -> None:
        super().__init__(
            base_url="https://aynotdead.com",
            vendor="Ay Not Dead",
            page_size=page_size,
            timeout_seconds=timeout_seconds,
        )

    def collect_items(self, limit: int | None = None) -> list[CatalogItem]:
        """Collect catalog items."""
        return list(islice(self.iter_items(), limit))

    def gender(self, product: JsonObject, category: str) -> str:
        """Infer item gender from Ay Not Dead product and collection text."""
        tokens = self._gender_tokens(
            category,
            product.get("title"),
            product.get("handle"),
            " ".join(str(tag) for tag in product.get("tags") or ()),
        )

        return next(
            (
                gender
                for gender, gender_tokens in AY_NOT_DEAD_GENDERS.items()
                if tokens & gender_tokens
            ),
            "unisex",
        )

    def _gender_tokens(self, *values: object) -> set[str]:
        text = " ".join(str(value or "") for value in values)
        ascii_text = normalize("NFKD", text).encode("ascii", "ignore").decode()

        return set(findall(r"[a-zA-Z]+", ascii_text.casefold()))
