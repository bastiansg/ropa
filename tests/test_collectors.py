from collections.abc import Iterable, Iterator
from itertools import islice
from typing import Literal

from pydantic_ai import BinaryContent
from rich.table import Table
from rich.console import Console

from ropa.collectors import (
    AyNotDeadCollector,
    BoliviaUniversoCollector,
    CatalogItem,
    RopaRevolverCollector,
)
from ropa.llm_agents import SizeTableExtractorOutput
from ropa.meta.schema import BodyMeasurements


PRINT_LIMIT = 5
MINIMUM_COLLECTED_ITEMS = 10


def item_row(item: CatalogItem) -> tuple[str, ...]:
    values = (
        getattr(item, field_name)
        for field_name in CatalogItem.model_fields
    )

    return tuple(format_value(value) for value in values)


def format_value(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, tuple):
        return "\n".join(str(item) for item in value)

    return str(value)


def catalog_table(
    title: str, items: Iterable[CatalogItem], limit: int
) -> Table:
    table = Table(title=f"{title}: first {limit} catalog results")
    for field_name in CatalogItem.model_fields:
        table.add_column(field_name.replace("_", " ").title(), overflow="fold")

    for row in map(item_row, items):
        table.add_row(*row)

    return table


def body_measurements_table(
    title: str,
    gender: str,
    measurements: Iterable[BodyMeasurements],
) -> Table:
    table = Table(title=f"{title}: {gender.title()} body measurements")
    for field_name in BodyMeasurements.model_fields:
        table.add_column(field_name.replace("_", " ").title())

    rows = (
        tuple(
            format_value(getattr(measurement, field_name))
            for field_name in BodyMeasurements.model_fields
        )
        for measurement in measurements
    )
    for row in rows:
        table.add_row(*row)

    return table


def assert_collector_returns_minimum_items(
    collector_name: str, items: tuple[CatalogItem, ...]
) -> None:
    Console().print(
        catalog_table(
            collector_name,
            islice(items, PRINT_LIMIT),
            PRINT_LIMIT,
        )
    )

    assert len(items) >= MINIMUM_COLLECTED_ITEMS


def test_ay_not_dead_collector_returns_catalog_items() -> None:
    collector = AyNotDeadCollector()
    items = tuple(collector.collect_items(limit=MINIMUM_COLLECTED_ITEMS))

    console = Console()
    for gender, measurements in collector.body_measurements.items():
        console.print(
            body_measurements_table("Ay Not Dead", gender, measurements)
        )

    assert_collector_returns_minimum_items("Ay Not Dead", items)


def test_ay_not_dead_collector_extracts_gender_size_guide_image_urls() -> None:
    class FixtureAyNotDeadCollector(AyNotDeadCollector):
        def _get_json(
            self, path: str, params: dict[str, int | str]
        ) -> dict[str, object]:
            return {
                "page": {
                    "body_html": (
                        f'<div><img src="/cdn/shop/files/{path.split("/")[-1]}.jpg">'
                        "</div>"
                    ),
                },
            }

    collector = FixtureAyNotDeadCollector()

    assert collector.size_guide_image_url() == (
        "https://aynotdead.com/cdn/shop/files/"
        "guia-de-talles-hombre.json.jpg"
    )
    assert collector.size_guide_image_url("woman") == (
        "https://aynotdead.com/cdn/shop/files/"
        "guia-de-talles-test.json.jpg"
    )


def test_ay_not_dead_collector_extracts_size_guides_when_collecting() -> None:
    class FixtureSizeTableExtractor:
        async def generate_cached(
            self,
            user_prompt: str,
            user_content: BinaryContent,
        ) -> SizeTableExtractorOutput:
            size_label = "M" if "woman" in user_prompt else "S"

            return SizeTableExtractorOutput(
                body_measurements=[
                    BodyMeasurements(
                        size_label=size_label,
                        chest_circumference=90,
                        waist_circumference=70,
                        hip_circumference=95,
                    ),
                ],
            )

    class FixtureAyNotDeadCollector(AyNotDeadCollector):
        def iter_items(self) -> Iterator[CatalogItem]:
            return iter(())

        def size_guide_image_url(
            self, gender: Literal["man", "woman"] = "man"
        ) -> str:
            return f"https://example.com/{gender}.jpg"

        def _get_bytes(self, url: str) -> bytes:
            return b"image"

    collector = FixtureAyNotDeadCollector()
    collector.size_table_extractor = FixtureSizeTableExtractor()

    assert collector.collect_items() == []
    assert collector.body_measurements == {
        "man": [
            BodyMeasurements(
                size_label="S",
                chest_circumference=90,
                waist_circumference=70,
                hip_circumference=95,
            ),
        ],
        "woman": [
            BodyMeasurements(
                size_label="M",
                chest_circumference=90,
                waist_circumference=70,
                hip_circumference=95,
            ),
        ],
    }


def test_bolivia_universo_collector_returns_catalog_items() -> None:
    collector = BoliviaUniversoCollector(
        listing_urls=("lo-nuevo/",),
        max_pages_per_listing=0,
    )
    items = tuple(
        islice(collector.iter_items(), MINIMUM_COLLECTED_ITEMS)
    )

    assert_collector_returns_minimum_items("Bolivia Universo", items)


def test_ropa_revolver_collector_returns_catalog_items() -> None:
    collector = RopaRevolverCollector()
    items = tuple(
        islice(collector.iter_items(), MINIMUM_COLLECTED_ITEMS)
    )

    assert_collector_returns_minimum_items("Ropa Revolver", items)
