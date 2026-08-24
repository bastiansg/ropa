import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from io import BytesIO
from itertools import pairwise
from math import dist
from pathlib import Path
from typing import Literal, cast

import httpx
import numpy as np
import trimesh
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from ropa.reconstruction import (
    BodyReconstruction,
    BodyReconstructor,
    FalBodyReconstructor,
)

type MeshFetcher = Callable[[str], Awaitable[bytes]]
type Vector = NDArray[np.float64]
type Vertex = tuple[float, float, float]
type Line = tuple[Vertex, Vertex]


class Measurement(BaseModel):
    value: float = Field(gt=0)
    unit: Literal["cm"] = "cm"


class BodyProfile(BaseModel):
    height: Measurement
    chest_circumference: Measurement
    waist_circumference: Measurement
    hip_circumference: Measurement
    shoulder_width: Measurement | None
    arm_sleeve_length: Measurement | None
    inseam_length: Measurement | None
    foot_length: Measurement | None
    neck_circumference: Measurement


class ProfileGenerationError(RuntimeError):
    pass


class BodyProfileGenerator:

    def __init__(
        self,
        *,
        reconstructor: BodyReconstructor | None = None,
        mesh_fetcher: MeshFetcher | None = None,
    ) -> None:
        self.reconstructor: BodyReconstructor = reconstructor or FalBodyReconstructor()
        self.mesh_fetcher: MeshFetcher | None = mesh_fetcher

    async def generate(
        self,
        front_image: str | Path,
        side_image: str | Path,
        height_cm: float,
    ) -> BodyProfile:
        if height_cm <= 0:
            raise ValueError("height_cm must be greater than zero")

        reconstructions = await asyncio.gather(
            self.reconstructor.reconstruct(front_image),
            self.reconstructor.reconstruct(side_image),
        )
        meshes = await self._meshes(reconstructions)
        profiles = (
            profile_from_reconstruction(
                meshes[0],
                reconstructions[0].keypoints,
                height_cm,
            ),
            profile_from_reconstruction(
                meshes[1],
                reconstructions[1].keypoints,
                height_cm,
            ),
        )

        return average_profiles(profiles, height_cm)

    async def _meshes(
        self,
        reconstructions: tuple[BodyReconstruction, BodyReconstruction],
    ) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
        if self.mesh_fetcher is not None:
            front_content, side_content = await asyncio.gather(
                self.mesh_fetcher(reconstructions[0].mesh_url),
                self.mesh_fetcher(reconstructions[1].mesh_url),
            )

            return load_mesh(front_content), load_mesh(side_content)

        async with httpx.AsyncClient(timeout=60) as client:
            front_content, side_content = await asyncio.gather(
                fetch_mesh(client, reconstructions[0].mesh_url),
                fetch_mesh(client, reconstructions[1].mesh_url),
            )

        return load_mesh(front_content), load_mesh(side_content)


async def fetch_mesh(client: httpx.AsyncClient, url: str) -> bytes:
    response = await client.get(url)
    _ = response.raise_for_status()

    return response.content


def load_mesh(content: bytes) -> trimesh.Trimesh:
    mesh = trimesh.load(  # pyright: ignore[reportUnknownMemberType]
        BytesIO(content),
        file_type="ply",
        force="mesh",
    )
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise ProfileGenerationError("SAM 3D Body returned an empty mesh")

    return mesh


def point(
    keypoints: dict[str, tuple[float, float, float]],
    name: str,
) -> Vector:
    coordinates = keypoints.get(name)
    if coordinates is None:
        raise ProfileGenerationError(f"SAM 3D Body omitted the {name} keypoint")

    return np.asarray(coordinates, dtype=np.float64)


def midpoint(first: Vector, second: Vector) -> Vector:
    return (first + second) / 2


def polyline_length(points: tuple[Vector, ...]) -> float:
    return float(sum(np.linalg.norm(end - start) for start, end in pairwise(points)))


def body_axis(
    keypoints: dict[str, tuple[float, float, float]],
) -> Vector:
    ankles = midpoint(point(keypoints, "left-ankle"), point(keypoints, "right-ankle"))
    axis = point(keypoints, "neck") - ankles
    length = np.linalg.norm(axis)
    if length == 0:
        raise ProfileGenerationError("SAM 3D Body returned a degenerate body axis")

    return axis / length


