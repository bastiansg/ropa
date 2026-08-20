from ropa.meta.interfaces import JsonObject, ShopifyCollector

CATEGORY_TAGS = {
    "abrigos",
    "accesorios",
    "anteojos",
    "billeteras",
    "buzos",
    "camisas",
    "campera",
    "camperas",
    "caps",
    "carteras",
    "carteras y bolsos",
    "cinturones",
    "cuero",
    "jeans",
    "mochilas y bolsos",
    "pantalones",
    "polleras",
    "remeras",
    "shorts",
    "socks",
    "sweaters",
    "tejidos",
    "tops",
    "underwear",
    "vestidos",
    "zapatos",
}
MAN_TAGS = {"hombre", "hombre_fw26", "hombres", "man", "men"}
WOMAN_TAGS = {"mujer", "mujer_fw26", "mujeres", "woman", "women"}
UNISEX_TAGS = {"unisex", "unisex_fw26"}


class AyNotDeadCollector(ShopifyCollector):
    """Collect AY NOT DEAD products from its public Shopify storefront."""

    base_url = "https://aynotdead.com"
    vendor = "Ay Not Dead"
    cache_namespace = "ay_not_dead:http"

    def gender(self, product: JsonObject) -> str:
        tags = set(self._tags(product))
        has_man = bool(tags & MAN_TAGS)
        has_woman = bool(tags & WOMAN_TAGS)

        if tags & UNISEX_TAGS or has_man and has_woman:
            return "unisex"

        if has_man:
            return "man"

        if has_woman:
            return "woman"

        return "unisex"

    def categories(self, product: JsonObject) -> tuple[str, ...]:
        product_type = str(product.get("product_type") or "").casefold()

        return tuple(
            dict.fromkeys(
                category
                for category in (*self._tags(product), product_type)
                if category in CATEGORY_TAGS
            )
        )
