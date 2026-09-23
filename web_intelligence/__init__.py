"""Vennela Internet Intelligence / Web Hunt Layer v0.1."""

from .analyzer import CrossSourceAnalyzer
from .cache import ResearchCache
from .config import WebIntelligenceSettings
from .engine import ResearchEngine
from .errors import Failure, FailureKind, WebHuntError
from .filter import SourceFilter, extract_clean_domain, normalize_url
from .models import (
    ExtractedFact,
    PageContent,
    ResearchPlan,
    ResearchResult,
    SearchResult,
    SourceProvenance,
)
from .planner import QueryPlanner
from .providers.base import SearchProvider
from .providers.mock import MockSearchProvider
from .providers.tavily import TavilySearchProvider
from .reader.base import PageReader
from .reader.http_reader import HTTPPageReader
from .reader.mock_reader import MockPageReader

__version__ = "0.1.0"

__all__ = [
    "ResearchEngine",
    "ResearchResult",
    "ResearchPlan",
    "SearchResult",
    "PageContent",
    "SourceProvenance",
    "ExtractedFact",
    "WebIntelligenceSettings",
    "QueryPlanner",
    "SourceFilter",
    "CrossSourceAnalyzer",
    "ResearchCache",
    "SearchProvider",
    "TavilySearchProvider",
    "MockSearchProvider",
    "PageReader",
    "HTTPPageReader",
    "MockPageReader",
    "WebHuntError",
    "Failure",
    "FailureKind",
    "normalize_url",
    "extract_clean_domain",
]
