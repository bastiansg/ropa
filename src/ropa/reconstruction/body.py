from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import fal_client
from pydantic import BaseModel

SAM3D_BODY_MODEL = "fal-ai/sam-3/3d-body"


class FalAsyncClient(Protocol):
    async def upload_file(self, path: str | Path) -> str: ...

    async def subscribe(
        self,
        application: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]: ...


class BodyReconstruction(BaseModel):
    mesh_url: str
    visualization_url: str
    keypoints: dict[str, tuple[float, float, float]]


class BodyReconstructionError(RuntimeError):
    """Raised when SAM 3D Body does not return usable reconstruction data."""


class BodyReconstructor(Protocol):
    async def reconstruct(self, image: str | Path) -> BodyReconstruction: ...


class FalBodyReconstructor:
    """Reconstruct one person with the fal-hosted Meta SAM 3D Body model."""

    def __init__(self, *, client: FalAsyncClient | None = None) -> None:
        self.client = client or fal_client.AsyncClient()

    async def reconstruct(self, image: str | Path) -> BodyReconstruction:
        """Return the first detected person's mesh, visualization, and keypoints."""
        result = await self.client.subscribe(
            SAM3D_BODY_MODEL,
            arguments={
                "image_url": await self._image_url(image),
                "export_meshes": True,
                "include_3d_keypoints": False,
                "include_mhr_params": False,
            },
        )
        meshes = result.get("meshes", ())
        metadata = result.get("metadata", {})
        people = metadata.get("people", ())
        names = metadata.get("keypoint_names", ())
        visualization = result.get("visualization", {})
        if not meshes or not people:
            raise BodyReconstructionError("SAM 3D Body did not detect a person")

        if not visualization.get("url"):
            raise BodyReconstructionError("SAM 3D Body omitted its visualization")

        coordinates = people[0].get("keypoints_3d", ())
        if len(names) != len(coordinates):
            raise BodyReconstructionError("SAM 3D Body returned invalid 3D keypoints")

        return BodyReconstruction(
            mesh_url=meshes[0]["url"],
            visualization_url=visualization["url"],
            keypoints={
                name: tuple(point)
                for name, point in zip(names, coordinates, strict=True)
            },
        )

    async def _image_url(self, image: str | Path) -> str:
        if isinstance(image, str) and urlparse(image).scheme in {"http", "https"}:
            return image

        path = Path(image)
        if not path.is_file():
            raise FileNotFoundError(path)

        return await self.client.upload_file(path)
