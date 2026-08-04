from abc import ABC, abstractmethod
from unicodedata import category

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    PositiveInt,
    StrictStr,
)


class CatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    vendor: StrictStr
    product_id: PositiveInt
    title: StrictStr
    url: StrictStr
    description: StrictStr
    image_urls: tuple[StrictStr, ...]
    colors: tuple[StrictStr, ...]
    gender: StrictStr
    price: NonNegativeFloat
    categories: tuple[StrictStr, ...]
    all_sizes: tuple[StrictStr, ...]
    available_sizes: tuple[StrictStr, ...]
    size_guide_url: StrictStr | None


class CatalogCollector(ABC):
    """Common interface for catalog collectors."""

    @staticmethod
    def normalize_color(color: str) -> str:
        """Lowercase a color and remove punctuation."""
        without_punctuation = "".join(
            " " if category(character).startswith("P") else character
            for character in color.lower()
        )

        return " ".join(without_punctuation.split())

    @abstractmethod
    def collect_items(self) -> list[CatalogItem]:
        """Collect public catalog items."""
        ...
