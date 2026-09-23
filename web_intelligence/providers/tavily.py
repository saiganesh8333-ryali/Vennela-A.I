"""Tavily search provider adapter."""

from __future__ import annotations

import json
import time
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .base import SearchProvider
from ..errors import Failure, FailureKind, WebHuntError
from ..models import SearchResult
from ..telemetry import log_error, log_info, sanitize


class TavilySearchProvider(SearchProvider):
    """Tavily Search API provider."""

    provider_name: str = "tavily"
    endpoint: str = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> Sequence[SearchResult]:
        if not self.api_key:
            raise WebHuntError.missing_key(self.provider_name)

        clean_query = query.strip()
        if not clean_query:
            return []

        payload = {
            "api_key": self.api_key,
            "query": clean_query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }

        data = json.dumps(payload).encode("utf-8")
        req = Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "VennelaWebHunt/0.1",
            },
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                resp_bytes = resp.read()
                try:
                    body = json.loads(resp_bytes.decode("utf-8"))
                except Exception as json_err:
                    raise WebHuntError.invalid_response(self.provider_name, f"Malformed JSON from search provider: {json_err}") from None

        except HTTPError as exc:
            code = exc.code
            safe_reason = sanitize(exc.reason if hasattr(exc, "reason") else str(exc))
            if code in (401, 403):
                raise WebHuntError(
                    Failure(
                        kind=FailureKind.AUTH,
                        message=f"Tavily authentication failed ({code})",
                        retryable=False,
                        provider=self.provider_name,
                        status_code=code,
                    )
                ) from None
            if code == 429:
                raise WebHuntError.rate_limit(self.provider_name, f"Tavily rate limit exceeded ({code})") from None
            if code >= 500:
                raise WebHuntError.server_error(self.provider_name, f"Tavily server error ({code})", status_code=code) from None
            raise WebHuntError(
                Failure(
                    kind=FailureKind.INVALID_REQUEST,
                    message=f"Tavily request error ({code}): {safe_reason}",
                    retryable=False,
                    provider=self.provider_name,
                    status_code=code,
                )
            ) from None

        except (URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
                raise WebHuntError.timeout(self.provider_name, f"Tavily search request timed out after {self.timeout}s") from None
            raise WebHuntError(
                Failure(
                    kind=FailureKind.NETWORK,
                    message=f"Tavily network request failed: {sanitize(str(exc))}",
                    retryable=True,
                    provider=self.provider_name,
                )
            ) from None

        if not isinstance(body, dict):
            raise WebHuntError.invalid_response(self.provider_name, "Tavily returned non-dictionary response")

        raw_results = body.get("results")
        if raw_results is None:
            # Check for error message
            if "error" in body:
                raise WebHuntError(
                    Failure(
                        kind=FailureKind.SERVER,
                        message=f"Tavily returned error: {sanitize(str(body.get('error')))}",
                        retryable=False,
                        provider=self.provider_name,
                    )
                )
            return []

        if not isinstance(raw_results, list):
            raise WebHuntError.invalid_response(self.provider_name, "Tavily results field is not a list")

        results: list[SearchResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("content", "")).strip()
            score = item.get("score")
            pub_date = item.get("published_date")

            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            results.append(
                SearchResult(
                    query=clean_query,
                    title=title or domain or "Untitled",
                    url=url,
                    snippet=snippet,
                    source_domain=domain or "unknown",
                    relevance_score=float(score) if isinstance(score, (int, float)) else None,
                    published_date=str(pub_date) if pub_date else None,
                    metadata={"raw_score": score},
                )
            )

        elapsed = (time.perf_counter() - started) * 1000
        log_info(f"Tavily search completed for query='{clean_query}' with {len(results)} results in {elapsed:.1f}ms")
        return results
