import unittest
from unittest.mock import patch

from pydantic_ai import ModelRetry

from ropa.llm_agents.catalog_filters import validate_catalog_filter
from ropa.llm_agents.tools import search_catalog


class CatalogFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_item_type_is_rejected_before_database_access(self):
        with patch("ropa.llm_agents.tools.get_mongo_connector") as connector:
            with self.assertRaisesRegex(ModelRetry, "lower_garment.*categories"):
                await search_catalog({"item_type": {"$in": ["jean", "jeans", "denim"]}}, 50)

            connector.assert_not_called()

    def test_normalized_values_are_checked_inside_boolean_and_array_operators(self):
        filters = (
            {"$or": [{"gender": "male"}]},
            {"$and": [{"item_type": {"$not": {"$in": ["jeans"]}}}]},
            {"color_family": {"$elemMatch": {"$eq": "negro"}}},
            {"construction_family": {"$all": ["jean"]}},
            {"available_size_family": "XL"},
            {"color_family": {"$in": "black"}},
            {"item_type": {"$regex": "jeans"}},
            {"colour_family": "black"},
            {"$or": []},
        )

        for filter in filters:
            with self.subTest(filter=filter), self.assertRaises(ModelRetry):
                validate_catalog_filter(filter)

    def test_valid_queries_preserve_raw_values_and_measurement_filters(self):
        filters = (
            {},
            {
                "gender": {"$in": ["man", "unisex"]},
                "item_type": "lower_garment",
                "color_family": "black",
                "available_sizes.0": {"$exists": True},
                "available_sizes": {"$in": ["XL", "36"]},
                "$or": [
                    {"categories": {"$in": ["jeans", "denim"]}},
                    {"title": {"$regex": "jeans", "$options": "i"}},
                ],
                "size_guide.XL.cont_cintura.value": {"$gte": 93.5},
                "_id": {"$nin": ["previous-item"]},
            },
            {"construction_family": {"$all": ["denim"]}},
            {"size_guide": None},
        )

        for filter in filters:
            with self.subTest(filter=filter):
                validate_catalog_filter(filter)
