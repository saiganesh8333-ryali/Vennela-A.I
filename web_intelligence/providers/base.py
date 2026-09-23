"""Search Provider ABC contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from ..models import SearchResult


class SearchProvider(ABC):
    """Abstract base interface for search engines and web search providers."""

    provider_name: str = "base"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> Sequence[SearchResult]:
        """Execute search for a query and return structured search results."""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Returns True if the provider is properly configured."""
        return bool(self.api_key)
