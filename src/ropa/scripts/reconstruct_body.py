import asyncio
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image
from tqdm import tqdm

from ropa.reconstruction import FalBodyReconstructor
from ropa.scripts.console import render_step

BODY_VIEWS = (
    ("01-front.png", "front", 1),
    ("02-side.png", "side", 4),
)
BODIES_DIR = Path("resources/test-bodies")
OUTPUT_DIR = Path("resources/generated/body-reconstructions")
PANEL_NAMES = ("original", "keypoints", "mesh")


def body_directories() -> Iterator[Path]:
    return iter(sorted(path for path in BODIES_DIR.iterdir() if path.is_dir()))


def save_visualization_panel(
    visualization: Image.Image,
    index: int,
    output_path: Path,
) -> Path:
    panel_width = visualization.width // 4
    visualization.crop(
        (
            index * panel_width,
            0,
            (index + 1) * panel_width,
            visualization.height,
        )
    ).save(output_path)

    return output_path


def save_visualization_panels(
    content: bytes,
    view: str,
    first_output_number: int,
    output_directory: Path,
) -> tuple[Path, ...]:
    output_directory.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(content)) as visualization:
        return tuple(
            save_visualization_panel(
                visualization,
                index,
                output_directory
                / f"{first_output_number + index:02d}-{view}-{panel_name}.png",
            )
            for index, panel_name in enumerate(PANEL_NAMES)
        )


async def reconstruct_body() -> tuple[Path, ...]:
    render_step("BODY RECONSTRUCTION", "PROCESSING AVAILABLE BODIES...")
    reconstructor = FalBodyReconstructor()
    async with httpx.AsyncClient(timeout=60) as client:

        async def reconstruct_view(
            body_directory: Path,
            image_name: str,
            view: str,
            first_output_number: int,
        ) -> tuple[Path, ...]:
            reconstruction = await reconstructor.reconstruct(
                body_directory / image_name
            )

            response = await client.get(reconstruction.visualization_url)
            response.raise_for_status()

            return await asyncio.to_thread(
                save_visualization_panels,
                response.content,
                view,
                first_output_number,
                OUTPUT_DIR / body_directory.name,
            )

        async def reconstruct_directory(
            body_directory: Path,
        ) -> tuple[Path, ...]:
            view_output_paths = await asyncio.gather(
                *(
                    reconstruct_view(
                        body_directory,
                        image_name,
                        view,
                        first_output_number,
                    )
                    for image_name, view, first_output_number in BODY_VIEWS
                )
            )

            return tuple(
                output_path
                for output_paths in view_output_paths
                for output_path in output_paths
            )

        tasks = tuple(
            asyncio.create_task(reconstruct_directory(body_directory))
            for body_directory in body_directories()
        )
        body_output_paths = [
            await task
            for task in tqdm(
                asyncio.as_completed(tasks),
                total=len(tasks),
                desc=" :: BODIES",
                unit="body",
                ascii=True,
                dynamic_ncols=True,
            )
        ]

        return tuple(
            output_path
            for output_paths in body_output_paths
            for output_path in output_paths
        )


def main() -> None:
    asyncio.run(reconstruct_body())


if __name__ == "__main__":
    main()
