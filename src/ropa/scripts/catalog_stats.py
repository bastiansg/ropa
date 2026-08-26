import asyncio
from collections.abc import Sequence

from rich.console import Console
from rich.table import Table

from ropa.db import get_mongo_connector
from ropa.scripts.console import cyberpunk_table, render_values

COLLECTION_NAME = "catalog_items"


def aggregation_pipeline(field: str, *, is_array: bool) -> list[dict]:
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
    collection = get_mongo_connector().db[COLLECTION_NAME]
    cursor = await collection.aggregate(
        aggregation_pipeline(field, is_array=is_array),
    )

    return await cursor.to_list()


def stats_table(title: str, value_heading: str, rows: Sequence[dict]) -> Table:
    table = cyberpunk_table(f":: {title.upper()} // {len(rows)} UNIQUE ::")

    table.add_column(value_heading.upper(), style="dim white")
    table.add_column("COUNT", justify="right", style="bright_cyan")
    table.add_column("VENDORS")

    for row in rows:
        table.add_row(
            str(row["_id"]),
            str(row["count"]),
            render_values(sorted(map(str, row["vendors"]))),
        )

    return table


async def print_catalog_stats() -> None:
    categories, colors, genders, sizes, size_guide_urls = await asyncio.gather(
        aggregate("categories", is_array=True),
        aggregate("colors", is_array=True),
        aggregate("gender", is_array=False),
        aggregate("all_sizes", is_array=True),
        aggregate("size_guide_url", is_array=False),
    )

    console = Console()
    console.print(stats_table("Categories", "Category", categories))
    console.print(stats_table("Colors", "Color", colors))
    console.print(stats_table("Genders", "Gender", genders))
    console.print(stats_table("All sizes", "Size", sizes))
    console.print(f"Unique size guide URLs: {len(size_guide_urls)}")


def main() -> None:
    asyncio.run(print_catalog_stats())


if __name__ == "__main__":
    main()
