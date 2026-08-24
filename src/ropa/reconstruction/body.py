from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import fal_client
from aiocache import RedisCache, cached
from aiocache.serializers import PickleSerializer
from pydantic import BaseModel

from ropa.config import config

SAM3D_BODY_MODEL = "fal-ai/sam-3/3d-body"


def _reconstruction_cache_key(
    _function: object,
    _reconstructor: object,
    image: str | Path,
) -> str:
    image_identity = str(image)
    if urlparse(image_identity).scheme in {"http", "https"}:
        return sha256(image_identity.encode()).hexdigest()

    path = Path(image)
    metadata = path.stat()
    image_identity = f"{path.resolve()}:{metadata.st_size}:{metadata.st_mtime_ns}"

    return sha256(image_identity.encode()).hexdigest()


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
    pass


class BodyReconstructor(Protocol):
    async def reconstruct(self, image: str | Path) -> BodyReconstruction: ...


class FalBodyReconstructor:

    def __init__(self, *, client: FalAsyncClient | None = None) -> None:
        self.client = client or fal_client.AsyncClient()

    @cached(
        cache=RedisCache,
        endpoint=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        pool_max_size=32,
        namespace="fal_body_reconstructor",
        ttl=None,
        key_builder=_reconstruction_cache_key,
        serializer=PickleSerializer(),
    )
    async def reconstruct(self, image: str | Path) -> BodyReconstruction:
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
