import asyncio

from aiocache import RedisCache
from aiocache.serializers import JsonSerializer
from pydantic import Field, StrictStr

from ropa.config import config
from ropa.db import get_mongo_connector
from ropa.meta.interfaces import CatalogItem


class RecommendedItem(CatalogItem):
    document_id: StrictStr = Field(alias="_id")
    matches: tuple[StrictStr, ...]


cache = RedisCache(
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    namespace=config.recommendations_cache_namespace,
    serializer=JsonSerializer(),
)


async def store_recommendations(
    request_id: str,
    profile_gender: str,
    recommendations: list[RecommendedItem],
) -> int:
    stored_recommendations = await cache.get(request_id, default=[])
    if stored_recommendations:
        return len(stored_recommendations)

    await asyncio.gather(
        *(
            validate_recommended_item(profile_gender, recommendation)
            for recommendation in recommendations
        )
    )

    await cache.set(
        request_id,
        [
            recommendation.model_dump(mode="json", by_alias=True)
            for recommendation in recommendations
        ],
        ttl=config.recommendations_ttl_seconds,
    )

    return len(recommendations)


async def validate_recommended_item(
    profile_gender: str,
    recommended_item: RecommendedItem,
) -> None:
    if recommended_item.gender not in {profile_gender, "unisex"}:
        raise ValueError(
            f"Catalog item {recommended_item.document_id!r} has gender "
            f"{recommended_item.gender!r}, but the profile has gender "
            f"{profile_gender!r}."
        )


async def get_profile_gender(profile_id: str) -> str:
    profile = await get_mongo_connector().find(
        config.profile_collection_name,
        {"_id": profile_id},
        projection={"gender": True},
    )
    if profile is None:
        raise ValueError(f"Profile {profile_id!r} was not found.")

    stored_profile_gender = str(profile["gender"])
    profile_gender = config.gender_aliases.get(
        stored_profile_gender,
        stored_profile_gender,
    )

    return profile_gender


async def get_recommendations(request_id: str) -> list[RecommendedItem]:
    recommendations = await cache.get(request_id, default=[])

    return [
        RecommendedItem.model_validate(recommendation)
        for recommendation in recommendations  # type: ignore
    ]
