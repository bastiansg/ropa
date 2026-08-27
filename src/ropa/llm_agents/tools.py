from typing import Annotated, Any

from pydantic import BaseModel, Field, StrictStr
from pydantic_ai import ModelRetry, RunContext, Tool

from ropa.conversions import (
    centimeters_to_eu_footwear_size,
    centimeters_to_us_footwear_size,
)
from ropa.db import get_mongo_connector
from ropa.meta.interfaces.catalog import CatalogItem
from ropa.ontology.colors import Color, get_color_variants, get_colors
from ropa.ontology.constructions import (
    Construction,
    get_construction_variants,
    get_constructions,
)
from ropa.ontology.item_types import (
    ItemType,
    get_item_type_variants,
    get_item_types,
)
from ropa.ontology.materials import (
    Material,
    get_material_variants,
    get_materials,
)
from ropa.ontology.sizes import Size, get_size_variants, get_sizes
from ropa.recommendations import RecommendedItem, store_recommendations

COLLECTION_NAME = "catalog_items"


class RecommendationReference(BaseModel):
    document_id: StrictStr = Field(
        alias="_id",
        description="MongoDB `_id` value of the recommended catalog document.",
    )

    matches: list[StrictStr] = Field(
        description=(
            "Catalog values from the document that match the user's query."
        ),
    )


async def get_catalog_schema() -> dict[str, Any]:
    """Get the schema of catalog items available to search."""

    return CatalogItem.model_json_schema(mode="serialization")


def get_color_parent_values() -> list[Color]:
    return list(get_colors())


def get_construction_parent_values() -> list[Construction]:
    return list(get_constructions())


def get_item_type_parent_values() -> list[ItemType]:
    return list(get_item_types())


def get_material_parent_values() -> list[Material]:
    return list(get_materials())


def get_size_parent_values(item_type: ItemType) -> list[Size]:
    return list(get_sizes(item_type))


async def search_catalog(
    filter: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Query document selecting which documents to include. {} includes "
                "all documents."
            ),
        ),
    ],
    limit: Annotated[
        int,
        Field(
            description=(
                "Maximum number of catalog items to return. 0 applies no limit."
            ),
            default=0,
            le=50,
        ),
    ],
) -> list[dict[str, Any]]:
    """Search the catalog with an arbitrary MongoDB find query.

    Args:
        filter: Query document selecting which documents to include. {} includes all
            documents.
        limit: Maximum number of catalog items to return. 0 applies no limit.
    """

    cursor = get_mongo_connector().find_multiple(
        COLLECTION_NAME,
        filter=filter,
        limit=limit,
    )

    return await cursor.to_list()


async def store_recommended_items(
    ctx: RunContext[Any],
    recommended_items: Annotated[
        list[RecommendationReference],
        Field(description="Recommended documents ordered by relevance."),
    ],
) -> int:
    document_ids = [item.document_id for item in recommended_items]
    documents = (
        await get_mongo_connector()
        .find_multiple(
            COLLECTION_NAME,
            {"_id": {"$in": document_ids}},
        )
        .to_list()
    )

    documents_by_id = {str(document["_id"]): document for document in documents}
    missing_document_ids = [
        document_id
        for document_id in document_ids
        if document_id not in documents_by_id
    ]
    if missing_document_ids:
        raise ValueError(
            "Catalog documents were not found: "
            f"{', '.join(missing_document_ids)}."
        )

    recommendations = [
        RecommendedItem.model_validate(
            {
                **documents_by_id[item.document_id],
                "_id": item.document_id,
                "matches": item.matches,
            }
        )
        for item in recommended_items
    ]

    try:
        return await store_recommendations(
            ctx.deps.request_id,
            ctx.deps.profile_id,
            recommendations,
        )
    except ValueError as error:
        raise ModelRetry(
            f"Recommendation validation failed: {error} "
            "Remove incompatible items and call store_recommended_items again."
        ) from error


get_catalog_schema_tool = Tool(
    function=get_catalog_schema,
    description="Get the schema of catalog items available to search.",
    docstring_format="google",
    require_parameter_descriptions=True,
)

search_catalog_tool = Tool(
    function=search_catalog,
    description="Search the catalog with an arbitrary MongoDB find query.",
    docstring_format="google",
    require_parameter_descriptions=True,
)

store_recommended_items_tool = Tool(
    function=store_recommended_items,
    description=(
        "Store ordered catalog recommendations with the catalog values matching "
        "the user's request."
    ),
    max_retries=3,
)

centimeters_to_eu_footwear_size_tool = Tool(
    function=centimeters_to_eu_footwear_size,
    description="Convert a foot length in centimeters to an EU footwear size.",
)

centimeters_to_us_footwear_size_tool = Tool(
    function=centimeters_to_us_footwear_size,
    description="Convert a foot length in centimeters to a US footwear size.",
)

get_colors_tool = Tool(
    function=get_color_parent_values,
    name="get_colors",
    description="Get all parent color values.",
)

get_color_variants_tool = Tool(
    function=get_color_variants,
    description="Get all variants of a parent color value.",
)

get_constructions_tool = Tool(
    function=get_construction_parent_values,
    name="get_constructions",
    description="Get all parent construction values.",
)

get_construction_variants_tool = Tool(
    function=get_construction_variants,
    description="Get all variants of a parent construction value.",
)

get_item_types_tool = Tool(
    function=get_item_type_parent_values,
    name="get_item_types",
    description="Get all parent item type values.",
)

get_item_type_variants_tool = Tool(
    function=get_item_type_variants,
    description="Get all variants of a parent item type value.",
)

get_materials_tool = Tool(
    function=get_material_parent_values,
    name="get_materials",
    description="Get all parent material values.",
)

get_material_variants_tool = Tool(
    function=get_material_variants,
    description="Get all variants of a parent material value.",
)

get_sizes_tool = Tool(
    function=get_size_parent_values,
    name="get_sizes",
    description="Get all parent size values available for an item type.",
)

get_size_variants_tool = Tool(
    function=get_size_variants,
    description="Get all variants of a parent size value for an item type.",
)

ontology_tools = (
    get_colors_tool,
    get_color_variants_tool,
    get_constructions_tool,
    get_construction_variants_tool,
    get_item_types_tool,
    get_item_type_variants_tool,
    get_materials_tool,
    get_material_variants_tool,
    get_sizes_tool,
    get_size_variants_tool,
)
