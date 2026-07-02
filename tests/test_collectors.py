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

from ropa.collectors.bolivia_universo import _ProductDetailParser, _SizeParser
from ropa.meta.size_guides import SizeGuideLinkParser


PRINT_LIMIT = 5
MINIMUM_COLLECTED_ITEMS = 10


def item_row(item: CatalogItem) -> tuple[str, ...]:
    values = (
        getattr(item, field_name) for field_name in CatalogItem.model_fields
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

    collector = AyNotDeadCollector()
    collector._size_guide_urls[1] = "https://aynotdead.com/pages/guia-de-talles"

    item = next(collector.product_to_items(product, "Hombres"))

    assert item.gender == "man"
    assert item.price == 120.50
    assert item.all_sizes == ("S", "M")
    assert item.available_sizes == ("M",)
    assert item.size_guide_url == "https://aynotdead.com/pages/guia-de-talles"


def test_bolivia_universo_collector_collects_gender_and_price() -> None:
    parser = _ProductDetailParser(
        "https://boliviauniverso.com",
        "https://boliviauniverso.com/productos/BW2640008-10/",
    )
    parser.feed(
        """
        <a role="button" title="TABLA DE TALLES" class="guia-talles"
            onclick="javascript:$('#medidas').modal();">
            TABLA DE TALLES
        </a>
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
    assert details.price == 12345.67
    assert (
        details.size_guide_url
        == "https://boliviauniverso.com/productos/BW2640008-10/#medidas"
    )


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
            {
                "available": False,
                "option1": "Azul",
                "option2": "M",
                "price": "220.00",
            },
        ),
    }

    collector = RopaRevolverCollector()
    collector._size_guide_urls[1] = (
        "https://roparevolver.com/cdn/shop/files/parka.jpg"
    )

    item = next(
        collector.product_to_items(product, collector.category(product))
    )

    assert item.gender == "woman"
    assert item.price == 220.00
    assert item.all_sizes == ("S", "M")
    assert item.available_sizes == ("S",)
    assert item.size_guide_url == (
        "https://roparevolver.com/cdn/shop/files/parka.jpg"
    )


def test_bolivia_universo_size_parser_collects_all_and_available_sizes() -> (
    None
):
    parser = _SizeParser()
    parser.feed(
        """
        <label class="btn btn-default">SM</label>
        <fieldset disabled class="btn btn-default btn-disabled">ME</fieldset>
        <label class="btn btn-default">LA</label>
        """
    )

    assert tuple(parser.all_sizes) == ("SM", "ME", "LA")
    assert tuple(parser.available_sizes) == ("SM", "LA")


def test_size_guide_parser_prefers_direct_guide_assets() -> None:
    parser = SizeGuideLinkParser(
        "https://roparevolver.com",
        "https://roparevolver.com/products/parka-fuji-negro",
    )
    parser.feed(
        """
        <link href="//roparevolver.com/cdn/shop/t/21/assets/size-guide-modal.css"
            rel="stylesheet">
        <modal-opener data-modal="#size-guide-modal-9014493184223">
            <button class="size-guide-button">VER GUIA DE TALLES</button>
        </modal-opener>
        <modal-dialog id="size-guide-modal-9014493184223"
            class="size-guide-modal">
            <img src="//roparevolver.com/cdn/shop/files/Parka_Fuji.jpg"
                alt="Guia de Talles">
        </modal-dialog>
        """
    )

    assert (
        parser.url() == "https://roparevolver.com/cdn/shop/files/Parka_Fuji.jpg"
    )


def test_bolivia_universo_collector_returns_catalog_items() -> None:
    collector = BoliviaUniversoCollector(
        listing_urls=("lo-nuevo/",),
        max_pages_per_listing=0,
    )
    items = tuple(islice(collector.iter_items(), MINIMUM_COLLECTED_ITEMS))

    assert_collector_returns_minimum_items("Bolivia Universo", items)


def test_ropa_revolver_collector_returns_catalog_items() -> None:
    collector = RopaRevolverCollector()
    items = tuple(islice(collector.iter_items(), MINIMUM_COLLECTED_ITEMS))

    assert_collector_returns_minimum_items("Ropa Revolver", items)
