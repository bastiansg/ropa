from pydantic import Field, StrictStr

from ropa.meta.interfaces import CatalogItem


class RecommendedItem(CatalogItem):
    document_id: StrictStr = Field(alias="_id")
    matches: tuple[StrictStr, ...] = Field(
        description=(
            "Matching catalog attributes plus separate short entries naming each "
            "supported measurement match, without numeric comparisons."
        ),
    )
