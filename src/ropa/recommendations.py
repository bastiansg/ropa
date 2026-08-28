import asyncio

from aiocache import RedisCache
from aiocache.serializers import JsonSerializer
from pydantic import Field, StrictStr

from ropa.config import config
from ropa.db import get_mongo_connector
from ropa.meta.interfaces import CatalogItem

RECOMMENDATION_TTL_SECONDS = 900
PROFILE_COLLECTION_NAME = "profiles"
GENDER_ALIASES = {
    "female": "woman",
    "male": "man",
}


class RecommendedItem(CatalogItem):
    document_id: StrictStr = Field(alias="_id")
    matches: tuple[StrictStr, ...]


cache = RedisCache(
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    namespace="recommendations",
    serializer=JsonSerializer(),
)


async def store_recommendations(
    request_id: str,
    profile_id: str,
    recommendations: list[RecommendedItem],
) -> int:
    stored_recommendations = await cache.get(request_id, default=[])
    if stored_recommendations:
        return len(stored_recommendations)

    await asyncio.gather(
        *(
            validate_recommended_item(profile_id, recommendation)
            for recommendation in recommendations
        )
    )

    await cache.set(
        request_id,
        [
            recommendation.model_dump(mode="json", by_alias=True)
            for recommendation in recommendations
        ],
        ttl=RECOMMENDATION_TTL_SECONDS,
    )

    return len(recommendations)


async def validate_recommended_item(
    profile_id: str,
    recommended_item: RecommendedItem,
) -> None:
    profile = await get_mongo_connector().find(
        PROFILE_COLLECTION_NAME,
        {"_id": profile_id},
        projection={"gender": True},
    )
    if profile is None:
        raise ValueError(f"Profile {profile_id!r} was not found.")

    stored_profile_gender = str(profile["gender"])
    profile_gender = GENDER_ALIASES.get(
        stored_profile_gender,
        stored_profile_gender,
    )

    if recommended_item.gender not in {profile_gender, "unisex"}:
        raise ValueError(
            f"Catalog item {recommended_item.document_id!r} has gender "
            f"{recommended_item.gender!r}, but profile {profile_id!r} has gender "
            f"{stored_profile_gender!r}."
        )


async def get_recommendations(request_id: str) -> list[RecommendedItem]:
    recommendations = await cache.get(request_id, default=[])

    return [
        RecommendedItem.model_validate(recommendation)
        for recommendation in recommendations  # type: ignore
    ]
