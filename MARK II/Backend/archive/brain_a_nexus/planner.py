"""Deterministic task-to-delegation planning, independent of execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from .models import DelegationDecision, DelegationType


class PlannerError(Exception):
    """Structured input or decision error from the delegation planner."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class TaskDelegationPlanner:
    """Classify tasks using explainable lexical rules.

    The planner decides whether a request should be handled directly or
    delegated by capability. It never imports, discovers, or executes agents.
    """

    WEB_RESEARCH_CAPABILITY = "web_research"
    _WEB_INTENT_TERMS = (
        "search the internet",
        "search online",
        "search the web",
        "look up",
        "browse the web",
        "on the internet",
        "online research",
        "web research",
        "research online",
        "find current",
        "find the latest",
        "latest information",
        "current information",
    )
    _CURRENT_TERMS = (
        "latest",
        "current",
        "recent",
        "today",
        "now",
        "this week",
        "this year",
        "breaking",
        "upcoming",
        "newest",
    )
    _RESEARCH_TERMS = ("research", "search", "internet", "web", "news", "source", "sources")

    def plan(
        self,
        task: str,
        *,
        context: Mapping[str, Any] | None = None,
        constraints: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> DelegationDecision:
        """Return a decision without invoking an agent or external provider."""
        if not isinstance(task, str):
            raise PlannerError("INVALID_TASK", "Task must be a string.")
        clean_task = task.strip()
        if not clean_task:
            raise PlannerError("INVALID_TASK", "Task must be a non-empty string.")
        if context is not None and not isinstance(context, Mapping):
            raise PlannerError("INVALID_CONTEXT", "context must be a mapping when provided.")
        if constraints is not None and not isinstance(constraints, Mapping):
            raise PlannerError("INVALID_CONSTRAINTS", "constraints must be a mapping when provided.")

        normalized = " ".join(clean_task.lower().split())
        metadata = {
            "planner": type(self).__name__,
            "context_keys": sorted(str(key) for key in context) if context else [],
            "constraint_keys": sorted(str(key) for key in constraints) if constraints else [],
        }
        if self._requires_web_research(normalized):
            return DelegationDecision(
                request_id=request_id or str(uuid4()),
                decision=DelegationType.DELEGATE,
                capability=self.WEB_RESEARCH_CAPABILITY,
                task=clean_task,
                reason="Task explicitly requests current, online, search, or research information.",
                confidence=0.95,
                metadata=metadata,
            )
        return DelegationDecision(
            request_id=request_id or str(uuid4()),
            decision=DelegationType.DIRECT,
            capability=None,
            task=clean_task,
            reason="No explicit web research intent was detected; leave handling to the direct path.",
            confidence=0.8,
            metadata=metadata,
        )

    @classmethod
    def _requires_web_research(cls, normalized_task: str) -> bool:
        if any(term in normalized_task for term in cls._WEB_INTENT_TERMS):
            return True
        if any(term in normalized_task for term in cls._CURRENT_TERMS):
            return True
        return any(
            term in normalized_task
            for term in cls._RESEARCH_TERMS
        ) and any(
            marker in normalized_task
            for marker in ("find", "tell me", "what", "who", "how", "about", "information")
        )


__all__ = ["DelegationDecision", "DelegationType", "PlannerError", "TaskDelegationPlanner"]
