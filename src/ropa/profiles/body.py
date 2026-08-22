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
    chest_circumference: Measurement | None
    waist_circumference: Measurement | None
    hip_circumference: Measurement | None
    shoulder_width: Measurement | None
    arm_sleeve_length: Measurement | None
    inseam_length: Measurement | None
    foot_length: Measurement | None
    neck_circumference: Measurement | None


class ProfileGenerationError(RuntimeError):
    """Raised when SAM 3D Body does not return usable body geometry."""


class BodyProfileGenerator:
    """Generate height-calibrated measurements from two SAM 3D body meshes."""

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
        """Reconstruct both views and average their independently scaled profiles."""
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
    """Download one PLY body mesh."""
    response = await client.get(url)
    _ = response.raise_for_status()

    return response.content


def load_mesh(content: bytes) -> trimesh.Trimesh:
    """Load a SAM 3D Body PLY response into a triangle mesh."""
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
    """Return one required MHR keypoint as a vector."""
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
    """Return the normalized ankle-to-neck direction of the reconstructed body."""
    ankles = midpoint(point(keypoints, "left-ankle"), point(keypoints, "right-ankle"))
    axis = point(keypoints, "neck") - ankles
    length = np.linalg.norm(axis)
    if length == 0:
        raise ProfileGenerationError("SAM 3D Body returned a degenerate body axis")

    return axis / length


def mesh_scale(mesh: trimesh.Trimesh, axis: Vector, height_cm: float) -> float:
    """Calculate model-unit to centimeter scale along the person's body axis."""
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
    """Return the longest closed mesh cross-section at one body-axis level."""
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


def average_bilateral(left: float, right: float) -> float:
    return (left + right) / 2


def profile_from_reconstruction(
    mesh: trimesh.Trimesh,
    keypoints: dict[str, tuple[float, float, float]],
    height_cm: float,
) -> BodyProfile:
    """Measure a single SAM 3D reconstruction after height calibration."""
    axis = body_axis(keypoints)
    scale = mesh_scale(mesh, axis, height_cm)
    neck = point(keypoints, "neck")
    hips = midpoint(point(keypoints, "left-hip"), point(keypoints, "right-hip"))
    neck_level = float(neck @ axis)
    hip_level = float(hips @ axis)
    torso_height = neck_level - hip_level
    levels = {
        "chest": hip_level + torso_height * 0.68,
        "waist": hip_level + torso_height * 0.3,
        "hip": hip_level,
        "neck": neck_level,
    }
    circumferences = {
        name: section_circumference(mesh, axis, level) for name, level in levels.items()
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
        chest_circumference=measurement(circumferences["chest"], scale),
        waist_circumference=measurement(circumferences["waist"], scale),
        hip_circumference=measurement(circumferences["hip"], scale),
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
        neck_circumference=measurement(circumferences["neck"], scale),
    )


def measurement(value: float | None, scale: float = 1) -> Measurement | None:
    """Scale and round an available measurement for the public profile."""
    return (
        Measurement(value=round(value * scale, 1))
        if value is not None and value > 0
        else None
    )


def average_profiles(
    profiles: tuple[BodyProfile, BodyProfile],
    height_cm: float,
) -> BodyProfile:
    """Average available measurements from the front and side reconstructions."""

    def average(
        selector: Callable[[BodyProfile], Measurement | None],
    ) -> Measurement | None:
        values = tuple(
            item.value
            for profile in profiles
            if (item := selector(profile)) is not None
        )

        return measurement(sum(values) / len(values)) if values else None

    return BodyProfile(
        height=Measurement(value=height_cm),
        chest_circumference=average(lambda profile: profile.chest_circumference),
        waist_circumference=average(lambda profile: profile.waist_circumference),
        hip_circumference=average(lambda profile: profile.hip_circumference),
        shoulder_width=average(lambda profile: profile.shoulder_width),
        arm_sleeve_length=average(lambda profile: profile.arm_sleeve_length),
        inseam_length=average(lambda profile: profile.inseam_length),
        foot_length=average(lambda profile: profile.foot_length),
        neck_circumference=average(lambda profile: profile.neck_circumference),
    )
