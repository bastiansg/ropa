from collections.abc import KeysView
from typing import Literal

from pydantic import RootModel

Material = Literal[
    "cotton",
    "linen",
    "wool",
    "llama_wool",
    "cashmere",
    "mohair",
    "leather",
    "viscose",
    "rayon",
    "modal",
    "lyocell",
    "polyester",
    "recycled_polyester",
    "polyamide",
    "acrylic",
    "elastane",
    "metallic_fiber",
    "polyurethane",
    "rubber",
    "silicone",
    "acetate",
    "metal",
    "aluminum",
    "steel",
    "zinc_alloy",
    "plastic",
]


class MaterialMap(RootModel[dict[Material, list[str]]]):
    def __getitem__(self, material: Material) -> list[str]:
        return self.root[material]


MATERIAL_MAP = MaterialMap(
    {
        "cotton": [
            "algodón",
            "algodon",
            "algodón ecológico",
            "algodón orgánico",
            "algodón peinado",
            "algodón pima",
        ],
        "linen": [
            "lino",
        ],
        "wool": [
            "lana",
            "lana merino",
            "lana ultra fina",
        ],
        "llama_wool": [
            "lana de llama",
        ],
        "cashmere": [
            "cashmere",
        ],
        "mohair": [
            "mohair",
        ],
        "leather": [
            "cuero",
            "cuero natural",
            "cuero vacuno",
            "cuero de cabra",
            "cuero de oveja",
            "gamuza vacuna",
            "gamuza de cabra",
            "suede",
        ],
        "viscose": [
            "viscosa",
        ],
        "rayon": [
            "rayón",
            "rayon",
        ],
        "modal": [
            "modal",
        ],
        "lyocell": [
            "tencel",
        ],
        "polyester": [
            "poliéster",
            "poliester",
        ],
        "recycled_polyester": [
            "poliéster reciclado",
            "poliester reciclado",
        ],
        "polyamide": [
            "poliamida",
            "nylon",
        ],
        "acrylic": [
            "acrílico",
            "acrilico",
        ],
        "elastane": [
            "elastano",
            "spandex",
            "lycra",
        ],
        "metallic_fiber": [
            "lurex",
        ],
        "polyurethane": [
            "PU",
            "poliuretano",
        ],
        "rubber": [
            "caucho",
            "goma",
        ],
        "silicone": [
            "silicona",
        ],
        "acetate": [
            "acetato",
        ],
        "metal": [
            "metal",
            "metálico",
            "metalico",
        ],
        "aluminum": [
            "aluminio",
        ],
        "steel": [
            "acero",
        ],
        "zinc_alloy": [
            "aleación de zinc",
            "aleacion de zinc",
        ],
        "plastic": [
            "plástico",
            "plastico",
        ],
    }
)

INVERTED_MATERIAL_MAP: dict[str, Material] = {
    variant: material
    for material, variants in MATERIAL_MAP.root.items()
    for variant in variants
}


def get_material_variants(material: Material) -> list[str]:
    return MATERIAL_MAP[material]


def get_materials() -> KeysView[Material]:
    return MATERIAL_MAP.root.keys()


def get_parent_material(variant: str) -> Material:
    return INVERTED_MATERIAL_MAP[variant]
