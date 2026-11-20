"""Typed data models for the Vennela Web Intelligence Layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    """Individual search result item returned by a search provider."""

    query: str
    title: str
    url: str
    snippet: str
    source_domain: str
    relevance_score: float | None = None
    published_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_domain": self.source_domain,
            "relevance_score": self.relevance_score,
            "published_date": self.published_date,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PageContent:
    """Extracted text and metadata from a retrieved webpage."""

    url: str
    title: str
    text_content: str
    status_code: int = 200
    content_length: int = 0
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text_content": self.text_content,
            "status_code": self.status_code,
            "content_length": self.content_length,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class SourceProvenance:
    """Provenance tracking for a verified source domain and URL."""

    url: str
    domain: str
    title: str
    snippet: str = ""
    claims_supported: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "snippet": self.snippet,
            "claims_supported": self.claims_supported,
        }


@dataclass(frozen=True)
class ExtractedFact:
    """Single verified atomic fact with direct source provenance."""

    fact: str
    source_url: str
    source_domain: str
    confidence: float = 1.0
    entity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact": self.fact,
            "source_url": self.source_url,
            "source_domain": self.source_domain,
            "confidence": self.confidence,
            "entity": self.entity,
        }


@dataclass(frozen=True)
class ResearchPlan:
    """Strategic plan constructed by the QueryPlanner."""

    original_query: str
    needs_search: bool
    intent: str
    search_queries: list[str] = field(default_factory=list)
    reasoning: str = ""
    requires_deep_retrieval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "needs_search": self.needs_search,
            "intent": self.intent,
            "search_queries": self.search_queries,
            "reasoning": self.reasoning,
            "requires_deep_retrieval": self.requires_deep_retrieval,
        }


@dataclass(frozen=True)
class ResearchResult:
    """Complete, structured output of the ResearchEngine."""

    original_query: str
    needs_search: bool
    search_queries: list[str] = field(default_factory=list)
    sources: list[SourceProvenance] = field(default_factory=list)
    extracted_information: list[ExtractedFact] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    errors_and_warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "needs_search": self.needs_search,
            "search_queries": self.search_queries,
            "sources": [s.to_dict() for s in self.sources],
            "extracted_information": [f.to_dict() for f in self.extracted_information],
            "key_findings": self.key_findings,
            "uncertainties": self.uncertainties,
            "timestamp": self.timestamp,
            "errors_and_warnings": self.errors_and_warnings,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @property
    def query(self) -> str:
        """Agent-facing alias for the original research task."""
        return self.original_query

    @property
    def findings(self) -> list[str]:
        """Agent-facing alias for synthesized key findings."""
        return self.key_findings

    @property
    def provider(self) -> str | None:
        return self.metadata.get("provider")

    @property
    def confidence(self) -> float | None:
        """Average fact confidence when the analyzer produced verified facts."""
        if not self.extracted_information:
            return None
        return sum(fact.confidence for fact in self.extracted_information) / len(self.extracted_information)

    @property
    def errors(self) -> list[str]:
        return self.errors_and_warnings

    @property
    def warnings(self) -> list[str]:
        return self.errors_and_warnings
