from abc import ABC, abstractmethod
from unicodedata import category, normalize

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    PositiveInt,
    StrictStr,
    field_validator,
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

    @field_validator("title")
    @classmethod
    def normalize_title(cls, title: str) -> str:
        return title.lower()

    @field_validator("colors")
    @classmethod
    def normalize_colors(cls, colors: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(map(cls._normalize_color, colors))

    @staticmethod
    def _normalize_color(color: str) -> str:
        without_punctuation = "".join(
            " " if category(character).startswith("P") else character
            for character in color.lower()
        )

        return " ".join(without_punctuation.split())

    @field_validator("all_sizes", "available_sizes")
    @classmethod
    def normalize_sizes(cls, sizes: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(map(cls._normalize_size, sizes)))

    @staticmethod
    def _normalize_size(size: str) -> str:
        comparable_size = "".join(
            character
            for character in normalize("NFKD", size)
            if not category(character).startswith("M")
        ).casefold()

        if comparable_size.strip() in {"u", "un", "unico", "one size"}:
            return "ONE SIZE"

        return size


class CatalogCollector(ABC):
    """Common interface for catalog collectors."""

    @abstractmethod
    def collect_items(self) -> list[CatalogItem]:
        """Collect public catalog items."""
        ...
