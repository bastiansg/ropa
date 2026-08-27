from bisect import bisect_left
from typing import Literal

from ropa.ontology.sizes import Size

EU_FOOTWEAR_SIZES: tuple[tuple[float, Size], ...] = (
    (22.1, "eu_36"),
    (22.9, "eu_37"),
    (23.3, "eu_38"),
    (24.2, "eu_39"),
    (24.6, "eu_40"),
    (25.5, "eu_41"),
    (25.9, "eu_42"),
    (26.7, "eu_43"),
    (27.1, "eu_44"),
    (27.6, "eu_44.5"),
    (27.8, "eu_45"),
    (28.0, "eu_45.5"),
    (28.4, "eu_46"),
)
EU_FOOT_LENGTHS = tuple(length for length, _ in EU_FOOTWEAR_SIZES)

US_FOOTWEAR_SIZES: dict[
    Literal["man", "woman"],
    tuple[tuple[float, Size], ...],
] = {
    "man": (
        (24.2, "us_6.5"),
        (24.6, "us_7"),
        (25.0, "us_7.5"),
        (25.5, "us_8"),
        (25.9, "us_8.5"),
        (26.3, "us_9"),
        (26.7, "us_9.5"),
        (27.1, "us_10"),
        (27.6, "us_10.5"),
        (28.0, "us_11"),
        (28.4, "us_11.5"),
    ),
    "woman": (
        (23.3, "us_6.5"),
        (23.8, "us_7"),
        (24.2, "us_7.5"),
        (24.6, "us_8"),
        (25.0, "us_8.5"),
        (25.5, "us_9"),
        (25.9, "us_9.5"),
        (26.3, "us_10"),
        (26.7, "us_10.5"),
        (27.1, "us_11"),
        (27.6, "us_11.5"),
    ),
}
US_FOOT_LENGTHS = {
    gender: tuple(length for length, _ in sizes)
    for gender, sizes in US_FOOTWEAR_SIZES.items()
}


def centimeters_to_eu_footwear_size(centimeters: float) -> Size:
    if not EU_FOOTWEAR_SIZES[0][0] <= centimeters <= EU_FOOTWEAR_SIZES[-1][0]:
        raise ValueError(f"Unsupported foot length: {centimeters} cm")

    index = bisect_left(
        EU_FOOT_LENGTHS,
        centimeters,
    )

    return EU_FOOTWEAR_SIZES[index][1]


def centimeters_to_us_footwear_size(
    centimeters: float,
    gender: Literal["man", "woman"],
) -> Size:
    sizes = US_FOOTWEAR_SIZES[gender]

    if not sizes[0][0] <= centimeters <= sizes[-1][0]:
        raise ValueError(f"Unsupported {gender} foot length: {centimeters} cm")

    index = bisect_left(
        US_FOOT_LENGTHS[gender],
        centimeters,
    )

    return sizes[index][1]
