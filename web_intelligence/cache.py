"""Lightweight in-memory TTL caching for search queries and retrieved web pages."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Generic, Sequence, TypeVar

from .models import PageContent, SearchResult

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    data: T
    expires_at: float


class ResearchCache:
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, default_ttl_seconds: float = 600.0) -> None:
        self.default_ttl = default_ttl_seconds
        self._search_store: dict[str, CacheEntry[list[SearchResult]]] = {}
        self._page_store: dict[str, CacheEntry[PageContent]] = {}
        self._lock = threading.Lock()

    def get_search(self, query: str) -> list[SearchResult] | None:
        key = query.strip().lower()
        now = time.perf_counter()
        with self._lock:
            entry = self._search_store.get(key)
            if entry is None:
                return None
            if entry.expires_at < now:
                del self._search_store[key]
                return None
            return list(entry.data)

    def set_search(self, query: str, results: Sequence[SearchResult], ttl: float | None = None) -> None:
        key = query.strip().lower()
        expires_at = time.perf_counter() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._search_store[key] = CacheEntry(data=list(results), expires_at=expires_at)

    def get_page(self, url: str) -> PageContent | None:
        key = url.strip().lower()
        now = time.perf_counter()
        with self._lock:
            entry = self._page_store.get(key)
            if entry is None:
                return None
            if entry.expires_at < now:
                del self._page_store[key]
                return None
            return entry.data

    def set_page(self, url: str, page: PageContent, ttl: float | None = None) -> None:
        key = url.strip().lower()
        expires_at = time.perf_counter() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._page_store[key] = CacheEntry(data=page, expires_at=expires_at)

    def clear(self) -> None:
        with self._lock:
            self._search_store.clear()
            self._page_store.clear()
