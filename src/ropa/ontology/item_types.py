from collections.abc import KeysView
from typing import Literal

from pydantic import RootModel

ItemType = Literal[
    "upper_garment",
    "lower_garment",
    "full_body_garment",
    "footwear",
    "underwear",
    "swimwear",
    "accessory",
    "other",
]


class ItemTypeMap(RootModel[dict[ItemType, list[str]]]):
    def __getitem__(self, item_type: ItemType) -> list[str]:
        return self.root[item_type]


ITEM_TYPE_MAP = ItemTypeMap(
    {
        "upper_garment": [
            "abrigo",
            "abrigos",
            "buzo",
            "buzos",
            "buzos y canguros",
            "buzos y sweaters",
            "camisa",
            "camisas",
            "campera",
            "camperas",
            "chaleco",
            "remera",
            "remeras",
            "sweater",
            "sweaters",
            "tops",
        ],
        "lower_garment": [
            "bermuda",
            "bermudas",
            "bermudas, faldas y shorts",
            "denim",
            "faldas y shorts",
            "jean",
            "jeans",
            "pantalones",
            "pantalón",
            "pollera",
            "polleras",
            "shorts",
        ],
        "full_body_garment": [
            "monoprendas y vestidos",
            "vestidos",
        ],
        "footwear": [
            "calzado",
            "dr. martens",
            "salomon",
            "timberland",
            "zapatos",
        ],
        "underwear": [
            "ropa interior",
            "socks",
            "underwear",
        ],
        "swimwear": [
            "short",
            "trajes de baño",
        ],
        "accessory": [
            "accesorio",
            "accesorios",
            "anteojos",
            "billeteras",
            "caps",
            "carteras",
            "carteras y bolsos",
            "cinturones",
            "mochilas y bolsos",
        ],
        "other": [
            "tarjetas de regalo",
        ],
    }
)

INVERTED_ITEM_TYPE_MAP: dict[str, ItemType] = {
    variant: item_type
    for item_type, variants in ITEM_TYPE_MAP.root.items()
    for variant in variants
}


def get_item_type_variants(item_type: ItemType) -> list[str]:
    return ITEM_TYPE_MAP[item_type]


def get_item_types() -> KeysView[ItemType]:
    return ITEM_TYPE_MAP.root.keys()


def get_parent_item_type(variant: str) -> ItemType:
    return INVERTED_ITEM_TYPE_MAP[variant]
