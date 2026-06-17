from ropa.meta.interfaces import ShopifyCollector


class AyNotDeadCollector(ShopifyCollector):
    color_option_names = frozenset({"color"})
    size_option_names = frozenset({"talle"})

    def __init__(self, page_size: int = 250, timeout_seconds: int = 30) -> None:
        super().__init__(
            base_url="https://aynotdead.com",
            vendor="Ay Not Dead",
            page_size=page_size,
            timeout_seconds=timeout_seconds,
        )
