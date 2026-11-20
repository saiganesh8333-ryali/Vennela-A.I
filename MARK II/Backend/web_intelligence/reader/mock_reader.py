"""Mock page reader for deterministic testing without external network calls."""

from __future__ import annotations

from typing import Mapping
from urllib.parse import urlparse

from .base import PageReader
from ..models import PageContent


class MockPageReader(PageReader):
    """Deterministic page reader returning mock webpage content or configurable errors."""

    reader_name: str = "mock_reader"

    def __init__(
        self,
        pages: Mapping[str, str] | None = None,
        errors: Mapping[str, str] | None = None,
        default_text: str = "This is verified mock page text with deep context regarding the subject matter.",
    ) -> None:
        super().__init__()
        self.pages = dict(pages or {})
        self.errors = dict(errors or {})
        self.default_text = default_text
        self.fetched_urls: list[str] = []

    def fetch_page(self, url: str) -> PageContent:
        self.fetched_urls.append(url)

        if url in self.errors:
            return PageContent(
                url=url,
                title="",
                text_content="",
                status_code=404 if "404" in self.errors[url] else 500,
                success=False,
                error_message=self.errors[url],
            )

        if url in self.pages:
            content = self.pages[url]
            return PageContent(
                url=url,
                title=urlparse(url).netloc,
                text_content=content,
                status_code=200,
                content_length=len(content),
                success=True,
            )

        # Fallback default page content
        return PageContent(
            url=url,
            title=urlparse(url).netloc,
            text_content=self.default_text,
            status_code=200,
            content_length=len(self.default_text),
            success=True,
        )
