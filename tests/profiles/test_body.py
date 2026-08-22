import asyncio

import numpy as np
import pytest
import trimesh

from ropa.profiles.body import BodyProfileGenerator
from ropa.reconstruction import BodyReconstruction


def keypoints() -> dict[str, tuple[float, float, float]]:
    return {
        "neck": (0, 0, 8),
        "left-acromion": (-2, 0, 7.5),
        "right-acromion": (2, 0, 7.5),
        "left-elbow": (-2, 0, 5.5),
        "right-elbow": (2, 0, 5.5),
        "left-wrist": (-2, 0, 3.5),
        "right-wrist": (2, 0, 3.5),
        "left-hip": (-1, 0, 4),
        "right-hip": (1, 0, 4),
        "left-knee": (-1, 0, 2),
        "right-knee": (1, 0, 2),
        "left-ankle": (-1, 0, 0.5),
        "right-ankle": (1, 0, 0.5),
        "left-big-toe-tip": (-1, -1.5, 0),
        "left-small-toe-tip": (-0.8, -1.4, 0),
        "left-heel": (-1, 0.5, 0),
        "right-big-toe-tip": (1, -1.5, 0),
        "right-small-toe-tip": (0.8, -1.4, 0),
        "right-heel": (1, 0.5, 0),
    }


class FakeReconstructor:
    async def reconstruct(self, image: str) -> BodyReconstruction:
        return BodyReconstruction(
            mesh_url=f"{image}.ply",
            visualization_url=f"{image}.png",
            keypoints=keypoints(),
        )


def test_generator_measures_and_averages_height_scaled_meshes() -> None:
    mesh = trimesh.creation.cylinder(radius=2, height=10, sections=64)
    mesh.apply_translation((0, 0, 5))
    mesh_content = mesh.export(file_type="ply")

    async def fetch_mesh(url: str) -> bytes:
        assert url in {"front.ply", "side.ply"}

        return mesh_content

    profile = asyncio.run(
        BodyProfileGenerator(
            reconstructor=FakeReconstructor(),
            mesh_fetcher=fetch_mesh,
        ).generate("front", "side", 180)
    )

    assert profile.height.value == 180
    assert profile.chest_circumference is not None
    assert profile.chest_circumference.value == pytest.approx(226.1, abs=0.1)
    assert profile.waist_circumference is not None
    assert profile.waist_circumference.value == profile.chest_circumference.value
    assert profile.shoulder_width is not None
    assert profile.shoulder_width.value == 72
    assert profile.arm_sleeve_length is not None
    assert profile.arm_sleeve_length.value == 72
    assert profile.inseam_length is not None
    assert profile.inseam_length.value == pytest.approx(67.2, abs=0.1)
    assert profile.foot_length is not None
    assert profile.foot_length.value == pytest.approx(36, abs=0.1)
    assert profile.neck_circumference is not None
    assert np.isfinite(profile.neck_circumference.value)
