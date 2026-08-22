import asyncio
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image
from rich.console import Console
from rich.text import Text

from ropa.reconstruction import FalBodyReconstructor

BODY_VIEWS = (
    (
        Path("resources/images/test-bodies/test-01/01-front.png"),
        "front",
        1,
    ),
    (
        Path("resources/images/test-bodies/test-01/02-side.png"),
        "side",
        4,
    ),
)
OUTPUT_DIR = Path("resources/generated/body-reconstructions/test-01")
PANEL_NAMES = ("original", "keypoints", "mesh")
console = Console(stderr=True)


def render_step(label: str, action: str) -> None:
    """Render one reconstruction progress step."""
    message = Text()
    message.append("\n┌─[ ", style="dim magenta")
    message.append(label, style="bold white")
    message.append(" ]\n", style="dim magenta")
    message.append("└──> ", style="dim magenta")
    message.append(action, style="dim bright_cyan")
    console.print(message)


def save_visualization_panel(
    visualization: Image.Image,
    index: int,
    output_path: Path,
) -> Path:
    """Save one panel from a SAM 3D Body visualization."""
    panel_width = visualization.width // 4
    visualization.crop(
        (index * panel_width, 0, (index + 1) * panel_width, visualization.height)
    ).save(output_path)

    return output_path


def save_visualization_panels(
    content: bytes,
    view: str,
    first_output_number: int,
) -> tuple[Path, ...]:
    """Save the useful panels from a SAM 3D Body visualization."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(content)) as visualization:
        return tuple(
            save_visualization_panel(
                visualization,
                index,
                OUTPUT_DIR
                / f"{first_output_number + index:02d}-{view}-{panel_name}.png",
            )
            for index, panel_name in enumerate(PANEL_NAMES)
        )


async def reconstruct_test_body() -> tuple[Path, ...]:
    """Reconstruct both views of the hardcoded test body and save their visualizations."""
    reconstructor = FalBodyReconstructor()
    async with httpx.AsyncClient(timeout=60) as client:

        async def reconstruct_view(
            input_path: Path,
            view: str,
            first_output_number: int,
        ) -> tuple[Path, ...]:
            render_step(view.upper(), "RECONSTRUCTING BODY")
            reconstruction = await reconstructor.reconstruct(input_path)

            render_step(view.upper(), "DOWNLOADING VISUALIZATION")
            response = await client.get(reconstruction.visualization_url)
            response.raise_for_status()

            render_step(view.upper(), "SAVING IMAGE PANELS")
            return await asyncio.to_thread(
                save_visualization_panels,
                response.content,
                view,
                first_output_number,
            )

        view_output_paths = await asyncio.gather(
            *(
                reconstruct_view(input_path, view, first_output_number)
                for input_path, view, first_output_number in BODY_VIEWS
            )
        )

        return tuple(
            output_path
            for output_paths in view_output_paths
            for output_path in output_paths
        )


def main() -> None:
    asyncio.run(reconstruct_test_body())
    render_step("OUTPUT", str(OUTPUT_DIR))


if __name__ == "__main__":
    main()
