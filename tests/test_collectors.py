from collections.abc import Iterable
from itertools import islice

from rich.table import Table
from rich.console import Console

from ropa.collectors import (
    AyNotDeadCollector,
    BoliviaUniversoCollector,
    CatalogItem,
)


ROW_LIMIT = 10
MINIMUM_COLLECTED_ITEMS = 10


def item_row(item: CatalogItem) -> tuple[str, ...]:
    values = (
        getattr(item, field_name)
        for field_name in CatalogItem.model_fields
    )

    return tuple(format_value(value) for value in values)


def format_value(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, tuple):
        return "\n".join(str(item) for item in value)

    return str(value)


def catalog_table(
    title: str, items: Iterable[CatalogItem], limit: int
) -> Table:
    table = Table(title=f"{title}: first {limit} catalog results")
    for field_name in CatalogItem.model_fields:
        table.add_column(field_name.replace("_", " ").title(), overflow="fold")

    for row in map(item_row, items):
        table.add_row(*row)

    return table


def assert_collector_returns_minimum_items(
    collector_name: str, items: tuple[CatalogItem, ...]
) -> None:
    Console().print(catalog_table(collector_name, items, ROW_LIMIT))

    assert len(items) >= MINIMUM_COLLECTED_ITEMS


def test_ay_not_dead_collector_returns_catalog_items() -> None:
    collector = AyNotDeadCollector()
    items = tuple(islice(collector.iter_items(), ROW_LIMIT))

    assert_collector_returns_minimum_items("Ay Not Dead", items)


def test_bolivia_universo_collector_returns_catalog_items() -> None:
    collector = BoliviaUniversoCollector(
        listing_urls=("lo-nuevo/",),
        max_pages_per_listing=0,
    )
    items = tuple(islice(collector.iter_items(), ROW_LIMIT))

    assert_collector_returns_minimum_items("Bolivia Universo", items)