def mesh_scale(mesh: trimesh.Trimesh, axis: Vector, height_cm: float) -> float:
    projections = np.asarray(cast(object, mesh.vertices), dtype=np.float64) @ axis
    mesh_height = float(np.ptp(projections))
    if mesh_height <= 0:
        raise ProfileGenerationError("SAM 3D Body returned a zero-height mesh")

    return height_cm / mesh_height


def section_circumference(
    mesh: trimesh.Trimesh,
    axis: Vector,
    level: float,
) -> float | None:
    segments = cast(
        NDArray[np.float64],
        trimesh.intersections.mesh_plane(  # pyright: ignore[reportUnknownMemberType]
            mesh,
            plane_normal=axis,
            plane_origin=axis * level,
        ),
    )
    if not len(segments):
        return None

    def vertex(coordinates: Vector) -> Vertex:
        return (
            float(cast(np.float64, coordinates[0])),
            float(cast(np.float64, coordinates[1])),
            float(cast(np.float64, coordinates[2])),
        )

    lines: tuple[Line, ...] = tuple(
        (
            vertex(cast(Vector, segments[index, 0])),
            vertex(cast(Vector, segments[index, 1])),
        )
        for index in range(len(segments))
    )

    def rounded_vertex(coordinates: Vertex) -> Vertex:
        return (
            round(coordinates[0], 8),
            round(coordinates[1], 8),
            round(coordinates[2], 8),
        )

    rounded: tuple[Line, ...] = tuple(
        (rounded_vertex(start), rounded_vertex(end)) for start, end in lines
    )
    endpoints = tuple(vertex for line in rounded for vertex in line)
    parents = {point: point for point in endpoints}

    def root(vertex: tuple[float, float, float]) -> tuple[float, float, float]:
        while parents[vertex] != vertex:
            parents[vertex] = parents[parents[vertex]]
            vertex = parents[vertex]

        return vertex

    for start, end in rounded:
        start_root = root(start)
        end_root = root(end)
        if start_root != end_root:
            parents[end_root] = start_root

    lengths: defaultdict[tuple[float, float, float], float] = defaultdict(float)
    for original, rounded_segment in zip(lines, rounded, strict=True):
        lengths[root(rounded_segment[0])] += dist(*original)

    return max(lengths.values(), default=None)


def mapped_mesh_levels(
    mesh: trimesh.Trimesh,
    keypoints: dict[str, tuple[float, float, float]],
    axis: Vector,
    levels: dict[str, float],
) -> tuple[dict[str, float], float]:
    mesh_projections = (
        np.asarray(cast(object, mesh.vertices), dtype=np.float64) @ axis
    )

    keypoint_projections = np.asarray(
        [
            np.asarray(coordinates, dtype=np.float64) @ axis
            for coordinates in keypoints.values()
        ],
        dtype=np.float64,
    )

    mesh_min = float(mesh_projections.min())
    mesh_max = float(mesh_projections.max())
    keypoint_min = float(keypoint_projections.min())
    keypoint_max = float(keypoint_projections.max())
    mesh_height = mesh_max - mesh_min
    keypoint_height = keypoint_max - keypoint_min
    if mesh_height <= 0 or keypoint_height <= 0:
        raise ProfileGenerationError("SAM 3D Body returned degenerate geometry")

    return (
        {
            name: mesh_min
            + (level - keypoint_min) / keypoint_height * mesh_height
            for name, level in levels.items()
        },
        mesh_height,
    )


def circumference_measurement(
    mesh: trimesh.Trimesh,
    axis: Vector,
    level: float,
    window: float,
    scale: float,
    name: str,
    *,
    minimum: bool,
) -> Measurement:
    circumferences = tuple(
        circumference
        for sample_level in np.linspace(level - window, level + window, 17)
        if (circumference := section_circumference(mesh, axis, sample_level))
        is not None
        and circumference > 0
    )
    if not circumferences:
        raise ProfileGenerationError(f"Could not measure {name} circumference")

    circumference = min(circumferences) if minimum else max(circumferences)

    return Measurement(value=round(circumference * scale, 1))


def average_bilateral(left: float, right: float) -> float:
    return (left + right) / 2


