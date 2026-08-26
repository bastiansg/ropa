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
    pass


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
