import asyncio

from xxhash import xxh3_128_hexdigest

from ropa.collectors import (
    AyNotDeadCollector,
    BoliviaUniversoCollector,
    CatalogCollector,
    CatalogItem,
    RopaRevolverCollector,
)
from ropa.db import get_mongo_connector

COLLECTION_NAME = "catalog_items"


def collectors() -> list[tuple[str, CatalogCollector]]:
    return [
        ("Ay Not Dead", AyNotDeadCollector()),
        ("Bolivia - Divina", BoliviaUniversoCollector()),
        ("Ropa Revolver", RopaRevolverCollector()),
    ]


def document(item: CatalogItem) -> dict:
    doc = item.model_dump(mode="json")
    identity = f"{item.vendor}\0{item.product_id}".encode()
    doc["_id"] = xxh3_128_hexdigest(identity)

    return doc


def document_filter(doc: dict) -> dict:
    return {"_id": doc["_id"]}


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
        await collect_provider(vendor, collector)


async def collect_provider(
    vendor: str,
    collector: CatalogCollector,
) -> None:
    items = await asyncio.to_thread(collector.collect_items)
    count = await store_items(items=items)
    print(f"{vendor}: stored {count} documents")


def main() -> None:
    asyncio.run(collect_data())


if __name__ == "__main__":
    main()
