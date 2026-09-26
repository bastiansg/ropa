import csv
from collections import deque
from pathlib import Path

import cv2
from joblib import Parallel, cpu_count, delayed
from PIL import Image, ImageDraw, ImageOps
from tqdm import tqdm

from ropa.config import config

OUTPUT_DIRECTORY = "mask_preprocessed"
CONTOUR_TOLERANCE = 20.0
SMOOTHING_SIGMA = 2.0
MIN_HOLE_AREA = 9.0
RENDER_SCALE = 3
BACKGROUND_COLOR = "#000000"
BODY_COLORS = {"male": "#00FFFF", "female": "#FF00FF"}


def preprocess_mask(source: Path, destination: Path, body_color: str) -> int:
    mask = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError(f"Cannot read mask: {source}")

    height, width = mask.shape
    resolution_scale = height / 960
    smoothed = cv2.GaussianBlur(
        mask,
        (0, 0),
        sigmaX=SMOOTHING_SIGMA * resolution_scale,
    )

    _, binary = cv2.threshold(smoothed, 127, 255, cv2.THRESH_BINARY)
    contours, hierarchy = cv2.findContours(
        binary,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if hierarchy is None:
        raise ValueError(f"Mask has no foreground: {source}")

    body_index = max(
        (index for index, entry in enumerate(hierarchy[0]) if entry[3] == -1),
        key=lambda index: cv2.contourArea(contours[index]),
    )

    moments = cv2.moments(contours[body_index])
    if moments["m00"] == 0:
        raise ValueError(f"Mask has no body area: {source}")

    center_x = moments["m10"] / moments["m00"]
    horizontal_offset = (width - 1) / 2 - center_x
    contour_indices = (
        body_index,
        *(
            index
            for index, entry in enumerate(hierarchy[0])
            if entry[3] == body_index
            and cv2.contourArea(contours[index])
            >= MIN_HOLE_AREA * resolution_scale**2
        ),
    )

    image = Image.new(
        "RGB",
        (width * RENDER_SCALE, height * RENDER_SCALE),
        BACKGROUND_COLOR,
    )

    draw = ImageDraw.Draw(image)
    vertex_count = 0
    for index in contour_indices:
        polygon = cv2.approxPolyDP(
            contours[index],
            CONTOUR_TOLERANCE * resolution_scale,
            closed=True,
        )

        if len(polygon) < 3:
            continue

        points = [
            (
                round((int(x) + horizontal_offset) * RENDER_SCALE),
                int(y) * RENDER_SCALE,
            )
            for x, y in polygon.reshape(-1, 2)
        ]

        fill = body_color if index == body_index else BACKGROUND_COLOR
        draw.polygon(points, fill=fill)
        draw.line(
            [*points, points[0]],
            fill=fill,
            width=RENDER_SCALE,
            joint="curve",
        )

        vertex_count += len(points)

    image = image.resize((width, height), Image.Resampling.LANCZOS)
    left_half = image.crop((0, 0, width // 2, height))
    image.paste(ImageOps.mirror(left_half), (width - width // 2, 0))
    image.save(destination)
    return vertex_count


def main() -> None:
    source_directory = config.bodym_train_directory / "mask"
    sources = sorted(source_directory.glob("*.png"))
    if not sources:
        raise FileNotFoundError(f"No front masks found in {source_directory}")

    output_directory = config.bodym_train_directory / OUTPUT_DIRECTORY
    output_directory.mkdir(parents=True, exist_ok=True)
    with (config.bodym_train_directory / "hwg_metadata.csv").open(
        encoding="utf-8",
        newline="",
    ) as metadata_file:
        genders = {
            row["subject_id"]: row["gender"]
            for row in csv.DictReader(metadata_file)
        }

    with (config.bodym_train_directory / "subject_to_photo_map.csv").open(
        encoding="utf-8",
        newline="",
    ) as photo_map_file:
        colors = {
            row["photo_id"]: BODY_COLORS[genders[row["subject_id"]]]
            for row in csv.DictReader(photo_map_file)
        }

    with Parallel(
        n_jobs=min(cpu_count(), len(sources)),
        return_as="generator_unordered",
    ) as parallel:
        results = parallel(
            delayed(preprocess_mask)(
                source,
                output_directory / source.name,
                colors[source.stem],
            )
            for source in sources
        )

        with tqdm(
            results,
            total=len(sources),
            desc=" :: BODY MASKS",
            unit="mask",
            ascii=True,
            colour="#666666",
            ncols=80,
        ) as progress:
            deque(progress, maxlen=0)


if __name__ == "__main__":
    main()
