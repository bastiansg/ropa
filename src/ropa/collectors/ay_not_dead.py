import asyncio

from itertools import islice
from typing import Literal
from urllib.parse import urljoin
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from pydantic_ai import BinaryContent

from ropa.config import config  # noqa
from ropa.llm_agents import SizeTableExtractor
from ropa.meta.schema import BodyMeasurements
from ropa.meta.interfaces import CatalogItem, ShopifyCollector


type Gender = Literal["man", "woman"]


class _ImageSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_source: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "img" or self.image_source is not None:
            return

        attributes = dict(attrs)
        self.image_source = attributes.get("src")


class AyNotDeadCollector(ShopifyCollector):
    color_option_names = frozenset({"color"})
    size_option_names = frozenset({"talle"})
    size_guide_handles: dict[Gender, str] = {
        "man": "guia-de-talles-hombre",
        "woman": "guia-de-talles-test",
    }

    def __init__(
        self,
        page_size: int = 250,
        timeout_seconds: int = 30,
    ) -> None:
        super().__init__(
            base_url="https://aynotdead.com",
            vendor="Ay Not Dead",
            page_size=page_size,
            timeout_seconds=timeout_seconds,
        )
        self.size_table_extractor = SizeTableExtractor()
        self.body_measurements: dict[Gender, list[BodyMeasurements]] = {}

    def collect_items(self, limit: int | None = None) -> list[CatalogItem]:
        """Collect catalog items and extract the men's and women's size guides."""
        items = list(islice(self.iter_items(), limit))
        self.body_measurements = asyncio.run(self._extract_body_measurements())

        return items

    def size_guide_image_url(self, gender: Gender = "man") -> str:
        """Return the selected gender's size-guide table image URL."""
        handle = self.size_guide_handles[gender]
        response = self._get_json(
            f"/pages/{handle}.json",
            {},
        )

        page = response.get("page") or {}
        parser = _ImageSourceParser()
        parser.feed(str(page.get("body_html") or ""))

        if parser.image_source is None:
            raise ValueError("Ay Not Dead size guide does not contain an image")

        return urljoin(f"{self.base_url}/", parser.image_source)

    async def _extract_body_measurements(
        self,
    ) -> dict[Gender, list[BodyMeasurements]]:
        genders = tuple(self.size_guide_handles)
        measurements = await asyncio.gather(
            *(
                self._extract_gender_body_measurements(gender)
                for gender in genders
            )
        )

        return dict(zip(genders, measurements, strict=True))

    async def _extract_gender_body_measurements(
        self,
        gender: Gender,
    ) -> list[BodyMeasurements]:
        image_url = await asyncio.to_thread(self.size_guide_image_url, gender)
        image_data = await asyncio.to_thread(self._get_bytes, image_url)
        output = await self.size_table_extractor.generate_cached(
            user_prompt=(
                f"Extract every size row from the Ay Not Dead {gender} "
                "size-guide table."
            ),
            user_content=BinaryContent(
                data=image_data,
                media_type="image/jpeg",
            ),
        )

        return output.body_measurements

    def _get_bytes(self, url: str) -> bytes:
        request = Request(url, headers={"Accept": "image/*"})

        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()
