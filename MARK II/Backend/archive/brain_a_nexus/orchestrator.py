"""Capability-based coordination for specialized Vennela agents."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Mapping
from uuid import uuid4

from web_intelligence.models import ResearchResult
from web_intelligence.telemetry import log_error, log_info, sanitize

from .registry import AgentRegistry


class AgentOrchestrator:
    """Select and execute a registered agent without embedding domain logic."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    async def run(
        self,
        task: str,
        *,
        capability: str,
        agent_id: str | None = None,
        request_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        options: Any = None,
        timeout_seconds: float | None = None,
    ) -> ResearchResult:
        request_id = request_id or str(uuid4())
        started = time.perf_counter()
        event = {"request_id": request_id, "capability": capability}
        log_info("orchestrator.started", **event)

        if not isinstance(task, str) or not task.strip():
            return self._failure(task if isinstance(task, str) else "", "INVALID_TASK", "Task must be a non-empty string.", request_id, started)
        if not isinstance(capability, str) or not capability.strip():
            return self._failure(task, "INVALID_CAPABILITY", "Capability must be a non-empty string.", request_id, started)
        if timeout_seconds is not None and timeout_seconds <= 0:
            return self._failure(task, "INVALID_TIMEOUT", "timeout_seconds must be greater than zero.", request_id, started)

        if agent_id is not None:
            selected = self.registry.get(agent_id)
            if selected is None:
                return self._failure(task, "UNKNOWN_AGENT", f"Unknown agent '{agent_id}'.", request_id, started)
            if capability not in {str(item) for item in selected.capabilities}:
                return self._failure(
                    task,
                    "AGENT_CAPABILITY_MISMATCH",
                    f"Agent '{agent_id}' does not support '{capability}'.",
                    request_id,
                    started,
                    agent_id,
                )
            candidates = [selected]
        else:
            candidates = self.registry.find_by_capability(capability)
        if not candidates:
            return self._failure(task, "UNAVAILABLE_CAPABILITY", f"No registered agent supports '{capability}'.", request_id, started)
        agent = candidates[0]
        log_info("orchestrator.agent_selected", **event, agent_id=agent.agent_id)

        try:
            run = agent.run(task, context=context, options=options)
            log_info("orchestrator.agent_started", **event, agent_id=agent.agent_id)
            result = await asyncio.wait_for(run, timeout=timeout_seconds) if timeout_seconds else await run
        except asyncio.TimeoutError:
            return self._failure(task, "TIMEOUT", "Agent execution timed out.", request_id, started, agent.agent_id, True)
        except Exception as exc:
            message = sanitize(str(exc)) or "Agent execution failed."
            log_error("orchestrator.failed", **event, agent_id=agent.agent_id, error=message)
            return self._failure(task, "AGENT_EXECUTION_FAILURE", message, request_id, started, agent.agent_id, True)

        metadata = {
            **result.metadata,
            "orchestrator_request_id": request_id,
            "orchestrator_agent_id": agent.agent_id,
            "orchestrator_capability": capability,
            "orchestrator_duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        log_info("orchestrator.agent_completed", **event, agent_id=agent.agent_id, status=metadata.get("status", "completed"))
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

    @staticmethod
    def _failure(
        task: str,
        code: str,
        message: str,
        request_id: str,
        started: float,
        agent_id: str | None = None,
        retryable: bool = False,
    ) -> ResearchResult:
        log_error("orchestrator.failed", request_id=request_id, code=code, error=message)
        metadata = {
            "status": "failed",
            "error_code": code,
            "retryable": retryable,
            "orchestrator_request_id": request_id,
            "orchestrator_duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        if agent_id:
            metadata["orchestrator_agent_id"] = agent_id
        return ResearchResult(
            original_query=task.strip(),
            needs_search=bool(task.strip()),
            uncertainties=[message],
            errors_and_warnings=[message],
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )
