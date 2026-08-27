from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from re import escape, search
from typing import Any
from unicodedata import category, normalize

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveInt,
    StrictStr,
    computed_field,
    field_validator,
)

from ropa.ontology.colors import INVERTED_COLOR_MAP, Color
from ropa.ontology.constructions import (
    INVERTED_CONSTRUCTION_MAP,
    Construction,
)
from ropa.ontology.item_types import (
    INVERTED_ITEM_TYPE_MAP,
    ItemType,
)
from ropa.ontology.materials import (
    INVERTED_MATERIAL_MAP,
    Material,
)
from ropa.ontology.sizes import INVERTED_SIZE_MAP, Size


class CatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    vendor: StrictStr = Field(description="Name of the product vendor")
    product_id: PositiveInt = Field(description="Vendor-specific product identifier")
    title: StrictStr = Field(description="Product title")
    url: StrictStr = Field(description="URL of the product page")
    description: StrictStr = Field(description="Product description")
    image_urls: tuple[StrictStr, ...] = Field(
        description="URLs of the product images"
    )

    colors: tuple[StrictStr, ...] = Field(description="Product color names")
    gender: StrictStr = Field(description="Gender targeted by the product")
    price: NonNegativeFloat = Field(description="Product price")
    categories: tuple[StrictStr, ...] = Field(
        description="Categories assigned to the product"
    )

    all_sizes: tuple[StrictStr, ...] = Field(
        description="All sizes offered for the product"
    )

    available_sizes: tuple[StrictStr, ...] = Field(
        description="Sizes currently available for the product"
    )

    size_guide_url: StrictStr | None = Field(
        description="URL of the product size guide"
    )

    size_guide: dict[str, Any] | None = Field(
        default=None,
        description="Structured product size guide",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, title: str) -> str:
        return title.lower()

    @field_validator("colors")
    @classmethod
    def normalize_colors(cls, colors: tuple[str, ...]) -> tuple[str, ...]:
        normalized_colors = map(cls._normalize_color, colors)

        return tuple(
            color
            for color in normalized_colors
            if color not in {"color unico", "unico", "único"}
        )

    @computed_field(description="Normalized color families of the product")
    @property
    def color_family(self) -> tuple[Color, ...]:
        return tuple(
            dict.fromkeys(INVERTED_COLOR_MAP[color] for color in self.colors)
        )

    @computed_field(description="Ontology item types assigned to the product")
    @property
    def item_type(self) -> tuple[ItemType, ...]:
        return tuple(
            dict.fromkeys(
                INVERTED_ITEM_TYPE_MAP[category]
                for category in self.categories
                if category in INVERTED_ITEM_TYPE_MAP
            )
        )

    @computed_field(description="Material families identified in the product text")
    @property
    def material_family(self) -> tuple[Material, ...]:
        variants = self._text_variants(
            self._ontology_text,
            INVERTED_MATERIAL_MAP,
        )

        return tuple(
            dict.fromkeys(INVERTED_MATERIAL_MAP[variant] for variant in variants)
        )

    @computed_field(
        description="Construction families identified in the product text"
    )
    @property
    def construction_family(self) -> tuple[Construction, ...]:
        variants = self._text_variants(
            self._ontology_text,
            INVERTED_CONSTRUCTION_MAP,
        )

        return tuple(
            dict.fromkeys(
                INVERTED_CONSTRUCTION_MAP[variant] for variant in variants
            )
        )

    @computed_field(description="Normalized families of all offered sizes")
    @property
    def all_size_family(self) -> tuple[Size, ...]:
        return self._size_family(self.all_sizes)

    @computed_field(description="Normalized families of currently available sizes")
    @property
    def available_size_family(self) -> tuple[Size, ...]:
        return self._size_family(self.available_sizes)

    @property
    def _ontology_text(self) -> str:
        return " ".join((self.title, self.description, *self.categories))

    @staticmethod
    def _text_variants(text: str, variants: Iterable[str]) -> Iterator[str]:
        comparable_text = text.casefold()

        return (
            variant
            for variant in variants
            if search(
                rf"(?<!\w){escape(variant.casefold())}(?!\w)",
                comparable_text,
            )
        )

    def _size_family(self, sizes: tuple[str, ...]) -> tuple[Size, ...]:
        return tuple(
            dict.fromkeys(
                INVERTED_SIZE_MAP[item_type][size]
                for item_type in self.item_type
                for size in sizes
                if size in INVERTED_SIZE_MAP.get(item_type, {})
            )
        )

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
    @abstractmethod
    def collect_items(self) -> list[CatalogItem]: ...
