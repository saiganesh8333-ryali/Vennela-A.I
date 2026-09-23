"""Central Research Engine for Vennela Web Intelligence / Web Hunt Layer."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Sequence

from .analyzer import CrossSourceAnalyzer
from .cache import ResearchCache
from .config import WebIntelligenceSettings
from .errors import Failure, FailureKind, WebHuntError
from .filter import SourceFilter
from .models import (
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
from .telemetry import TelemetryTracker, log_error, log_info, log_warning, sanitize


class ResearchEngine:
    """Orchestrates planning, multi-query search, deduplication, deep page reading, and cross-source analysis."""

    def __init__(
        self,
        settings: WebIntelligenceSettings | None = None,
        search_provider: SearchProvider | None = None,
        page_reader: PageReader | None = None,
        planner: QueryPlanner | None = None,
        source_filter: SourceFilter | None = None,
        analyzer: CrossSourceAnalyzer | None = None,
        cache: ResearchCache | None = None,
    ) -> None:
        self.settings = settings or WebIntelligenceSettings.from_env()
        self.planner = planner or QueryPlanner()
        self.source_filter = source_filter or SourceFilter()
        self.analyzer = analyzer or CrossSourceAnalyzer()

        # Wire search provider
        if search_provider is not None:
            self.search_provider = search_provider
        elif self.settings.tavily_api_key:
            self.search_provider = TavilySearchProvider(
                api_key=self.settings.tavily_api_key,
                timeout=self.settings.search_timeout_seconds,
            )
        else:
            # Safe default when no key is set; callers will get structured missing key diagnosis
            self.search_provider = TavilySearchProvider(
                api_key=None,
                timeout=self.settings.search_timeout_seconds,
            )

        # Wire page reader
        if page_reader is not None:
            self.page_reader = page_reader
        else:
            self.page_reader = HTTPPageReader(
                timeout=self.settings.page_fetch_timeout_seconds,
                max_bytes=self.settings.max_page_content_bytes,
                user_agent=self.settings.user_agent,
            )

        # Wire cache
        if cache is not None:
            self.cache = cache
        elif self.settings.cache_enabled:
            self.cache = ResearchCache(default_ttl_seconds=self.settings.cache_ttl_seconds)
        else:
            self.cache = None

    def hunt(
        self,
        query: str,
        deep_retrieval: bool = False,
        max_results: int | None = None,
    ) -> ResearchResult:
        """Execute full standalone internet research hunt for a query."""
        tracker = TelemetryTracker()
        clean_query = query.strip()
        limit = max_results or self.settings.max_search_results_per_query

        log_info("Starting research hunt", query=clean_query)

        # Step 1: Query Planning
        plan = self.planner.plan(clean_query)
        if not plan.needs_search:
            log_info("Query does not require web search", intent=plan.intent, reasoning=plan.reasoning)
            return ResearchResult(
                original_query=clean_query,
                needs_search=False,
                search_queries=[],
                sources=[],
                extracted_information=[],
                key_findings=[],
                uncertainties=[],
                timestamp=datetime.now(timezone.utc).isoformat(),
                errors_and_warnings=[],
                metadata={
                    **tracker.summary(),
                    "intent": plan.intent,
                    "reasoning": plan.reasoning,
                    "search_executed": False,
                },
            )

        # Step 2: Multi-Query Search Execution
        raw_results: list[SearchResult] = []
        tracker.search_queries_count = len(plan.search_queries)

        for search_q in plan.search_queries:
            # Check cache
            cached = self.cache.get_search(search_q) if self.cache else None
            if cached is not None:
                tracker.cache_hits += 1
                raw_results.extend(cached)
                continue

            try:
                results = self.search_provider.search(search_q, max_results=limit)
                raw_results.extend(results)
                if self.cache:
                    self.cache.set_search(search_q, results)
            except WebHuntError as exc:
                tracker.record_error(f"Search failed for '{search_q}': {exc.failure.message}")
            except Exception as exc:
                tracker.record_error(f"Unexpected search error for '{search_q}': {sanitize(str(exc))}")

        tracker.results_found_count = len(raw_results)

        # If zero results obtained and we had failures
        if not raw_results:
            return ResearchResult(
                original_query=clean_query,
                needs_search=True,
                search_queries=plan.search_queries,
                sources=[],
                extracted_information=[],
                key_findings=[],
                uncertainties=["No search results were retrieved for the query."],
                timestamp=datetime.now(timezone.utc).isoformat(),
                errors_and_warnings=tracker.errors,
                metadata={
                    **tracker.summary(),
                    "provider": getattr(self.search_provider, "provider_name", "unknown"),
                    "search_executed": True,
                },
            )

        # Step 3: Source Filtering, URL Normalization, and Deduplication
        filtered_results = self.source_filter.deduplicate_and_rank(raw_results)
        tracker.results_filtered_count = len(filtered_results)
        initial_sources = self.source_filter.build_provenance_list(filtered_results)

        # Step 4: Selective Webpage Retrieval (Deep Retrieval)
        retrieved_pages: list[PageContent] = []
        should_retrieve_pages = deep_retrieval or plan.requires_deep_retrieval
        pages_to_fetch = min(len(filtered_results), self.settings.max_pages_to_retrieve)

        if should_retrieve_pages and pages_to_fetch > 0:
            for item in filtered_results[:pages_to_fetch]:
                target_url = item.url
                # Check cache for page
                cached_page = self.cache.get_page(target_url) if self.cache else None
                if cached_page is not None:
                    tracker.cache_hits += 1
                    retrieved_pages.append(cached_page)
                    continue

                try:
                    page = self.page_reader.fetch_page(target_url)
                    if page.success:
                        tracker.pages_retrieved_count += 1
                        retrieved_pages.append(page)
                        if self.cache:
                            self.cache.set_page(target_url, page)
                    else:
                        tracker.pages_failed_count += 1
                        if page.error_message:
                            tracker.record_error(f"Page fetch failed for '{target_url}': {page.error_message}")
                except Exception as exc:
                    tracker.pages_failed_count += 1
                    tracker.record_error(f"Error fetching page '{target_url}': {sanitize(str(exc))}")

        # Step 5: Cross-Source Synthesis & Conflict Detection
        extracted_facts, key_findings, uncertainties, updated_sources = self.analyzer.analyze(
            query=clean_query,
            results=filtered_results,
            pages=retrieved_pages,
            sources=initial_sources,
        )

        # Step 6: Construct Final Structured Result
        metadata = {
            **tracker.summary(),
            "provider": getattr(self.search_provider, "provider_name", "unknown"),
            "reader": getattr(self.page_reader, "reader_name", "unknown"),
            "search_executed": True,
            "deep_retrieval_used": should_retrieve_pages,
            "plan_intent": plan.intent,
        }

        result = ResearchResult(
            original_query=clean_query,
            needs_search=True,
            search_queries=plan.search_queries,
            sources=updated_sources,
            extracted_information=extracted_facts,
            key_findings=key_findings,
            uncertainties=uncertainties,
            timestamp=datetime.now(timezone.utc).isoformat(),
            errors_and_warnings=tracker.errors,
            metadata=metadata,
        )

        log_info(
            "Completed research hunt",
            query=clean_query,
            elapsed_ms=metadata["elapsed_ms"],
            findings=len(key_findings),
            sources=len(updated_sources),
        )
        return result
