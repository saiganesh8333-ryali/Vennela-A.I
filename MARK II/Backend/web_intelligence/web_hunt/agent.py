"""Standalone async boundary around the existing Web Intelligence engine."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Mapping
from uuid import uuid4

from web_intelligence.config import WebIntelligenceSettings
from web_intelligence.engine import ResearchEngine
from web_intelligence.models import ResearchResult
from web_intelligence.telemetry import log_error, log_info, sanitize

from .config import (
    AGENT_DESCRIPTION,
    AGENT_ID,
    AGENT_NAME,
    AGENT_VERSION,
    CAPABILITIES,
)
from .models import AgentStatus, WebHuntOptions


class WebHuntAgent:
    """Orchestrator-facing Web research agent.

    Provider, reader, planner, filtering, analysis, and cache details remain
    inside ``ResearchEngine`` and are intentionally not exposed here.
    """

    name = AGENT_NAME
    agent_id = AGENT_ID
    version = AGENT_VERSION
    description = AGENT_DESCRIPTION
    capabilities = CAPABILITIES
    input_contract = "task: non-empty str; context: optional mapping; options: optional WebHuntOptions"
    output_contract = "web_intelligence.models.ResearchResult"

    def __init__(
        self,
        engine: ResearchEngine | None = None,
        *,
        settings: WebIntelligenceSettings | None = None,
    ) -> None:
        self.engine = engine or ResearchEngine(settings=settings)

    def health_check(self) -> AgentStatus:
        """Return a non-network health snapshot suitable for an orchestrator."""
        provider = getattr(self.engine.search_provider, "provider_name", "unknown")
        healthy = bool(self.engine.search_provider.health_check())
        return AgentStatus(
            agent_id=self.agent_id,
            name=self.name,
            version=self.version,
            healthy=healthy,
            provider=provider,
            details={"engine": type(self.engine).__name__},
        )

    async def run(
        self,
        task: str,
        *,
        context: Mapping[str, Any] | None = None,
        options: WebHuntOptions | Mapping[str, Any] | None = None,
    ) -> ResearchResult:
        """Research ``task`` and return a source-backed structured result."""
        request_id = str(uuid4())
        started = time.perf_counter()
        event = {"request_id": request_id, "agent_id": self.agent_id}
        log_info("web_hunt.started", **event)

        if not isinstance(task, str) or not task.strip():
            return self._failure_result(
                task if isinstance(task, str) else "",
                "INVALID_TASK",
                "Research task must be a non-empty string.",
                request_id,
                started,
            )

        try:
            request_options = WebHuntOptions.from_value(options)
        except (TypeError, ValueError) as exc:
            return self._failure_result(
                task.strip(),
                "INVALID_OPTIONS",
                str(exc),
                request_id,
                started,
            )

        timeout = request_options.timeout_seconds
        try:
            log_info("web_hunt.query_planned", **event)
            hunt = asyncio.to_thread(
                self.engine.hunt,
                task,
                request_options.deep_retrieval,
                request_options.max_results,
            )
            result = await asyncio.wait_for(hunt, timeout=timeout) if timeout else await hunt
        except asyncio.TimeoutError:
            result = self._failure_result(
                task.strip(),
                "TIMEOUT",
                "Web research timed out before completion.",
                request_id,
                started,
                retryable=True,
            )
        except Exception as exc:
            message = sanitize(str(exc)) or "Web research failed unexpectedly."
            log_error("web_hunt.failed", **event, error=message)
            result = self._failure_result(
                task.strip(),
                "ENGINE_FAILURE",
                message,
                request_id,
                started,
                retryable=True,
            )
        else:
            result = self._annotate_result(result, request_id, started, context)
            log_info(
                "web_hunt.completed",
                **event,
                provider=result.metadata.get("provider", "unknown"),
                sources=len(result.sources),
                findings=len(result.key_findings),
            )
        return result

    def _annotate_result(
        self,
        result: ResearchResult,
        request_id: str,
        started: float,
        context: Mapping[str, Any] | None,
    ) -> ResearchResult:
        metadata = {
            **result.metadata,
            "request_id": request_id,
            "agent_id": self.agent_id,
            "agent_version": self.version,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "status": (
                "partial"
                if result.errors_and_warnings and (result.sources or result.key_findings)
                else "failed"
                if result.errors_and_warnings
                else "completed"
            ),
        }
        if context:
            metadata["context_keys"] = sorted(str(key) for key in context)
        log_info(
            "web_hunt.search_completed",
            request_id=request_id,
            sources=len(result.sources),
            errors=len(result.errors_and_warnings),
        )
        log_info(
            "web_hunt.analysis_completed",
            request_id=request_id,
            findings=len(result.key_findings),
        )
        return ResearchResult(
            original_query=result.original_query,
            needs_search=result.needs_search,
            search_queries=result.search_queries,
            sources=result.sources,
            extracted_information=result.extracted_information,
            key_findings=result.key_findings,
            uncertainties=result.uncertainties,
            timestamp=result.timestamp,
            errors_and_warnings=result.errors_and_warnings,
            metadata=metadata,
        )

    def _failure_result(
        self,
        query: str,
        code: str,
        message: str,
        request_id: str,
        started: float,
        *,
        retryable: bool = False,
    ) -> ResearchResult:
        log_error("web_hunt.failed", request_id=request_id, code=code, error=message)
        return ResearchResult(
            original_query=query.strip(),
            needs_search=bool(query.strip()),
            uncertainties=[message],
            errors_and_warnings=[message],
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "request_id": request_id,
                "agent_id": self.agent_id,
                "agent_version": self.version,
                "status": "failed",
                "error_code": code,
                "retryable": retryable,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
