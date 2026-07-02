import asyncio

from tqdm import tqdm
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
        ("Bolivia Universo", BoliviaUniversoCollector()),
        ("Ropa Revolver", RopaRevolverCollector()),
    ]


def document(item: CatalogItem) -> dict:
    return item.model_dump(mode="json")


def document_filter(doc: dict) -> dict:
    return {
        "vendor": doc["vendor"],
        "product_id": doc["product_id"],
        "category": doc["category"],
        "color": doc["color"],
    }


async def store_items(items: list[CatalogItem]) -> int:
    mongo_connector = get_mongo_connector()
    docs = [document(item) for item in items]

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


def collect_data() -> None:
    collector_items = (
        (name, collector.collect_items())
        for name, collector in tqdm(
            collectors(),
            ascii=True,
        )
    )

    for vendor, items in collector_items:
        count = asyncio.run(store_items(items=items))
        print(f"{vendor}: stored {count} documents")


def main() -> None:
    collect_data()


if __name__ == "__main__":
    main()
