from html.parser import HTMLParser
from unicodedata import normalize
from urllib.parse import urljoin


SIZE_GUIDE_TOKENS = {"guia", "guide", "medidas", "size", "talle", "talles"}


def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name: value or "" for name, value in attrs}


def _clean_fragment(value: str) -> str:
    return value if value.startswith("#") else f"#{value}"


def _guide_tokens(value: str) -> set[str]:
    ascii_text = normalize("NFKD", value).encode("ascii", "ignore").decode()

    return set(ascii_text.casefold().replace("-", " ").replace("_", " ").split())


def _is_size_guide(value: str) -> bool:
    return bool(_guide_tokens(value) & SIZE_GUIDE_TOKENS)


class SizeGuideLinkParser(HTMLParser):
    """Extract direct or in-page size-guide URLs from product page HTML."""

    def __init__(self, base_url: str, product_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.product_url = product_url
        self.asset_urls: list[str] = []
        self.page_urls: list[str] = []
        self._modal_depth: int | None = None
        self._modal_id: str | None = None
        self._opener_depth: int | None = None
        self._opener_target: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag_attrs = _attrs(attrs)
        self._advance_depths()
        self._capture_modal(tag, tag_attrs)
        self._capture_opener(tag, tag_attrs)
        self._capture_link(tag, tag_attrs)
        self._capture_image(tag, tag_attrs)

    def handle_endtag(self, tag: str) -> None:
        self._close_modal(tag)
        self._close_opener(tag)

    def url(self) -> str | None:
        urls = tuple(dict.fromkeys((*self.asset_urls, *self.page_urls)))

        return next(iter(urls), None)

    def _advance_depths(self) -> None:
        if self._modal_depth is not None:
            self._modal_depth += 1

        if self._opener_depth is not None:
            self._opener_depth += 1

    def _capture_modal(self, tag: str, attrs: dict[str, str]) -> None:
        element_id = attrs.get("id", "")
        class_text = attrs.get("class", "")
        is_modal = tag in {"dialog", "modal-dialog", "div"}
        if not is_modal:
            return

        if not _is_size_guide(f"{element_id} {class_text}"):
            return

        self._modal_depth = 1
        self._modal_id = element_id or None
        if self._modal_id:
            self._add_page_url(_clean_fragment(self._modal_id))

    def _capture_opener(self, tag: str, attrs: dict[str, str]) -> None:
        target = attrs.get("data-modal", "")
        if tag != "modal-opener" or not target:
            return

        self._opener_depth = 1
        self._opener_target = target

    def _capture_link(self, tag: str, attrs: dict[str, str]) -> None:
        if tag == "link":
            return

        haystack = " ".join(
            attrs.get(name, "")
            for name in (
                "aria-label",
                "class",
                "data-modal",
                "href",
                "id",
                "onclick",
                "title",
            )
        )
        if not _is_size_guide(haystack):
            return

        href = attrs.get("href", "")
        if href:
            self._add_url(href)
            return

        data_modal = attrs.get("data-modal", "")
        if data_modal:
            self._add_page_url(data_modal)
            return

        if self._opener_target:
            self._add_page_url(self._opener_target)
            return

        onclick = attrs.get("onclick", "")
        if "medidas" in onclick.casefold():
            self._add_page_url("#medidas")

    def _capture_image(self, tag: str, attrs: dict[str, str]) -> None:
        if tag != "img":
            return

        haystack = " ".join(
            attrs.get(name, "")
            for name in ("alt", "class", "id", "src", "title")
        )
        if self._modal_depth is None and not _is_size_guide(haystack):
            return

        src = attrs.get("src", "")
        if src:
            self.asset_urls.append(urljoin(self.base_url, src))

    def _close_modal(self, tag: str) -> None:
        if self._modal_depth is None:
            return

        self._modal_depth -= 1
        if self._modal_depth:
            return

        self._modal_depth = None
        self._modal_id = None

    def _close_opener(self, tag: str) -> None:
        if self._opener_depth is None:
            return

        self._opener_depth -= 1
        if self._opener_depth:
            return

        self._opener_depth = None
        self._opener_target = None

    def _add_url(self, url: str) -> None:
        if url.startswith("#"):
            self._add_page_url(url)
            return

        self.asset_urls.append(urljoin(self.base_url, url))

    def _add_page_url(self, fragment: str) -> None:
        self.page_urls.append(f"{self.product_url}{_clean_fragment(fragment)}")
