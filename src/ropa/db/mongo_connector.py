from functools import lru_cache

from pymongo import AsyncMongoClient
from pymongo.results import DeleteResult
from pymongo.asynchronous.cursor import AsyncCursor

from ropa.config import config


class MongoConnector:
    def __init__(self):
        self.client = AsyncMongoClient(config.mongodb_dsn)
        self.db = self.client[config.mongodb_db_name]

    async def insert_doc(self, doc: dict, collection: str) -> None:
        await self.db[collection].insert_one(doc)

    async def insert_docs(self, docs: list[dict], collection: str) -> None:
        await self.db[collection].insert_many(docs)

    async def upsert_doc(
        self,
        collection: str,
        filter: dict,
        update: dict,
    ) -> None:
        await self.db[collection].update_one(
            filter,
            {"$set": update},
            upsert=True,
        )

    async def find(
        self,
        collection: str,
        filter: dict = {},
        fields: dict = {},
    ) -> dict | None:
        return await self.db[collection].find_one(filter, fields)

    def find_multiple(
        self,
        collection: str,
        filter: dict = {},
    ) -> AsyncCursor[dict]:
        return self.db[collection].find(filter)

    async def create_index(self, collection: str, key: str) -> None:
        await self.db[collection].create_index(key)

    async def delete_doc(
        self,
        collection: str,
        query: dict = {},
    ) -> DeleteResult:
        return await self.db[collection].delete_one(query)

    async def delete_docs(
        self,
        collection: str,
        query: dict = {},
    ) -> DeleteResult:
        return await self.db[collection].delete_many(query)

    async def ensure_index(self, collection_name: str, field_name: str) -> None:
        collection = self.db[collection_name]
        indexes = await collection.index_information()

        index_name = f"{field_name}_index"
        if index_name in indexes:
            return

        await collection.create_index(
            [(field_name, 1)],
            name=index_name,
        )


@lru_cache()
def get_mongo_connector() -> MongoConnector:
    return MongoConnector()
