import asyncio
from collections.abc import Sequence
from itertools import chain

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ropa.db import get_mongo_connector

COLLECTION_NAME = "catalog_items"


def aggregation_pipeline(field: str, *, is_array: bool) -> list[dict]:
    """Build a pipeline that counts unique field values and their vendors."""
    values = f"${field}" if is_array else [f"${field}"]

    return [
        {"$project": {"vendor": 1, "value": values}},
        {"$unwind": "$value"},
        {"$match": {"value": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$value",
                "count": {"$sum": 1},
                "vendors": {"$addToSet": "$vendor"},
            },
        },
        {"$sort": {"count": -1, "_id": 1}},
    ]


async def aggregate(field: str, *, is_array: bool) -> list[dict]:
    """Return unique catalog values with their counts and vendors."""
    collection = get_mongo_connector().db[COLLECTION_NAME]
    cursor = await collection.aggregate(
        aggregation_pipeline(field, is_array=is_array),
    )

    return await cursor.to_list()


def stats_table(title: str, value_heading: str, rows: Sequence[dict]) -> Table:
    """Create a table for aggregated catalog item values."""
    table = Table(
        title=f":: {title.upper()} // {len(rows)} UNIQUE ::",
        title_style="bold bright_magenta",
        border_style="dim magenta",
        header_style="bold bright_cyan",
        box=box.ASCII,
    )

    table.add_column(value_heading.upper(), style="dim white")
    table.add_column("COUNT", justify="right", style="bright_cyan")
    table.add_column("VENDORS")

    for row in rows:
        vendors = Text.assemble(
            *chain.from_iterable(
                (
                    (Text(" // ", style="bold bright_white"), vendor)
                    if index
                    else (vendor,)
                )
                for index, vendor in enumerate(
                    Text(name, style="dim white")
                    for name in sorted(map(str, row["vendors"]))
                )
            )
        )

        table.add_row(
            str(row["_id"]),
            str(row["count"]),
            vendors,
        )

    return table


async def print_catalog_stats() -> None:
    """Print unique catalog values with counts and associated vendors."""
    colors, genders, sizes = await asyncio.gather(
        aggregate("colors", is_array=True),
        aggregate("gender", is_array=False),
        aggregate("all_sizes", is_array=True),
    )

    console = Console()
    console.print(stats_table("Colors", "Color", colors))
    console.print(stats_table("Genders", "Gender", genders))
    console.print(stats_table("All sizes", "Size", sizes))


def main() -> None:
    asyncio.run(print_catalog_stats())


if __name__ == "__main__":
    main()
