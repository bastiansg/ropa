import asyncio
from collections.abc import Sequence
from itertools import chain

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ropa.db import get_mongo_connector
from ropa.scripts.console import cyberpunk_table, render_values

COLLECTION_NAME = "catalog_items"


def options_pipeline() -> list[dict]:
    return [
        {"$match": {"size_guide": {"$type": "object"}}},
        {
            "$project": {
                "vendor": 1,
                "categories": 1,
                "option": {"$objectToArray": "$size_guide"},
            },
        },
        {"$unwind": "$option"},
        {
            "$group": {
                "_id": "$option.k",
                "count": {"$sum": 1},
                "vendors": {"$addToSet": "$vendor"},
                "categories": {"$addToSet": "$categories"},
            },
        },
        {"$sort": {"count": -1, "_id": 1}},
    ]


async def size_guide_options() -> list[dict]:
    collection = get_mongo_connector().db[COLLECTION_NAME]
    cursor = await collection.aggregate(options_pipeline())

    return await cursor.to_list()


def options_table(rows: Sequence[dict]) -> Table:
    table = cyberpunk_table(
        f":: SIZE GUIDE OPTIONS // {len(rows)} UNIQUE ::"
    )

    table.add_column("SIZE", style="dim white")
    table.add_column("COUNT", justify="right", style="bright_cyan")
    table.add_column("ITEM TYPES")
    table.add_column("VENDORS")

    for row in rows:
        categories = Text(" // ").join(
            Text(name, style="dim white")
            for name in sorted(set(chain.from_iterable(row["categories"])))
        )

        table.add_row(
            str(row["_id"]),
            str(row["count"]),
            categories,
            render_values(sorted(map(str, row["vendors"]))),
        )

    return table


async def print_size_guide_stats() -> None:
    Console().print(options_table(await size_guide_options()))


def main() -> None:
    asyncio.run(print_size_guide_stats())


if __name__ == "__main__":
    main()
