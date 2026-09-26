from typing import Annotated, Any, Literal
from uuid import uuid4

from aiocache import RedisCache
from aiocache.serializers import JsonSerializer
from pydantic import BaseModel, Field
from pydantic_ai import ModelRetry, RunContext, Tool

from ropa.config import config
from ropa.db import get_mongo_connector
from ropa.llm_agents.agent_deps import AssistantDeps
from ropa.llm_agents.tools import COLLECTION_NAME, search_catalog

cache = RedisCache(
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    namespace="retrieved_items",
    serializer=JsonSerializer(),
)
RETRIEVAL_TTL_SECONDS = 900


class RetrievalOutput(BaseModel):
    status: Literal["available_in_redis"] = "available_in_redis"
    search_id: str
    item_count: int


async def search_items(
    ctx: RunContext[AssistantDeps],
    filter: Annotated[dict[str, Any], Field(description="MongoDB catalog query.")],
    limit: Annotated[int, Field(ge=1, le=50, description="Maximum number of items to inspect.")] = 50,
) -> list[dict[str, Any]]:
    items = await search_catalog(filter, limit)
    ctx.deps.retrieved_items.update((str(item["_id"]), item) for item in items)
    return items


async def finish_search(
    ctx: RunContext[AssistantDeps],
    document_ids: Annotated[list[str], Field(description="IDs of suitable items from this run, ranked by relevance; empty if none qualify.")],
) -> RetrievalOutput:
    if any(document_id not in ctx.deps.retrieved_items for document_id in document_ids):
        raise ModelRetry("Select only IDs returned by search_catalog during this retrieval run.")

    selected_ids = list(dict.fromkeys(document_ids))
    search_id = f"{ctx.deps.request_id}:{uuid4()}"
    await cache.set(search_id, selected_ids, ttl=RETRIEVAL_TTL_SECONDS)
    ctx.deps.retrieval_keys.add(search_id)
    return RetrievalOutput(search_id=search_id, item_count=len(selected_ids))


async def read_retrieved_items(
    ctx: RunContext[AssistantDeps],
    search_id: Annotated[str, Field(description="Search ID returned by the retriever for this request.")],
) -> list[dict[str, Any]]:
    if search_id not in ctx.deps.retrieval_keys:
        raise ModelRetry("Use a search_id returned by the retriever for the current request.")

    document_ids = await cache.get(search_id)
    if document_ids is None:
        raise ModelRetry("The retrieved items have expired. Delegate a new search.")

    if not document_ids:
        return []

    items = await get_mongo_connector().find_multiple(
        COLLECTION_NAME,
        filter={"_id": {"$in": document_ids}},
    ).to_list()

    items_by_id = {str(item["_id"]): item for item in items}
    if any(document_id not in items_by_id for document_id in document_ids):
        raise ModelRetry("Some selected items no longer exist in the catalog. Delegate a new search.")

    return [items_by_id[document_id] for document_id in document_ids]


search_items_tool = Tool(search_items, name="search_catalog")
read_retrieved_items_tool = Tool(read_retrieved_items)
