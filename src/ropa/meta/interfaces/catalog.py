from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class CatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    vendor: str
    product_id: int
    title: str
    url: str
    description: str
    image_urls: tuple[str, ...]
    color: str | None
    category: str
    available_sizes: tuple[str, ...]


class CatalogCollector(ABC):
    """Common interface for catalog collectors."""

    @abstractmethod
    def collect_items(self) -> list[CatalogItem]:
        """Collect public catalog items."""
        ...
