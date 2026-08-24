import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from tqdm import tqdm

from ropa.db import get_mongo_connector
from ropa.profiles import BodyProfile, BodyProfileGenerator, Measurement
from ropa.scripts.console import render_step

COLLECTION_NAME = "profiles"
BODIES_DIR = Path("resources/test-bodies")


class BodyMetadata(BaseModel):
    height: Measurement
    gender: Literal["female", "male"]


def body_directories() -> Iterator[Path]:
    return iter(sorted(path for path in BODIES_DIR.iterdir() if path.is_dir()))


async def generate_profile(
    generator: BodyProfileGenerator,
    body_directory: Path,
) -> tuple[str, BodyMetadata, BodyProfile]:
    metadata = BodyMetadata.model_validate_json(
        (body_directory / "metadata.json").read_text()
    )

    return body_directory.name, metadata, await generator.generate(
        body_directory / "01-front.png",
        body_directory / "02-side.png",
        metadata.height.value,
    )


async def generate_body_profiles() -> int:
    render_step("BODY PROFILES", "GENERATING AND STORING AVAILABLE BODIES...")
    generator = BodyProfileGenerator()
    mongo_connector = get_mongo_connector()

    async def generate_and_store(body_directory: Path) -> str:
        body_name, metadata, profile = await generate_profile(generator, body_directory)
        await mongo_connector.upsert_doc(
            COLLECTION_NAME,
            {"_id": body_name},
            {
                "_id": body_name,
                "gender": metadata.gender,
                **profile.model_dump(mode="json"),
            },
        )

        return body_name

    tasks = tuple(
        asyncio.create_task(generate_and_store(body_directory))
        for body_directory in body_directories()
    )
    stored_profiles = [
        await task
        for task in tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=" :: PROFILES",
            unit="profile",
            ascii=True,
            dynamic_ncols=True,
        )
    ]

    return len(stored_profiles)


def main() -> None:
    asyncio.run(generate_body_profiles())


if __name__ == "__main__":
    main()
