"""Page Reader ABC contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import PageContent


class PageReader(ABC):
    """Abstract interface for fetching and extracting readable text from web pages."""

    reader_name: str = "base"

    def __init__(self, timeout: float = 10.0, max_bytes: int = 250_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    @abstractmethod
    def fetch_page(self, url: str) -> PageContent:
        """Fetch URL content and extract clean, readable text."""
        raise NotImplementedError
