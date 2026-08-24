import asyncio
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import PurePosixPath
import re
from typing import Protocol, cast
from urllib.parse import urljoin, urlparse

from aiocache import RedisCache, cached
from aiocache.serializers import JsonSerializer
from aiolimiter import AsyncLimiter
from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.errors import RequestsError
from pydantic_ai import BinaryContent
from pydantic_ai.exceptions import ModelHTTPError
from pymongo.asynchronous.collection import AsyncCollection
from rich.console import Console
from rich.text import Text
from tqdm import tqdm

from ropa.config import config
from ropa.db import get_mongo_connector
from ropa.llm_agents import SizeTableExtractor
from ropa.scripts.console import render_step

COLLECTION_NAME = "catalog_items"
OUTPUT_FIELD = "size_guide"
SUPPORTED_IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
SUPPORTED_IMAGE_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}
NUMBER_PATTERN = re.compile(r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(?:cm)?\s*$")
RANGE_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(?:cm)?\s*"
    r"[-–—]\s*([+-]?\d+(?:[.,]\d+)?)\s*(?:cm)?\s*$"
)

size_table_extractor = SizeTableExtractor()
console = Console(stderr=True)


class SizeGuideImageError(Exception):
    pass


class _CachedFunction(Protocol):
    cache: RedisCache


class SizeGuideImageParser(HTMLParser):

    def __init__(self) -> None:
        super().__init__()
        self.image_url: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "img" or self.image_url is not None:
            return

        tag_attrs = {name: value or "" for name, value in attrs}
        self.image_url = tag_attrs.get("src") or None


def _is_image_url(url: str) -> bool:
    return (
        PurePosixPath(urlparse(url).path).suffix.casefold()
        in SUPPORTED_IMAGE_SUFFIXES
    )


async def _request(
    session: AsyncSession,
    limiter: AsyncLimiter,
    url: str,
    accept: str,
) -> Response:
    async with limiter:
        return await session.get(
            url,
            headers={"Accept": accept},
            timeout=30,
        )


async def _resolve_image_url(
    session: AsyncSession,
    limiter: AsyncLimiter,
    size_guide_url: str,
) -> str:
    if _is_image_url(size_guide_url):
        return size_guide_url

    response = await _request(
        session,
        limiter,
        f"{size_guide_url}.json",
        "application/json",
    )
    if response.status_code >= 400:
        raise SizeGuideImageError(
            f"GET {size_guide_url}.json returned {response.status_code}"
        )

    try:
        body_html = response.json()["page"]["body_html"]
    except (KeyError, TypeError, ValueError) as error:
        raise SizeGuideImageError(
            f"{size_guide_url} returned an invalid page payload"
        ) from error

    parser = SizeGuideImageParser()
    parser.feed(body_html)
    if parser.image_url is None:
        raise SizeGuideImageError(f"{size_guide_url} does not contain an image")

    return urljoin(size_guide_url, parser.image_url)


def _render_detail(label: str, value: object) -> None:
    detail = Text()
    detail.append(" :: ", style="dim magenta")
    detail.append(label, style="bold white")
    detail.append(" // ", style="dim magenta")
    detail.append(str(value), style="dim white")
    console.print(detail)


def _cache_key(
    _function: object,
    _session: AsyncSession,
    _limiter: AsyncLimiter,
    size_guide_url: str,
) -> str:
    return sha256(size_guide_url.encode()).hexdigest()


