import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

from ropa.collectors.ropa_revolver import RopaRevolverCollector
from ropa.meta.interfaces import shopify

PRODUCT = {
    "id": 123,
    "title": "Remera JR Verde",
    "handle": "remera-jr-verde",
    "body_html": "<p>Remera de algodón.</p>",
    "product_type": "Remera FERIA",
    "images": [
        {"src": "https://cdn.shopify.com/front.jpg"},
        {"src": "https://cdn.shopify.com/front.jpg"},
    ],
    "options": [
        {"name": "Talle", "position": 1},
        {"name": "Color", "position": 2},
    ],
    "variants": [
        {
            "available": True,
            "price": "32950.00",
            "option1": "S",
            "option2": "Verde",
        },
        {
            "available": False,
            "price": "33950.00",
            "option1": "M",
            "option2": "Verde",
        },
    ],
}


def test_product_to_item_normalizes_shopify_product() -> None:
    item = RopaRevolverCollector().product_to_item(
        PRODUCT,
        "https://roparevolver.com/cdn/shop/files/guia.jpg",
    )

    assert item.model_dump() == {
        "vendor": "Ropa Revolver",
        "product_id": 123,
        "title": "remera jr verde",
        "url": "https://roparevolver.com/products/remera-jr-verde",
        "description": "Remera de algodón.",
        "image_urls": ("https://cdn.shopify.com/front.jpg",),
        "colors": ("verde",),
        "gender": "unisex",
        "price": 32950.0,
        "categories": ("remera",),
        "all_sizes": ("S", "M"),
        "available_sizes": ("S",),
        "size_guide_url": (
            "https://roparevolver.com/cdn/shop/files/guia.jpg"
        ),
    }


def test_sitemap_parser_ignores_nested_image_locations() -> None:
    document = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
      <url>
        <loc>https://roparevolver.com/products/remera-jr-verde</loc>
        <image:image>
          <image:loc>
            https://cdn.shopify.com/files/products/remera-jr-verde.jpg
          </image:loc>
        </image:image>
      </url>
      <url><loc>https://roparevolver.com/collections/all</loc></url>
    </urlset>
    """

    collector = RopaRevolverCollector()

    assert collector._product_urls_from_sitemap_document(document) == (
        "https://roparevolver.com/products/remera-jr-verde",
    )


def test_fallback_product_normalizes_shopify_js_shape() -> None:
    product = RopaRevolverCollector()._normalize_fallback_product(
        {
            "description": "<p>Remera.</p>",
            "type": "Remera",
            "images": ["//roparevolver.com/front.jpg"],
            "options": ["Talle", "Color"],
            "variants": [{"price": 3295000}],
        }
    )

    assert product["body_html"] == "<p>Remera.</p>"
    assert product["product_type"] == "Remera"
    assert product["images"] == (
        {"src": "https://roparevolver.com/front.jpg"},
    )
    assert product["options"] == (
        {"name": "Talle", "position": 1},
        {"name": "Color", "position": 2},
    )
    assert product["variants"][0]["price"] == 32950.0


def test_collection_closes_cache_before_event_loop_exits(monkeypatch) -> None:
    collector = RopaRevolverCollector()
    close = AsyncMock()

    async def product_urls_from_sitemap(*_args: object) -> tuple[str, ...]:
        return ()

    async def iter_products(*_args: object) -> AsyncIterator[dict]:
        if False:
            yield {}

    monkeypatch.setattr(
        collector,
        "_product_urls_from_sitemap",
        product_urls_from_sitemap,
    )
    monkeypatch.setattr(collector, "iter_products", iter_products)
    monkeypatch.setattr(shopify._request_text_cached.cache, "close", close)

    assert asyncio.run(collector._collect_items()) == []
    close.assert_awaited_once_with()