def profile_from_reconstruction(
    mesh: trimesh.Trimesh,
    keypoints: dict[str, tuple[float, float, float]],
    height_cm: float,
) -> BodyProfile:
    axis = body_axis(keypoints)
    scale = mesh_scale(mesh, axis, height_cm)
    neck = point(keypoints, "neck")
    hips = midpoint(point(keypoints, "left-hip"), point(keypoints, "right-hip"))
    neck_level = float(neck @ axis)
    hip_level = float(hips @ axis)
    torso_height = neck_level - hip_level
    keypoint_levels = {
        "chest": hip_level + torso_height * 0.68,
        "waist": hip_level + torso_height * 0.3,
        "hip": hip_level,
        "neck": neck_level,
    }
    levels, mesh_height = mapped_mesh_levels(
        mesh,
        keypoints,
        axis,
        keypoint_levels,
    )

    window = mesh_height * 0.025
    circumferences = {
        name: circumference_measurement(
            mesh,
            axis,
            level,
            window,
            scale,
            name,
            minimum=name in {"waist", "neck"},
        )
        for name, level in levels.items()
    }
    left_arm = polyline_length(
        (
            point(keypoints, "left-acromion"),
            point(keypoints, "left-elbow"),
            point(keypoints, "left-wrist"),
        )
    )
    right_arm = polyline_length(
        (
            point(keypoints, "right-acromion"),
            point(keypoints, "right-elbow"),
            point(keypoints, "right-wrist"),
        )
    )
    left_inseam = polyline_length(
        (
            hips,
            point(keypoints, "left-knee"),
            point(keypoints, "left-ankle"),
        )
    )
    right_inseam = polyline_length(
        (
            hips,
            point(keypoints, "right-knee"),
            point(keypoints, "right-ankle"),
        )
    )
    left_foot = max(
        np.linalg.norm(point(keypoints, name) - point(keypoints, "left-heel"))
        for name in ("left-big-toe-tip", "left-small-toe-tip")
    )
    right_foot = max(
        np.linalg.norm(point(keypoints, name) - point(keypoints, "right-heel"))
        for name in ("right-big-toe-tip", "right-small-toe-tip")
    )
    shoulder_width = np.linalg.norm(
        point(keypoints, "left-acromion") - point(keypoints, "right-acromion")
    )

    return BodyProfile(
        height=Measurement(value=height_cm),
        chest_circumference=circumferences["chest"],
        waist_circumference=circumferences["waist"],
        hip_circumference=circumferences["hip"],
        shoulder_width=measurement(float(shoulder_width), scale),
        arm_sleeve_length=measurement(
            average_bilateral(left_arm, right_arm),
            scale,
        ),
        inseam_length=measurement(
            average_bilateral(left_inseam, right_inseam),
            scale,
        ),
        foot_length=measurement(
            average_bilateral(float(left_foot), float(right_foot)),
            scale,
        ),
        neck_circumference=circumferences["neck"],
    )


def measurement(value: float | None, scale: float = 1) -> Measurement | None:
    return (
        Measurement(value=round(value * scale, 1))
        if value is not None and value > 0
        else None
    )


def average_profiles(
    profiles: tuple[BodyProfile, BodyProfile],
    height_cm: float,
) -> BodyProfile:

    def average(
        selector: Callable[[BodyProfile], Measurement | None],
    ) -> Measurement | None:
        values = tuple(
            item.value
            for profile in profiles
            if (item := selector(profile)) is not None
        )

        return measurement(sum(values) / len(values)) if values else None

    def average_required(
        selector: Callable[[BodyProfile], Measurement],
    ) -> Measurement:
        values = tuple(selector(profile).value for profile in profiles)

        return Measurement(value=round(sum(values) / len(values), 1))

    return BodyProfile(
        height=Measurement(value=height_cm),
        chest_circumference=average_required(
            lambda profile: profile.chest_circumference
        ),
        waist_circumference=average_required(
            lambda profile: profile.waist_circumference
        ),
        hip_circumference=average_required(lambda profile: profile.hip_circumference),
        shoulder_width=average(lambda profile: profile.shoulder_width),
        arm_sleeve_length=average(lambda profile: profile.arm_sleeve_length),
        inseam_length=average(lambda profile: profile.inseam_length),
        foot_length=average(lambda profile: profile.foot_length),
        neck_circumference=average_required(
            lambda profile: profile.neck_circumference
        ),
    )
