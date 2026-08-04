from collections.abc import Iterable
from itertools import islice
from threading import Lock
from time import sleep

import pytest
from rich.console import Console
from rich.table import Table

from ropa.collectors import (
    AyNotDeadCollector,
    BoliviaUniversoCollector,
    CatalogItem,
    RopaRevolverCollector,
)
from ropa.collectors.bolivia_universo import (
    _ProductDetailParser,
    _SizeParser,
)
from ropa.collectors.bolivia_universo import (
    _request_url as bolivia_request_url,
)
from ropa.meta.interfaces.shopify import ShopifyCollector, _request_url
from ropa.meta.size_guides import SizeGuideLinkParser

PRINT_LIMIT = 5
MINIMUM_COLLECTED_ITEMS = 10


def shopify_product(product_id: int) -> dict:
    return {
        "id": product_id,
        "title": f"Product {product_id}",
        "handle": f"product-{product_id}",
        "body_html": "",
        "options": ({"name": "Color", "position": 1},),
        "variants": (
            {
                "available": True,
                "option1": "Black",
                "price": "100.00",
            },
        ),
    }


class ConcurrentShopifyCollector(ShopifyCollector):
    def __init__(self, max_concurrent_requests: int) -> None:
        super().__init__(
            "https://example.myshopify.com",
            "Example",
            max_concurrent_requests=max_concurrent_requests,
        )
        self.active_requests = 0
        self.high_water_mark = 0
        self.lock = Lock()

    def _iter_product_categories(self):
        return (
            (shopify_product(product_id), "Test") for product_id in range(1, 7)
        )

    def _get_text(self, url: str) -> str:
        with self.lock:
            self.active_requests += 1
            self.high_water_mark = max(
                self.high_water_mark,
                self.active_requests,
            )

        sleep(0.01)

        with self.lock:
            self.active_requests -= 1

        return ""


def test_shopify_collector_limits_concurrent_requests() -> None:
    collector = ConcurrentShopifyCollector(max_concurrent_requests=2)

    items = collector.collect_items()

    assert len(items) == 6
    assert collector.high_water_mark == 2


def test_shopify_collector_rejects_invalid_concurrency() -> None:
    with pytest.raises(
        ValueError,
        match="max_concurrent_requests must be greater than zero",
    ):
        ConcurrentShopifyCollector(max_concurrent_requests=0)


def test_shopify_request_url_encodes_non_ascii_paths() -> None:
    url = _request_url("https://example.com/collections/corazón/products.json")

    assert url == ("https://example.com/collections/coraz%C3%B3n/products.json")


def test_bolivia_request_url_encodes_non_ascii_paths() -> None:
    url = bolivia_request_url("https://example.com/categorías/corazón")

    assert url == "https://example.com/categor%C3%ADas/coraz%C3%B3n"


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
            {
                "available": True,
                "option1": "Blanco",
                "option2": "S",
                "price": "110.00",
            },
        ),
    }

    collector = AyNotDeadCollector()
    collector._size_guide_urls[1] = "https://aynotdead.com/pages/guia-de-talles"

    item = collector.product_to_item(product, ("Hombres",))

    assert item.gender == "man"
    assert item.categories == ("Hombres",)
    assert item.colors == ("blanco", "negro")
    assert item.price == 110.00
    assert item.all_sizes == ("S", "M")
    assert item.available_sizes == ("S", "M")
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


def test_bolivia_universo_product_parser_accepts_json_control_characters() -> (
    None
):
    parser = _ProductDetailParser("https://boliviauniverso.com")
    parser.feed(
        """
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Vestido",
            "description": "Primera línea\u000bSegunda línea",
            "offers": {"price": "12345.67"}
        }
        </script>
        """
    )

    assert parser.details().description == "Primera línea\u000bSegunda línea"


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

    item = collector.product_to_item(
        product,
        (collector.category(product),),
    )

    assert item.gender == "woman"
    assert item.colors == ("azul",)
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


@pytest.mark.parametrize(
    "collector",
    (
        AyNotDeadCollector(),
        BoliviaUniversoCollector(),
        RopaRevolverCollector(),
    ),
)
def test_collectors_normalize_colors(collector) -> None:
    assert collector.normalize_color("  Gris-Negro!  ") == "gris negro"


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
