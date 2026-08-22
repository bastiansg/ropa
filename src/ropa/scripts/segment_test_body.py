import asyncio
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from ropa.segmentation import BodyPartSegmentation, BodyPartSegmenter

INPUT_PATH = Path("resources/images/test-bodies/test-01/01-front.png")
OUTPUT_PATH = Path("resources/generated/body-segments/test-01-front.png")
OVERLAY_ALPHA = 144
PART_COLORS = (
    (239, 71, 111),
    (255, 159, 28),
    (255, 209, 102),
    (6, 214, 160),
    (17, 138, 178),
    (7, 59, 76),
    (131, 56, 236),
    (247, 37, 133),
    (67, 97, 238),
    (76, 201, 240),
    (114, 9, 183),
    (58, 134, 255),
    (128, 237, 153),
    (255, 89, 94),
    (106, 76, 147),
)


async def download_mask(
    client: httpx.AsyncClient,
    segmentation: BodyPartSegmentation,
) -> tuple[str, Image.Image] | None:
    """Download the first mask produced for one body part."""
    if not segmentation.masks:
        return None

    response = await client.get(segmentation.masks[0].url)
    response.raise_for_status()

    return segmentation.prompt, Image.open(BytesIO(response.content)).copy()


def mask_alpha(mask: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Convert a SAM mask into a translucent alpha channel."""
    resized = mask.resize(size, Image.Resampling.NEAREST)
    alpha = resized.getchannel("A") if "A" in resized.getbands() else resized.convert("L")
    if alpha.getextrema() == (255, 255):
        alpha = resized.convert("L")

    return alpha.point(lambda value: OVERLAY_ALPHA if value > 127 else 0)


def draw_segments(
    image: Image.Image,
    masks: tuple[tuple[str, Image.Image] | None, ...],
) -> Image.Image:
    """Overlay every detected body part with its assigned color."""
    result = image.convert("RGBA")
    for downloaded_mask, color in zip(masks, PART_COLORS, strict=True):
        if downloaded_mask is None:
            continue

        _, mask = downloaded_mask
        overlay = Image.new("RGBA", result.size, (*color, 0))
        overlay.putalpha(mask_alpha(mask, result.size))
        result = Image.alpha_composite(result, overlay)

    return result


async def segment_test_body() -> Path:
    """Segment the hardcoded test body and save its colored visualization."""
    segmentations = await BodyPartSegmenter().segment(INPUT_PATH)
    async with httpx.AsyncClient(timeout=30) as client:
        masks = tuple(
            await asyncio.gather(
                *(download_mask(client, segmentation) for segmentation in segmentations)
            )
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(INPUT_PATH) as image:
        draw_segments(image, masks).convert("RGB").save(OUTPUT_PATH)

    return OUTPUT_PATH


def main() -> None:
    output_path = asyncio.run(segment_test_body())
    print(f"Segmented image written to {output_path}")


if __name__ == "__main__":
    main()
