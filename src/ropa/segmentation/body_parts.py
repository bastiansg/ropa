import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import fal_client
from pydantic import BaseModel, ConfigDict, Field

SAM3_IMAGE_MODEL = "fal-ai/sam-3/image"
BODY_PART_PROMPTS = (
    "head",
    "neck",
    "torso",
    "person's left upper arm",
    "person's right upper arm",
    "person's left forearm",
    "person's right forearm",
    "person's left hand",
    "person's right hand",
    "person's left thigh",
    "person's right thigh",
    "person's left lower leg",
    "person's right lower leg",
    "person's left foot",
    "person's right foot",
)


class FalAsyncClient(Protocol):
    async def upload_file(self, path: str | Path) -> str: ...

    async def subscribe(
        self,
        application: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]: ...


class MaskImage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    content_type: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None


class BodyPartSegmentation(BaseModel):
    prompt: str
    masks: tuple[MaskImage, ...] = Field(default_factory=tuple)
    scores: tuple[float, ...] = Field(default_factory=tuple)
    boxes: tuple[tuple[float, ...], ...] = Field(default_factory=tuple)


class BodyPartSegmenter:
    """Segment anatomical regions from a person's image with Meta SAM 3."""

    def __init__(
        self,
        *,
        client: FalAsyncClient | None = None,
        max_concurrency: int = 4,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")

        self.client = client or fal_client.AsyncClient()
        self.max_concurrency = max_concurrency

    async def segment(
        self,
        image: str | Path,
        *,
        body_parts: Sequence[str] = BODY_PART_PROMPTS,
    ) -> tuple[BodyPartSegmentation, ...]:
        """Return one independently generated mask result per requested body part."""
        image_url = await self._image_url(image)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        return tuple(
            await asyncio.gather(
                *(
                    self._segment_part(image_url, part, semaphore)
                    for part in body_parts
                )
            )
        )

    async def _image_url(self, image: str | Path) -> str:
        if isinstance(image, str) and urlparse(image).scheme in {"http", "https"}:
            return image

        path = Path(image)
        if not path.is_file():
            raise FileNotFoundError(path)

        return await self.client.upload_file(path)

    async def _segment_part(
        self,
        image_url: str,
        prompt: str,
        semaphore: asyncio.Semaphore,
    ) -> BodyPartSegmentation:
        async with semaphore:
            result = await self.client.subscribe(
                SAM3_IMAGE_MODEL,
                arguments={
                    "image_url": image_url,
                    "prompt": prompt,
                    "apply_mask": False,
                    "output_format": "png",
                    "return_multiple_masks": False,
                    "include_scores": True,
                    "include_boxes": True,
                },
            )

        return BodyPartSegmentation(
            prompt=prompt,
            masks=tuple(
                MaskImage.model_validate(mask) for mask in result.get("masks", ())
            ),
            scores=tuple(result.get("scores", ())),
            boxes=tuple(tuple(box) for box in result.get("boxes", ())),
        )
