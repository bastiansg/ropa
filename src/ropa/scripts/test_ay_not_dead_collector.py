from argparse import ArgumentParser, Namespace
from collections.abc import Iterable
from itertools import islice

from rich.table import Table
from rich.console import Console

from ropa.collectors import AyNotDeadCollector, ShopifyCatalogItem


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Collect Ay Not Dead catalog data and print sample rows."
    )

    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        help="Number of collected rows to print.",
    )

    return parser.parse_args()


def item_row(item: ShopifyCatalogItem) -> tuple[str, ...]:
    return (
        str(item.product_id),
        item.title,
        item.description,
        "\n".join(item.image_urls),
        item.category,
        item.color or "",
        ", ".join(item.available_sizes),
        item.url,
    )


def catalog_table(items: Iterable[ShopifyCatalogItem], limit: int) -> Table:
    table = Table(title=f"First {limit} Ay Not Dead catalog results")
    table.add_column("Product ID", justify="right", no_wrap=True)
    table.add_column("Title", ratio=2)
    table.add_column("Description", ratio=4, overflow="fold")
    table.add_column("Image URLs", ratio=3, overflow="fold")
    table.add_column("Category")
    table.add_column("Color")
    table.add_column("Available Sizes")
    table.add_column("URL", ratio=2, overflow="fold")

    for row in map(item_row, items):
        table.add_row(*row)

    return table


def main() -> None:
    args = parse_args()
    collector = AyNotDeadCollector()
    limit = max(args.limit, 0)
    items = islice(collector.iter_items(), limit)

    Console().print(catalog_table(items, limit))


if __name__ == "__main__":
    main()
