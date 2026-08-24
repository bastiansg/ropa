from collections.abc import Iterable

from ropa.meta.interfaces import JsonObject, ShopifyCollector


class RopaRevolverCollector(ShopifyCollector):

    base_url = "https://roparevolver.com"
    vendor = "Ropa Revolver"
    cache_namespace = "ropa_revolver:http"

    def products_for_size_guides(
        self,
        products: Iterable[JsonObject],
    ) -> Iterable[JsonObject]:
        return (
            product
            for product in products
            if self._option_position(product, "talle") is not None
        )

    def categories(self, product: JsonObject) -> tuple[str, ...]:
        product_type = str(product.get("product_type") or "").casefold()
        category = product_type.removesuffix(" feria")

        return (category,) if category else ()
