"""Public models for the Web Hunt Agent contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from web_intelligence.models import ResearchResult


@dataclass(frozen=True)
class WebHuntOptions:
    """Per-request controls accepted by :meth:`WebHuntAgent.run`."""

    deep_retrieval: bool = False
    max_results: int | None = None
    timeout_seconds: float | None = None

    @classmethod
    def from_value(cls, value: "WebHuntOptions | Mapping[str, Any] | None") -> "WebHuntOptions":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("options must be WebHuntOptions, a mapping, or None")
        allowed = {"deep_retrieval", "max_results", "timeout_seconds"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported Web Hunt options: {', '.join(sorted(unknown))}")
        options = cls(**dict(value))
        if options.max_results is not None and options.max_results < 1:
            raise ValueError("max_results must be at least 1")
        if options.timeout_seconds is not None and options.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        return options


@dataclass(frozen=True)
class AgentStatus:
    """Operational status exposed to a future agent orchestrator."""

    agent_id: str
    name: str
    version: str
    healthy: bool
    provider: str
    details: dict[str, Any] = field(default_factory=dict)


__all__ = ["AgentStatus", "ResearchResult", "WebHuntOptions"]
