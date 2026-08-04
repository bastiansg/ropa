import asyncio
from collections.abc import Sequence

from rich import box
from rich.console import Console
from rich.table import Table

from ropa.db import get_mongo_connector

COLLECTION_NAME = "catalog_items"


def aggregation_pipeline(field: str, *, is_array: bool) -> list[dict]:
    """Build a pipeline that counts field values by vendor."""
    values = f"${field}" if is_array else [f"${field}"]

    return [
        {"$project": {"vendor": 1, "value": values}},
        {"$unwind": "$value"},
        {"$match": {"value": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": {"vendor": "$vendor", "value": "$value"},
                "count": {"$sum": 1},
            },
        },
        {"$sort": {"_id.vendor": 1, "count": -1, "_id.value": 1}},
    ]


async def aggregate(field: str, *, is_array: bool) -> list[dict]:
    """Return counts for a catalog item field grouped by vendor."""
    collection = get_mongo_connector().db[COLLECTION_NAME]
    cursor = await collection.aggregate(
        aggregation_pipeline(field, is_array=is_array),
    )

    return await cursor.to_list()


def stats_table(title: str, value_heading: str, rows: Sequence[dict]) -> Table:
    """Create a table for aggregated catalog item values."""
    table = Table(
        title=f":: {title.upper()} ::",
        title_style="bold bright_magenta",
        border_style="dim magenta",
        header_style="bold bright_cyan",
        box=box.ASCII,
    )

    table.add_column("VENDOR", style="bold white")
    table.add_column(value_heading.upper(), style="dim white")
    table.add_column("ITEMS", justify="right", style="bright_cyan")

    for row in rows:
        table.add_row(
            str(row["_id"]["vendor"]),
            str(row["_id"]["value"]),
            str(row["count"]),
        )

    return table


async def print_catalog_stats() -> None:
    """Print catalog option counts aggregated by vendor."""
    colors, genders, sizes = await asyncio.gather(
        aggregate("colors", is_array=True),
        aggregate("gender", is_array=False),
        aggregate("all_sizes", is_array=True),
    )

    console = Console()
    console.print(stats_table("Colors by vendor", "Color", colors))
    console.print(stats_table("Gender by vendor", "Gender", genders))
    console.print(stats_table("All sizes by vendor", "Size", sizes))


def main() -> None:
    asyncio.run(print_catalog_stats())


if __name__ == "__main__":
    main()
