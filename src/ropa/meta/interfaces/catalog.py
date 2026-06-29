from abc import ABC, abstractmethod
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    PositiveInt,
    PositiveFloat,
)


class CatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    vendor: StrictStr
    product_id: PositiveInt
    title: StrictStr
    url: StrictStr
    description: StrictStr
    image_urls: tuple[StrictStr, ...]
    color: StrictStr
    gender: StrictStr
    price: PositiveFloat
    category: StrictStr
    available_sizes: tuple[StrictStr, ...]


class CatalogCollector(ABC):
    """Common interface for catalog collectors."""

    @abstractmethod
    def collect_items(self) -> list[CatalogItem]:
        """Collect public catalog items."""
        ...
