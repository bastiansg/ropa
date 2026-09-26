from typing import Any, get_args

from pydantic_ai import ModelRetry

from ropa.meta.interfaces.catalog import CatalogItem
from ropa.ontology.colors import Color
from ropa.ontology.constructions import Construction
from ropa.ontology.item_types import ItemType
from ropa.ontology.materials import Material
from ropa.ontology.sizes import Size

CATALOG_FIELDS = {"_id", *CatalogItem.model_fields, *CatalogItem.model_computed_fields}
NORMALIZED_VALUES = {
    "gender": {"man", "woman", "unisex"},
    "item_type": set(get_args(ItemType)),
    "color_family": set(get_args(Color)),
    "construction_family": set(get_args(Construction)),
    "material_family": set(get_args(Material)),
    "all_size_family": set(get_args(Size)),
    "available_size_family": set(get_args(Size)),
}
FIELD_HINTS = {
    "gender": "Use man, woman, or unisex.",
    "item_type": "Use parent types such as lower_garment; match jeans in categories or text, and denim in construction_family.",
    "color_family": "Use get_colors for parent values; match vendor color variants in colors.",
    "construction_family": "Use get_constructions for parent values; match variants in categories or text.",
    "material_family": "Use get_materials for parent values; match variants in description or title.",
    "all_size_family": "Use get_sizes for normalized values; match vendor labels in all_sizes.",
    "available_size_family": "Use get_sizes for normalized values; match vendor labels in available_sizes.",
}


def validate_normalized_value(field: str, condition: Any) -> None:
    if isinstance(condition, dict):
        for operator, value in condition.items():
            if operator in {"$exists", "$size", "$type"}:
                continue

            if operator not in {"$eq", "$ne", "$in", "$nin", "$all", "$not", "$elemMatch"}:
                raise ModelRetry(f"Unsupported operator {operator!r} for {field}. Use exact ontology values. {FIELD_HINTS[field]}")

            if operator in {"$in", "$nin", "$all"} and not isinstance(value, list):
                raise ModelRetry(f"{operator} requires a list of values for {field}.")

            validate_normalized_value(field, value)

        return

    if isinstance(condition, list):
        for value in condition:
            validate_normalized_value(field, value)

        return

    if condition is not None and (
        not isinstance(condition, str) or condition not in NORMALIZED_VALUES[field]
    ):
        raise ModelRetry(f"Invalid value {condition!r} for {field}. {FIELD_HINTS[field]}")


def validate_catalog_filter(filter: dict[str, Any]) -> None:
    for field, condition in filter.items():
        if field in {"$and", "$or", "$nor"}:
            if not isinstance(condition, list) or not condition:
                raise ModelRetry(f"{field} requires a nonempty list of query documents.")

            for clause in condition:
                if not isinstance(clause, dict):
                    raise ModelRetry(f"Each {field} clause must be a query document.")

                validate_catalog_filter(clause)

            continue

        root = field.split(".", 1)[0]
        if root not in CATALOG_FIELDS:
            raise ModelRetry(f"Unknown catalog field {field!r}. Use the supplied catalog schema; combine clauses with $and, $or, or $nor.")

        if root in NORMALIZED_VALUES:
            validate_normalized_value(root, condition)