@cached(
    cache=RedisCache,
    endpoint=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    pool_max_size=32,
    namespace="size_table_extractor",
    ttl=None,
    key_builder=_cache_key,
    serializer=JsonSerializer(),
)
async def extract_size_guide(
    session: AsyncSession,
    limiter: AsyncLimiter,
    size_guide_url: str,
) -> list[dict] | dict:
    image_url = await _resolve_image_url(session, limiter, size_guide_url)
    response = await _request(
        session,
        limiter,
        image_url,
        ",".join(sorted(SUPPORTED_IMAGE_TYPES)),
    )

    if response.status_code >= 400:
        raise SizeGuideImageError(
            f"GET {image_url} returned {response.status_code}"
        )

    media_type = response.headers.get("content-type", "").partition(";")[0]
    if media_type not in SUPPORTED_IMAGE_TYPES:
        raise SizeGuideImageError(
            f"{image_url} returned unsupported content type {media_type or 'unknown'}"
        )

    output = await size_table_extractor.generate_cached(
        user_prompt="Extract the complete clothing size table from this image.",
        user_content=BinaryContent(
            data=response.content,
            media_type=media_type,
        ),
    )

    return output.data


def measurement_value(value: object) -> object:
    if not isinstance(value, str) or not (match := NUMBER_PATTERN.fullmatch(value)):
        return value

    normalized = match.group(1).replace(",", ".")
    if "." in normalized:
        return float(normalized)

    return int(normalized)


def size_guide_measurements(value: object) -> object:
    if isinstance(value, dict):
        if value.get("unit") == "cm" and ({"value", "range"} & value.keys()):
            return value

        return {
            key: size_guide_measurements(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [size_guide_measurements(item) for item in value]

    if isinstance(value, str) and (match := RANGE_PATTERN.fullmatch(value)):
        return {
            "range": [
                measurement_value(match.group(1)),
                measurement_value(match.group(2)),
            ],
            "unit": "cm",
        }

    return {"value": measurement_value(value), "unit": "cm"}


async def normalize_stored_size_guides(collection: AsyncCollection) -> None:
    documents = collection.find(
        {OUTPUT_FIELD: {"$type": "object"}},
        {OUTPUT_FIELD: 1},
    )

    updates = [
        collection.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    OUTPUT_FIELD: size_guide_measurements(document[OUTPUT_FIELD])
                }
            },
        )
        async for document in documents
    ]

    await asyncio.gather(*updates)


async def process_size_guide_url(
    session: AsyncSession,
    limiter: AsyncLimiter,
    collection: AsyncCollection,
    size_guide_url: str,
) -> tuple[int, bool]:
    try:
        size_guide = await extract_size_guide(
            session,
            limiter,
            size_guide_url,
        )
    except ModelHTTPError, RequestsError, SizeGuideImageError:
        return 0, False

    result = await collection.update_many(
        {"size_guide_url": size_guide_url},
        {"$set": {OUTPUT_FIELD: size_guide_measurements(size_guide)}},
    )

    return result.matched_count, True


async def extract_size_guides() -> None:
    render_step("SIZE TABLE EXTRACTOR", "SCANNING STORED CATALOG...")
    mongo_connector = get_mongo_connector()
    collection = mongo_connector.db[COLLECTION_NAME]
    await normalize_stored_size_guides(collection)
    document_filter = {
        "size_guide_url": {"$type": "string", "$ne": ""},
    }
    size_guide_urls = tuple(
        await collection.distinct("size_guide_url", document_filter)
    )
    _render_detail("UNIQUE IMAGE URLS", len(size_guide_urls))
    limiter = AsyncLimiter(1, 1)

    async with AsyncSession(
        impersonate="chrome",
    ) as session:
        extracted = 0
        failed = 0

        with tqdm(
            size_guide_urls,
            desc=" :: SIZE TABLES",
            unit="guide",
            ascii=True,
            dynamic_ncols=True,
        ) as progress:
            for size_guide_url in progress:
                updated, succeeded = await process_size_guide_url(
                    session,
                    limiter,
                    collection,
                    size_guide_url,
                )
                extracted += updated
                failed += not succeeded

    await cast(_CachedFunction, extract_size_guide).cache.close()
    render_step("EXTRACTION COMPLETE", f"{extracted} DOCUMENTS UPDATED")
    _render_detail("SIZE GUIDES FAILED", failed)


def main() -> None:
    asyncio.run(extract_size_guides())


if __name__ == "__main__":
    main()
