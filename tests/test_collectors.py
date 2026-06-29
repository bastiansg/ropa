from decimal import Decimal
from collections.abc import Iterable
from itertools import islice

from rich.table import Table
from rich.console import Console

from ropa.collectors import (
    AyNotDeadCollector,
    BoliviaUniversoCollector,
    CatalogItem,
    RopaRevolverCollector,
)
from ropa.collectors.bolivia_universo import _ProductDetailParser


PRINT_LIMIT = 5
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
    Console().print(
        catalog_table(
            collector_name,
            islice(items, PRINT_LIMIT),
            PRINT_LIMIT,
        )
    )

    assert len(items) >= MINIMUM_COLLECTED_ITEMS


def test_ay_not_dead_collector_returns_catalog_items() -> None:
    collector = AyNotDeadCollector()
    items = tuple(collector.collect_items(limit=MINIMUM_COLLECTED_ITEMS))

    assert_collector_returns_minimum_items("Ay Not Dead", items)


def test_ay_not_dead_collector_collects_gender_and_price() -> None:
    product = {
        "id": 1,
        "title": "Campera Hombre",
        "handle": "campera-hombre",
        "body_html": "",
        "options": (
            {"name": "Color", "position": 1},
            {"name": "Talle", "position": 2},
        ),
        "variants": (
            {
                "available": False,
                "option1": "Negro",
                "option2": "S",
                "price": "100.00",
            },
            {
                "available": True,
                "option1": "Negro",
                "option2": "M",
                "price": "120.50",
            },
        ),
    }

    item = next(AyNotDeadCollector().product_to_items(product, "Hombres"))

    assert item.gender == "man"
    assert item.price == Decimal("120.50")


def test_bolivia_universo_collector_collects_gender_and_price() -> None:
    parser = _ProductDetailParser("https://boliviauniverso.com")
    parser.feed(
        """
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Vestido",
            "description": "Producto para mujer",
            "image": "/vestido.jpg",
            "offers": {"price": "12345.67"}
        }
        </script>
        """
    )

    collector = BoliviaUniversoCollector()
    details = parser.details()

    assert collector.gender("categorias/mujeres", details.title) == "woman"
    assert details.price == Decimal("12345.67")


def test_ropa_revolver_collector_collects_gender_and_price() -> None:
    product = {
        "id": 1,
        "title": "Pantalon Mujer",
        "handle": "pantalon-mujer",
        "product_type": "Mujer",
        "body_html": "",
        "options": (
            {"name": "Color", "position": 1},
            {"name": "Talle", "position": 2},
        ),
        "variants": (
            {
                "available": True,
                "option1": "Azul",
                "option2": "S",
                "price": "220.00",
            },
        ),
    }

    collector = RopaRevolverCollector()

    item = next(collector.product_to_items(product, collector.category(product)))

    assert item.gender == "woman"
    assert item.price == Decimal("220.00")


def test_bolivia_universo_collector_returns_catalog_items() -> None:
    collector = BoliviaUniversoCollector(
        listing_urls=("lo-nuevo/",),
        max_pages_per_listing=0,
    )
    items = tuple(
        islice(collector.iter_items(), MINIMUM_COLLECTED_ITEMS)
    )

    assert_collector_returns_minimum_items("Bolivia Universo", items)


def test_ropa_revolver_collector_returns_catalog_items() -> None:
    collector = RopaRevolverCollector()
    items = tuple(
        islice(collector.iter_items(), MINIMUM_COLLECTED_ITEMS)
    )

    assert_collector_returns_minimum_items("Ropa Revolver", items)
