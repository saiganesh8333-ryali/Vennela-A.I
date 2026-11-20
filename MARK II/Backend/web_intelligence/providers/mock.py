"""Mock search provider for fast, deterministic unit and integration tests."""

from __future__ import annotations

from typing import Callable, Mapping, Sequence

from .base import SearchProvider
from ..errors import WebHuntError
from ..models import SearchResult

# Preconfigured realistic mock results for common benchmark and testing queries
MOCK_DATABASE: dict[str, list[dict[str, str]]] = {
    "andhra pradesh": [
        {
            "title": "Government of Andhra Pradesh - Official Portal",
            "url": "https://www.ap.gov.in/chief-minister?utm_source=portal",
            "snippet": "N. Chandrababu Naidu serves as the Chief Minister of Andhra Pradesh following the 2024 assembly elections.",
            "score": "0.98",
        },
        {
            "title": "Andhra Pradesh Assembly - Leadership Details",
            "url": "https://aplegislature.org/members/cm",
            "snippet": "The current Chief Minister of Andhra Pradesh is Nara Chandrababu Naidu, assuming office in June 2024.",
            "score": "0.95",
        },
        {
            "title": "News Report - AP Cabinet Formation",
            "url": "https://thehindu.com/news/national/andhra-pradesh/chandrababu-naidu-takes-oath-as-ap-cm/article123.ece",
            "snippet": "Chandrababu Naidu sworn in as CM of Andhra Pradesh heading the NDA coalition government.",
            "score": "0.92",
        },
    ],
    "ai agent": [
        {
            "title": "State of Autonomous AI Agents 2026",
            "url": "https://arxiv.org/abs/2601.00001",
            "snippet": "Recent developments in AI agents highlight multi-agent orchestration, proactive context memory, and deterministic tool use.",
            "score": "0.96",
        },
        {
            "title": "Enterprise Multi-Agent Architectures",
            "url": "https://techcrunch.com/2026/02/ai-agents-evolution?ref=rss",
            "snippet": "AI agents have evolved from single prompt execution to asynchronous multi-agent coordination with local tool verification.",
            "score": "0.93",
        },
        {
            "title": "Benchmark Results for Autonomous Agent Protocols",
            "url": "https://huggingface.co/blog/agent-benchmarks-2026",
            "snippet": "Benchmarking autonomous agents demonstrates improved reasoning robustness, latency reduction, and zero hallucination guardrails.",
            "score": "0.90",
        },
    ],
    "rust vs go": [
        {
            "title": "Rust vs Go for Backend Microservices in 2026",
            "url": "https://eng.uber.com/rust-vs-go-backends",
            "snippet": "Go provides high developer velocity and built-in goroutine concurrency, while Rust provides zero-cost abstractions and memory safety without GC pauses.",
            "score": "0.94",
        },
        {
            "title": "Performance Analysis: Rust and Golang Services",
            "url": "https://blog.cloudflare.com/rust-vs-go-latency",
            "snippet": "Rust demonstrates lower tail latency in memory-constrained environments, whereas Go excels in network I/O bound HTTP APIs.",
            "score": "0.91",
        },
    ],
}


class MockSearchProvider(SearchProvider):
    """Deterministic mock search provider supporting keyword lookups and injected failure states."""

    provider_name: str = "mock"

    def __init__(
        self,
        api_key: str | None = "mock-key",
        timeout: float = 5.0,
        custom_responses: Mapping[str, Sequence[SearchResult]] | None = None,
        error_trigger: WebHuntError | None = None,
    ) -> None:
        super().__init__(api_key=api_key, timeout=timeout)
        self.custom_responses = dict(custom_responses or {})
        self.error_trigger = error_trigger
        self.recorded_queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> Sequence[SearchResult]:
        if not self.api_key:
            raise WebHuntError.missing_key(self.provider_name)

        self.recorded_queries.append(query)

        if self.error_trigger:
            raise self.error_trigger

        clean_query = query.strip()
        lower_query = clean_query.lower()

        # Check custom response first
        for key, res in self.custom_responses.items():
            if key.lower() in lower_query:
                return res[:max_results]

        # Check preconfigured mock database
        for keyword, items in MOCK_DATABASE.items():
            if keyword in lower_query:
                results: list[SearchResult] = []
                for item in items:
                    results.append(
                        SearchResult(
                            query=clean_query,
                            title=item["title"],
                            url=item["url"],
                            snippet=item["snippet"],
                            source_domain=item["url"].split("/")[2].replace("www.", ""),
                            relevance_score=float(item.get("score", 0.9)),
                        )
                    )
                return results[:max_results]

        # Generic fallback mock search result
        return [
            SearchResult(
                query=clean_query,
                title=f"Overview of {clean_query}",
                url=f"https://example.org/topics/{clean_query.replace(' ', '-').lower()}",
                snippet=f"Information regarding {clean_query} and related verified facts.",
                source_domain="example.org",
                relevance_score=0.85,
            )
        ]
