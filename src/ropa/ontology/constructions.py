from collections.abc import KeysView
from typing import Literal

from pydantic import RootModel

Construction = Literal[
    "knit",
    "denim",
    "gabardine",
    "jersey",
    "poplin",
    "fleece",
    "rib",
    "corduroy",
    "twill",
    "canvas",
    "bengaline",
    "matelasse",
    "flannel",
    "sire",
    "waffle",
    "pique",
    "jacquard",
    "ripstop",
    "ottoman",
    "broadcloth",
    "microfiber",
    "tulle",
]


class ConstructionMap(RootModel[dict[Construction, list[str]]]):
    def __getitem__(self, construction: Construction) -> list[str]:
        return self.root[construction]


CONSTRUCTION_MAP = ConstructionMap(
    {
        "knit": [
            "tejidos",
        ],
        "denim": [
            "denim",
            "jean",
        ],
        "gabardine": [
            "gabardina",
        ],
        "jersey": [
            "jersey",
        ],
        "poplin": [
            "poplin",
            "popelín",
        ],
        "fleece": [
            "frisa",
            "felpa",
        ],
        "rib": [
            "ribb",
            "rib",
        ],
        "corduroy": [
            "corderoy",
        ],
        "twill": [
            "sarga",
        ],
        "canvas": [
            "bull",
        ],
        "bengaline": [
            "bengalina",
        ],
        "matelasse": [
            "matelassé",
            "matelaseado",
        ],
        "flannel": [
            "viyela",
        ],
        "sire": [
            "siré",
        ],
        "waffle": [
            "waffle",
        ],
        "pique": [
            "piqué",
        ],
        "jacquard": [
            "jacquard",
        ],
        "ripstop": [
            "ripstop",
        ],
        "ottoman": [
            "ottoman",
        ],
        "broadcloth": [
            "paño",
        ],
        "microfiber": [
            "microfibra",
        ],
        "tulle": [
            "tul",
            "microtul",
        ],
    }
)

INVERTED_CONSTRUCTION_MAP: dict[str, Construction] = {
    variant: construction
    for construction, variants in CONSTRUCTION_MAP.root.items()
    for variant in variants
}


def get_construction_variants(construction: Construction) -> list[str]:
    return CONSTRUCTION_MAP[construction]


def get_constructions() -> KeysView[Construction]:
    return CONSTRUCTION_MAP.root.keys()


def get_parent_construction(variant: str) -> Construction:
    return INVERTED_CONSTRUCTION_MAP[variant]
