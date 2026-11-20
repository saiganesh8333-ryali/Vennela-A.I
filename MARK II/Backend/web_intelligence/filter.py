"""Source filtering, URL normalization, and deduplication for Web Intelligence."""

from __future__ import annotations

import re
from typing import Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .models import SearchResult, SourceProvenance

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_src",
    "source",
    "fbclid",
    "gclid",
    "msclkid",
    "ncid",
    "sr_share",
    "igshid",
}

HIGH_AUTHORITY_TLDS = {".gov", ".edu", ".org", ".gov.in", ".gov.uk", ".int"}


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, fragments, trailing slashes, and standardizing host."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()

        # Strip www. prefix for consistent comparison
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = parsed.path.rstrip("/")
        if not path:
            path = ""

        # Filter out tracking query parameters
        filtered_queries = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in TRACKING_PARAMS
        ]
        query = urlencode(filtered_queries) if filtered_queries else ""

        # Drop fragment completely
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return url.strip()


def extract_clean_domain(url: str) -> str:
    """Extract clean domain name without www or port."""
    try:
        netloc = urlparse(url).netloc.lower().split(":")[0]
        if netloc.startswith("www."):
            return netloc[4:]
        return netloc or "unknown"
    except Exception:
        return "unknown"


def domain_authority_bias(domain: str) -> float:
    """Bonus score for institutional, government, or academic sources."""
    d = domain.lower()
    if any(d.endswith(tld) for tld in HIGH_AUTHORITY_TLDS):
        return 0.15
    if "wikipedia.org" in d or "github.com" in d or "arxiv.org" in d:
        return 0.10
    return 0.0


class SourceFilter:
    """Filters, deduplicates, and ranks search results across multiple queries."""

    def __init__(self, min_snippet_length: int = 15) -> None:
        self.min_snippet_length = min_snippet_length

    def deduplicate_and_rank(self, results: Sequence[SearchResult]) -> list[SearchResult]:
        """Deduplicates results by canonical URL and ranks by relevance and source authority."""
        seen_urls: dict[str, SearchResult] = {}

        for res in results:
            if not res.url or not res.snippet:
                continue
            if len(res.snippet.strip()) < self.min_snippet_length:
                continue

            canonical = normalize_url(res.url)
            if not canonical:
                continue

            domain = extract_clean_domain(canonical)
            base_score = res.relevance_score if res.relevance_score is not None else 0.75
            adjusted_score = min(1.0, base_score + domain_authority_bias(domain))

            if canonical not in seen_urls:
                seen_urls[canonical] = SearchResult(
                    query=res.query,
                    title=res.title or domain,
                    url=canonical,
                    snippet=res.snippet.strip(),
                    source_domain=domain,
                    relevance_score=adjusted_score,
                    published_date=res.published_date,
                    metadata=res.metadata,
                )
            else:
                # Merge snippet if alternative provides richer text
                existing = seen_urls[canonical]
                if len(res.snippet) > len(existing.snippet):
                    seen_urls[canonical] = SearchResult(
                        query=existing.query,
                        title=existing.title or res.title,
                        url=canonical,
                        snippet=res.snippet.strip(),
                        source_domain=domain,
                        relevance_score=max(existing.relevance_score or 0.0, adjusted_score),
                        published_date=existing.published_date or res.published_date,
                        metadata=existing.metadata,
                    )

        # Sort results: descending relevance score
        ranked = sorted(
            seen_urls.values(),
            key=lambda r: (r.relevance_score or 0.0),
            reverse=True,
        )
        return ranked

    def build_provenance_list(self, filtered_results: Sequence[SearchResult]) -> list[SourceProvenance]:
        """Convert filtered results into structured SourceProvenance items."""
        provenance: list[SourceProvenance] = []
        for r in filtered_results:
            provenance.append(
                SourceProvenance(
                    url=r.url,
                    domain=r.source_domain,
                    title=r.title,
                    snippet=r.snippet,
                    claims_supported=[],
                )
            )
        return provenance
