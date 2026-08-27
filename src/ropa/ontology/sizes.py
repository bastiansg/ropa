from collections.abc import KeysView
from typing import Literal

from pydantic import RootModel

from ropa.ontology.item_types import ItemType

Size = Literal[
    "one_size",
    "extra_small",
    "small",
    "medium",
    "large",
    "extra_large",
    "double_extra_large",
    "triple_extra_large",
    "quadruple_extra_large",
    "22",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "36",
    "38",
    "40",
    "42",
    "44",
    "eu_36",
    "eu_37",
    "eu_38",
    "eu_39",
    "eu_40",
    "eu_41",
    "eu_42",
    "eu_43",
    "eu_44",
    "eu_44.5",
    "eu_45",
    "eu_45.5",
    "eu_46",
    "uk_4",
    "uk_5",
    "us_6.5",
    "us_7",
    "us_7.5",
    "us_8",
    "us_8.5",
    "us_9",
    "us_9.5",
    "us_10",
    "us_10.5",
    "us_11",
    "us_11.5",
    "belt_95_cm",
    "belt_100_cm",
    "belt_105_cm",
    "belt_110_cm",
    "belt_115_cm",
]


class SizeMap(RootModel[dict[ItemType, dict[Size, list[str]]]]):
    def __getitem__(self, item_type: ItemType) -> dict[Size, list[str]]:
        return self.root[item_type]


SIZE_MAP = SizeMap(
    {
        "upper_garment": {
            "extra_small": [
                "XS",
            ],
            "small": [
                "S",
                "SM",
                "1",
            ],
            "medium": [
                "M",
                "ME",
                "2",
            ],
            "large": [
                "L",
                "LA",
                "3",
            ],
            "extra_large": [
                "XL",
            ],
            "double_extra_large": [
                "XXL",
                "XX",
            ],
            "triple_extra_large": [
                "3XL",
                "3X",
            ],
            "quadruple_extra_large": [
                "4XL",
            ],
        },
        "lower_garment": {
            "extra_small": [
                "XS",
            ],
            "small": [
                "S",
                "SM",
                "1",
            ],
            "medium": [
                "M",
                "ME",
                "2",
            ],
            "large": [
                "L",
                "LA",
                "3",
            ],
            "extra_large": [
                "XL",
            ],
            "double_extra_large": [
                "XXL",
                "XX",
            ],
            "triple_extra_large": [
                "3XL",
                "3X",
            ],
            "22": [
                "22",
            ],
            "24": [
                "24",
            ],
            "25": [
                "25",
            ],
            "26": [
                "26",
            ],
            "27": [
                "27",
            ],
            "28": [
                "28",
            ],
            "29": [
                "29",
            ],
            "30": [
                "30",
            ],
            "31": [
                "31",
            ],
            "32": [
                "32",
            ],
            "33": [
                "33",
            ],
            "34": [
                "34",
            ],
            "36": [
                "36",
            ],
            "38": [
                "38",
            ],
            "40": [
                "40",
            ],
            "42": [
                "42",
            ],
            "44": [
                "44",
            ],
        },
        "full_body_garment": {
            "extra_small": [
                "XS",
            ],
            "small": [
                "S",
                "SM",
            ],
            "medium": [
                "M",
                "ME",
            ],
            "large": [
                "L",
                "LA",
            ],
            "extra_large": [
                "XL",
            ],
            "double_extra_large": [
                "XX",
            ],
        },
        "footwear": {
            "eu_36": [
                "36",
            ],
            "eu_37": [
                "37",
            ],
            "eu_38": [
                "38",
            ],
            "eu_39": [
                "39",
            ],
            "eu_40": [
                "40",
            ],
            "eu_41": [
                "41",
            ],
            "eu_42": [
                "42",
            ],
            "eu_43": [
                "43",
            ],
            "eu_44": [
                "44",
            ],
            "eu_44.5": [
                "44.5",
            ],
            "eu_45": [
                "45",
            ],
            "eu_45.5": [
                "455",
            ],
            "eu_46": [
                "46",
            ],
            "uk_4": [
                "4",
            ],
            "uk_5": [
                "5",
            ],
            "us_6.5": [
                "6.5 US",
            ],
            "us_7": [
                "7",
                "7 US",
            ],
            "us_7.5": [
                "7.5",
                "7.5 US",
            ],
            "us_8": [
                "8",
                "8 US",
            ],
            "us_8.5": [
                "8.5",
                "8.5 US",
            ],
            "us_9": [
                "9",
                "9 US",
            ],
            "us_9.5": [
                "9.5",
                "9.5 US",
            ],
            "us_10": [
                "10",
                "10 US",
            ],
            "us_10.5": [
                "10.5",
                "10.5 US",
            ],
            "us_11": [
                "11",
                "11 US",
            ],
            "us_11.5": [
                "11.5",
            ],
        },
        "underwear": {
            "one_size": [
                "ONE SIZE",
            ],
            "small": [
                "S",
            ],
            "medium": [
                "M",
            ],
            "large": [
                "L",
            ],
            "extra_large": [
                "XL",
            ],
            "double_extra_large": [
                "XXL",
            ],
        },
        "swimwear": {
            "small": [
                "S",
                "SM",
            ],
            "medium": [
                "M",
                "ME",
            ],
            "large": [
                "L",
                "LA",
            ],
            "extra_large": [
                "XL",
            ],
            "double_extra_large": [
                "XXL",
                "XX",
            ],
        },
        "accessory": {
            "one_size": [
                "ONE SIZE",
            ],
            "small": [
                "S",
                "SM",
            ],
            "medium": [
                "M",
                "ME",
            ],
            "large": [
                "L",
                "LA",
            ],
            "extra_large": [
                "XL",
            ],
            "double_extra_large": [
                "XX",
            ],
            "belt_95_cm": [
                "95",
            ],
            "belt_100_cm": [
                "1",
                "100",
                "1 (100cm)",
            ],
            "belt_105_cm": [
                "105",
            ],
            "belt_110_cm": [
                "110",
            ],
            "belt_115_cm": [
                "2",
                "115",
                "2 (115cm)",
            ],
        },
    }
)

INVERTED_SIZE_MAP: dict[ItemType, dict[str, Size]] = {
    item_type: {
        variant: size
        for size, variants in sizes.items()
        for variant in variants
    }
    for item_type, sizes in SIZE_MAP.root.items()
}
def get_size_variants(item_type: ItemType, size: Size) -> list[str]:
    sizes = SIZE_MAP[item_type]
    if size not in sizes:
        raise ValueError(
            f"Size {size!r} is not available for item type {item_type!r}. "
            f"Available sizes: {', '.join(sizes)}."
        )

    return sizes[size]


def get_sizes(item_type: ItemType) -> KeysView[Size]:
    return SIZE_MAP[item_type].keys()


def get_parent_size(item_type: ItemType, variant: str) -> Size:
    return INVERTED_SIZE_MAP[item_type][variant]
