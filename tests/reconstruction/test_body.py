import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from ropa.reconstruction import SAM3D_BODY_MODEL, FalBodyReconstructor


def test_reconstructor_uploads_image_and_maps_fal_result(tmp_path: Path) -> None:
    image = tmp_path / "person.png"
    image.touch()
    client = AsyncMock()
    client.upload_file.return_value = "https://fal.media/person.png"
    client.subscribe.return_value = {
        "meshes": [{"url": "https://fal.media/person.ply"}],
        "visualization": {"url": "https://fal.media/person-result.png"},
        "metadata": {
            "keypoint_names": ["neck", "left-ankle"],
            "people": [{"keypoints_3d": [[0, 0, 1], [0, 0, 0]]}],
        },
    }

    result = asyncio.run(FalBodyReconstructor(client=client).reconstruct(image))

    client.upload_file.assert_awaited_once_with(image)
    client.subscribe.assert_awaited_once_with(
        SAM3D_BODY_MODEL,
        arguments={
            "image_url": "https://fal.media/person.png",
            "export_meshes": True,
            "include_3d_keypoints": False,
            "include_mhr_params": False,
        },
    )
    assert result.mesh_url == "https://fal.media/person.ply"
    assert result.visualization_url == "https://fal.media/person-result.png"
    assert result.keypoints["neck"] == (0, 0, 1)
