"""Isolated Central Brain orchestration boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Mapping
from uuid import uuid4

from web_intelligence.models import ResearchResult
from web_intelligence.telemetry import log_error, log_info, sanitize

from .models import DelegationDecision, DelegationType
from .orchestrator import AgentOrchestrator
from .planner import PlannerError, TaskDelegationPlanner
from .reasoning import ReasoningLayer, ReasoningResponse, VennelaReasoningAdapter


@dataclass(frozen=True)
class BrainResult:
    """One normalized result contract for direct and delegated tasks."""

    request_id: str
    status: str
    task: str
    decision: DelegationType | None = None
    capability: str | None = None
    agent_id: str | None = None
    result: ResearchResult | None = None
    error: dict[str, Any] | None = None
    response: str | None = None
    model_id: str | None = None
    provider: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "task": self.task,
            "decision": self.decision.value if self.decision else None,
            "capability": self.capability,
            "agent_id": self.agent_id,
            "result": self.result.to_dict() if self.result else None,
            "error": dict(self.error) if self.error else None,
            "response": self.response,
            "model_id": self.model_id,
            "provider": self.provider,
            "usage": dict(self.usage),
            "metadata": dict(self.metadata),
            "duration_ms": self.duration_ms,
        }


class VennelaBrain:
    """Coordinates planning and delegation without reasoning or agent logic."""

    def __init__(
        self,
        planner: TaskDelegationPlanner | None = None,
        orchestrator: AgentOrchestrator | None = None,
        reasoning: ReasoningLayer | None = None,
    ) -> None:
        self.planner = planner or TaskDelegationPlanner()
        self.orchestrator = orchestrator
        self.reasoning = reasoning

    async def process(
        self,
        task: str,
        *,
        request_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        constraints: Mapping[str, Any] | None = None,
        options: Any = None,
        timeout_seconds: float | None = None,
        messages: list[Mapping[str, str]] | None = None,
    ) -> BrainResult:
        request_id = request_id or str(uuid4())
        started = time.perf_counter()
        log_info("brain.started", request_id=request_id)

        if not isinstance(task, str) or not task.strip():
            return self._failure(
                task if isinstance(task, str) else "",
                request_id,
                "INVALID_TASK",
                "Task must be a non-empty string.",
                started,
                stage="brain",
            )

        try:
            decision = self.planner.plan(
                task,
                context=context,
                constraints=constraints,
                request_id=request_id,
            )
        except PlannerError as exc:
            return self._failure(task, request_id, exc.code, exc.message, started, stage="planner")
        except Exception as exc:
            return self._failure(
                task,
                request_id,
                "PLANNER_FAILURE",
                sanitize(str(exc)) or "Planner failed unexpectedly.",
                started,
                stage="planner",
            )

        if decision.decision is DelegationType.DIRECT:
            response = self._generate_response(
                decision.task,
                request_id,
                started,
                messages=messages,
                context=context,
            )
            if isinstance(response, BrainResult):
                return response
            return BrainResult(
                request_id=request_id,
                status="direct",
                task=decision.task,
                decision=decision.decision,
                response=response.text if response else None,
                model_id=response.model_id if response else None,
                provider=response.provider if response else None,
                usage=response.usage if response else {},
                metadata={
                    **decision.metadata,
                    "reason": decision.reason,
                    "confidence": decision.confidence,
                    "execution": "not_delegated",
                    "fallback_used": response.fallback_used if response else False,
                    "reasoning_attempts": response.attempts if response else (),
                },
                duration_ms=self._duration(started),
            )

        if self.orchestrator is None:
            return self._failure(
                decision.task,
                request_id,
                "ORCHESTRATOR_UNAVAILABLE",
                "No AgentOrchestrator is configured for delegated work.",
                started,
                stage="orchestrator",
                capability=decision.capability,
                decision=decision.decision,
            )

        try:
            agent_result = await self.orchestrator.run(
                decision.task,
                capability=decision.capability or "",
                request_id=request_id,
                context=context,
                options=options,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            return self._failure(
                decision.task,
                request_id,
                "ORCHESTRATOR_FAILURE",
                sanitize(str(exc)) or "Orchestrator failed unexpectedly.",
                started,
                stage="orchestrator",
                capability=decision.capability,
                decision=decision.decision,
            )

        synthesis = self._synthesize_result(
            decision,
            agent_result,
            request_id,
            started,
            messages=messages,
            context=context,
        )
        if isinstance(synthesis, BrainResult):
            return synthesis
        status = "partial" if agent_result.metadata.get("status") == "partial" else (
            "failed" if agent_result.metadata.get("status") == "failed" else "completed"
        )
        return BrainResult(
            request_id=request_id,
            status=status,
            task=decision.task,
            decision=decision.decision,
            capability=decision.capability,
            agent_id=agent_result.metadata.get("orchestrator_agent_id"),
            result=agent_result,
            response=synthesis.text if synthesis else None,
            model_id=synthesis.model_id if synthesis else None,
            provider=synthesis.provider if synthesis else None,
            usage=synthesis.usage if synthesis else {},
            error=(
                {
                    "code": agent_result.metadata.get("error_code", "AGENT_FAILURE"),
                    "message": agent_result.errors[0],
                    "stage": "agent",
                    "retryable": agent_result.metadata.get("retryable", False),
                }
                if agent_result.errors
                else None
            ),
            metadata={
                **decision.metadata,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "orchestrator_request_id": agent_result.metadata.get("orchestrator_request_id"),
                "fallback_used": synthesis.fallback_used if synthesis else False,
                "reasoning_attempts": synthesis.attempts if synthesis else (),
            },
            duration_ms=self._duration(started),
        )

    def _generate_response(self, task, request_id, started, *, messages, context):
        if self.reasoning is None:
            return None
        try:
            return self.reasoning.respond(task, messages=messages, context=context)
        except Exception as exc:
            return self._failure(
                task, request_id, "REASONING_FAILURE", sanitize(str(exc)) or "Reasoning failed.",
                started, stage="reasoning",
            )

    def _synthesize_result(self, decision, agent_result, request_id, started, *, messages, context):
        if self.reasoning is None:
            return None
        findings = "\n".join(f"- {finding}" for finding in agent_result.findings)
        prompt = (
            f"Answer the user's task using the research findings below.\n"
            f"Task: {decision.task}\nFindings:\n{findings or '- No findings were returned.'}"
        )
        return self._generate_response(
            prompt,
            request_id,
            started,
            messages=messages,
            context=context,
        )

    @staticmethod
    def _duration(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    @classmethod
    def _failure(
        cls,
        task: str,
        request_id: str,
        code: str,
        message: str,
        started: float,
        *,
        stage: str,
        capability: str | None = None,
        decision: DelegationType | None = None,
    ) -> BrainResult:
        log_error("brain.failed", request_id=request_id, stage=stage, code=code, error=message)
        return BrainResult(
            request_id=request_id,
            status="failed",
            task=task.strip(),
            decision=decision,
            capability=capability,
            error={
                "code": code,
                "message": message,
                "stage": stage,
                "retryable": code in {"TIMEOUT", "ORCHESTRATOR_FAILURE"},
            },
            metadata={"stage": stage},
            duration_ms=cls._duration(started),
        )


__all__ = ["BrainResult", "VennelaBrain"]
