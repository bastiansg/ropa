import asyncio

from ropa.collectors import (
    AyNotDeadCollector,
    CatalogCollector,
    CatalogItem,
)
from ropa.db import get_mongo_connector

COLLECTION_NAME = "catalog_items"


def collectors() -> list[tuple[str, CatalogCollector]]:
    return [
        ("Ay Not Dead", AyNotDeadCollector()),
    ]


def document(item: CatalogItem) -> dict:
    return item.model_dump(mode="json")


def document_filter(doc: dict) -> dict:
    return {"_id": doc["product_id"]}


async def store_items(items: list[CatalogItem]) -> int:
    mongo_connector = get_mongo_connector()
    docs = [document(item) for item in items]
    vendors = tuple(dict.fromkeys(item.vendor for item in items))

    await asyncio.gather(
        *(
            mongo_connector.delete_docs(
                COLLECTION_NAME,
                {"vendor": vendor},
            )
            for vendor in vendors
        )
    )

    await asyncio.gather(
        *(
            mongo_connector.upsert_doc(
                COLLECTION_NAME,
                document_filter(doc),
                doc,
            )
            for doc in docs
        )
    )

    return len(docs)


async def collect_data() -> None:
    for vendor, collector in collectors():
        items = await asyncio.to_thread(collector.collect_items)
        count = await store_items(items=items)
        print(f"{vendor}: stored {count} documents")


def main() -> None:
    asyncio.run(collect_data())


if __name__ == "__main__":
    main()
