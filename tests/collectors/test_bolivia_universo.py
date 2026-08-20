from ropa.collectors.bolivia_universo import (
    BoliviaUniversoCollector,
    _CatalogHTMLParser,
)

PRODUCT_HTML = """
<html>
  <head>
    <script>'item_category': 'Buzos y Sweaters'</script>
  </head>
  <body>
    <h1 data-fitit="title">SWEATER DIVINA LANA</h1>
    <div id="precios" class="precios">
      <span class="antes">$ 269.900</span>
      <span class="off">$ 199.900</span>
    </div>
    <p data-fitit="description">Sweater tejido con texturas.</p>
    <span data-fitit="sku">DW2650001-11</span>
    <div data-fitit="sizes">
      <label><input type="radio">XS</label>
      <label><input type="radio">SM</label>
    </div>
    <div data-fitit="colors">
      <a class="btn btn-otros active" title="GRIS"></a>
      <a class="btn btn-otros" title="NEGRO"></a>
    </div>
    <input id="idProducto" type="hidden" value="3720">
    <img src="/files/productos/3720/front.jpg?v=2.0">
    <source srcset="/files/productos/3720/front.jpg.webp?v=2.0">
    <img src="/files/productos/9999/related.jpg">
  </body>
</html>
"""


def test_catalog_parser_deduplicates_canonical_product_urls() -> None:
    parser = _CatalogHTMLParser()
    parser.feed(
        """
        <a href="https://boliviauniverso.com/productos/DW2650001-11/">
        <a href="productos/DW2650001-11/?utm_source=grid">
        <a href="/categorias/coleccion/">
        """
    )

    assert tuple(dict.fromkeys(parser.product_urls)) == (
        "https://boliviauniverso.com/productos/DW2650001-11/",
    )


def test_html_to_item_normalizes_product_page() -> None:
    item = BoliviaUniversoCollector._html_to_item(
        "https://boliviauniverso.com/productos/DW2650001-11/?tracking=1",
        PRODUCT_HTML,
    )

    assert item.model_dump() == {
        "vendor": "Bolivia - Divina",
        "product_id": 3720,
        "title": "sweater divina lana",
        "url": "https://boliviauniverso.com/productos/DW2650001-11/",
        "description": "Sweater tejido con texturas.",
        "image_urls": (
            "https://boliviauniverso.com/files/productos/3720/front.jpg",
        ),
        "colors": ("gris",),
        "gender": "woman",
        "price": 199900.0,
        "categories": ("buzos y sweaters",),
        "all_sizes": ("XS", "SM"),
        "available_sizes": ("XS", "SM"),
        "size_guide_url": None,
    }


def test_html_to_item_falls_back_to_title_category() -> None:
    html = PRODUCT_HTML.replace(
        "<script>'item_category': 'Buzos y Sweaters'</script>",
        "",
    ).replace("SWEATER DIVINA LANA", "PANTALON DIVINA")

    item = BoliviaUniversoCollector._html_to_item(
        "https://boliviauniverso.com/productos/DW2620002-18/",
        html,
    )

    assert item.categories == ("pantalones",)
