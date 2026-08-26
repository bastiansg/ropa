from typing import Literal

from pydantic import RootModel

Color = Literal[
    "black",
    "white",
    "gray",
    "blue",
    "green",
    "red",
    "pink",
    "purple",
    "yellow",
    "orange",
    "brown",
    "metallic",
    "transparent",
    "multicolor",
]


class ColorMap(RootModel[dict[Color, list[str]]]):
    def __getitem__(self, color: Color) -> list[str]:
        return self.root[color]


COLOR_MAP = ColorMap({
    "black": [
        "negro",
        "negrido",
        "worn black",
        "black",
        "negro brillante",
        "negro mate",
        "negro melange",
        "washed black",
    ],
    "white": [
        "blanco",
        "crudo",
        "coco",
        "off white",
        "crema",
        "white",
        "manteca",
    ],
    "gray": [
        "gris",
        "gris mel",
        "gris claro",
        "gris medio",
        "gris melange",
        "dark gray",
        "gray",
        "cemento",
        "charcoal gray",
        "gris negro",
        "gris perla",
        "gris plutonio",
        "light grey",
    ],
    "blue": [
        "azul",
        "celeste",
        "marino",
        "blue",
        "light blue",
        "dark blue",
        "aero",
        "azul gant",
        "azul oscuro",
        "vintage blue",
        "celeste jack",
        "marino navy",
        "deep blue",
        "azul claro",
        "celeste claro",
        "denin",
        "oiled blue",
        "pure blue",
        "rinsed",
        "turquesa",
        "azul francia",
        "azul marino",
        "francia blue",
        "grit blue",
        "mid stone",
        "navy blue",
        "navy",
        "petroleo",
        "turquoise",
        "zafiro",
    ],
    "green": [
        "verde militar",
        "verde seco",
        "verde oliva",
        "verde ingles",
        "verde jungla",
        "verde malba",
        "verde oscuro",
        "verde pistachio",
        "army",
        "oliva",
        "verde",
        "verde brillante",
        "verde limon",
        "verde pasto",
        "verde perico",
    ],
    "red": [
        "rojo",
        "bordeaux",
        "bordo",
        "bordo oscuro",
        "rojo torino",
        "red",
        "rojo tomate",
        "borgona",
        "borravino",
        "viñedo",
    ],
    "pink": [
        "rosa",
        "salmon",
    ],
    "purple": [
        "violeta",
        "lila",
    ],
    "yellow": [
        "amarillo",
    ],
    "orange": [
        "naranja",
        "naranja fanta",
        "terra",
        "ladrillo",
        "talampaya",
        "naranja rock",
    ],
    "brown": [
        "tostado",
        "chocolate",
        "marron",
        "marrón",
        "marrón claro",
        "beige",
        "camel",
        "bamby",
        "cappuchino",
        "arena",
    ],
    "metallic": [
        "dorado",
        "plateado",
        "cobre",
        "plata",
        "holographic silver",
        "espejado",
    ],
    "transparent": [
        "translucido",
    ],
    "multicolor": [
        "rayas",
        "cuadros",
        "combinado",
        "leopardo",
        "estampado",
        "camuflado",
        "camo",
        "green and yellow",
        "snake",
        "blue and black",
        "lunar chico",
        "multicolor",
        "rayado",
        "zebra",
    ],
})

INVERTED_COLOR_MAP: dict[str, Color] = {
    variant: color
    for color, variants in COLOR_MAP.root.items()
    for variant in variants
}


def get_color_variants(color: Color) -> list[str]:
    return COLOR_MAP[color]


def get_parent_color(variant: str) -> Color:
    return INVERTED_COLOR_MAP[variant]
