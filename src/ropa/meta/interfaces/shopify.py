import json

from typing import Any, cast
from itertools import chain, groupby

from html.parser import HTMLParser
from collections.abc import Iterator
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ropa.meta.interfaces.catalog import CatalogCollector, CatalogItem


JsonObject = dict[str, Any]


ShopifyCatalogItem = CatalogItem


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)

    def text(self) -> str:
        return " ".join(self.parts)


class ShopifyCollector(CatalogCollector):
    """Collect public catalog data from Shopify storefront JSON endpoints."""

    color_option_names = frozenset({"color", "colour"})
    size_option_names = frozenset({"size", "talle", "tamaño", "tamano"})

    def __init__(
        self,
        base_url: str,
        vendor: str,
        page_size: int = 250,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.vendor = vendor
        self.page_size = page_size
        self.timeout_seconds = timeout_seconds

    def collect_items(self) -> list[ShopifyCatalogItem]:
        """Collect all public catalog items grouped by category and color."""
        return list(self.iter_items())

    def iter_items(self) -> Iterator[ShopifyCatalogItem]:
        """Yield public catalog items grouped by collection category and color."""
        seen_keys: set[tuple[int, str | None, str]] = set()
        categorized_product_ids: set[int] = set()

        for collection in self.iter_collections():
            if not collection.get("products_count", 1):
                continue

            category = str(
                collection.get("title") or collection.get("handle") or ""
            )
            collection_handle = str(collection["handle"])
            product_items = (
                item
                for product in self.iter_collection_products(collection_handle)
                for item in self.product_to_items(product, category)
            )

            for item in product_items:
                key = (item.product_id, item.color, item.category)
                if key in seen_keys:
                    continue

                seen_keys.add(key)
                categorized_product_ids.add(item.product_id)
                yield item

        uncategorized_items = (
            item
            for product in self.iter_products()
            if int(product["id"]) not in categorized_product_ids
            for item in self.product_to_items(product, "Uncategorized")
        )

        yield from uncategorized_items

    def iter_products(self) -> Iterator[JsonObject]:
        """Yield all public storefront products."""
        yield from self._paginate_objects("/products.json", "products")

    def iter_collections(self) -> Iterator[JsonObject]:
        """Yield all public storefront collections."""
        yield from self._paginate_objects("/collections.json", "collections")

    def iter_collection_products(
        self, collection_handle: str
    ) -> Iterator[JsonObject]:
        """Yield public products for a collection handle."""
        path = f"/collections/{collection_handle}/products.json"
        yield from self._paginate_objects(path, "products")

    def product_to_items(
        self, product: JsonObject, category: str
    ) -> Iterator[ShopifyCatalogItem]:
        """Normalize one Shopify product into item records."""
        color_position = self._option_position(product, self.color_option_names)
        size_position = self._option_position(product, self.size_option_names)
        color_groups = {
            color: self._available_sizes(variants, size_position)
            for color, variants in self._group_variants_by_color(
                product, color_position
            ).items()
        }

        return (
            ShopifyCatalogItem(
                vendor=self.vendor,
                product_id=int(product["id"]),
                title=str(product.get("title") or ""),
                url=self.product_url(product),
                description=self.description(product),
                image_urls=self.image_urls(product),
                color=color,
                category=category,
                available_sizes=sizes,
            )
            for color, sizes in color_groups.items()
        )

    def product_url(self, product: JsonObject) -> str:
        """Build the canonical storefront URL for a product."""
        return f"{self.base_url}/products/{product['handle']}"

    def description(self, product: JsonObject) -> str:
        """Return a normalized text description for a Shopify product."""
        parser = _HTMLTextExtractor()
        parser.feed(
            str(product.get("body_html") or product.get("description") or "")
        )

        return parser.text()

    def image_urls(self, product: JsonObject) -> tuple[str, ...]:
        """Return unique Shopify image URLs for a product."""
        featured_image = product.get("image")
        featured_images = (
            (featured_image,) if isinstance(featured_image, dict) else ()
        )

        return tuple(
            dict.fromkeys(
                str(url)
                for image in chain(featured_images, product.get("images") or ())
                if isinstance(image, dict)
                for url in (image.get("src"),)
                if url
            )
        )

    def _paginate_objects(self, path: str, key: str) -> Iterator[JsonObject]:
        page = 1

        while True:
            response = self._get_json(
                path, {"limit": self.page_size, "page": page}
            )
            raw_objects = cast(Iterator[JsonObject], response.get(key) or ())
            objects = tuple(raw_objects)
            if not objects:
                return

            yield from objects
            page += 1

    def _get_json(self, path: str, params: dict[str, int | str]) -> JsonObject:
        query = urlencode(params)
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        request_url = f"{url}?{query}" if query else url
        request = Request(request_url, headers={"Accept": "application/json"})

        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)

    def _option_position(
        self, product: JsonObject, names: frozenset[str]
    ) -> int | None:
        matches = (
            int(option["position"])
            for option in product.get("options", ())
            if str(option.get("name", "")).casefold() in names
        )

        return next(matches, None)

    def _group_variants_by_color(
        self,
        product: JsonObject,
        color_position: int | None,
    ) -> dict[str | None, tuple[JsonObject, ...]]:
        variants = sorted(
            product.get("variants", ()),
            key=lambda variant: (
                self._variant_option(variant, color_position) or ""
            ),
        )

        colors = {
            color: tuple(grouped_variants)
            for color, grouped_variants in groupby(
                variants,
                key=lambda variant: self._variant_option(
                    variant, color_position
                ),
            )
        }

        return colors or {None: tuple()}

    def _available_sizes(
        self, variants: tuple[JsonObject, ...], size_position: int | None
    ) -> tuple[str, ...]:
        sizes = dict.fromkeys(
            size
            for variant in variants
            if variant.get("available")
            for size in (self._variant_option(variant, size_position),)
            if size
        )

        return tuple(sizes)

    def _variant_option(
        self, variant: JsonObject, position: int | None
    ) -> str | None:
        if position is None:
            return None

        value = variant.get(f"option{position}")
        if value is None:
            return None

        return str(value)
