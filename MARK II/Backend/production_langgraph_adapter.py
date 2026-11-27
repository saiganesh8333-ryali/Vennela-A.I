"""Production compatibility boundary for the LangGraph Brain.

The lab graph keeps its existing contracts and node implementations. This
adapter supplies production conversation, memory, and LLM services without
making the lab mocks part of the production path.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import importlib
import logging
from threading import RLock
from time import perf_counter
from typing import Any, Mapping, Sequence

from core.intelligence_contracts import BrainResult, DelegationType


logger = logging.getLogger(__name__)
_LAB_IMPORT_LOCK = RLock()
_LANGGRAPH_CLASS = None
_RESOLVE_INTENT = None
_TELEMETRY_CLASS = None


@dataclass(frozen=True)
class _RequestExecutionContext:
    """Immutable per-request execution scope isolated across concurrent Brain B calls."""

    request_id: str
    user_id: str | None
    session_id: str
    system_instruction: str | None
    messages: tuple[dict[str, str], ...]
    memory_context: tuple[str, ...]
    timing: dict[str, Any] | None = None
    telemetry: Any = None


_REQUEST_EXECUTION_CONTEXT: ContextVar[_RequestExecutionContext | None] = ContextVar(
    "vennela_brain_b_request_context",
    default=None,
)


@contextmanager
def _isolated_lab_imports():
    """Keep the deployable package isolated from production top-level modules."""
    yield


def _langgraph_brain_class():
    global _LANGGRAPH_CLASS
    if _LANGGRAPH_CLASS is not None:
        return _LANGGRAPH_CLASS
    with _LAB_IMPORT_LOCK:
        if _LANGGRAPH_CLASS is None:
            with _isolated_lab_imports():
                _LANGGRAPH_CLASS = importlib.import_module(
                    "vennela_langgraph.orchestration.langgraph_brain"
                ).LangGraphBrain
    return _LANGGRAPH_CLASS


def _resolve_lab_intent():
    global _RESOLVE_INTENT
    if _RESOLVE_INTENT is not None:
        return _RESOLVE_INTENT
    with _LAB_IMPORT_LOCK:
        if _RESOLVE_INTENT is None:
            with _isolated_lab_imports():
                _RESOLVE_INTENT = importlib.import_module(
                    "vennela_langgraph.core.intent"
                ).resolve_intent
    return _RESOLVE_INTENT


def _in_memory_telemetry_class():
    global _TELEMETRY_CLASS
    if _TELEMETRY_CLASS is not None:
        return _TELEMETRY_CLASS
    with _LAB_IMPORT_LOCK:
        if _TELEMETRY_CLASS is None:
            with _isolated_lab_imports():
                _TELEMETRY_CLASS = importlib.import_module(
                    "vennela_langgraph.observability.telemetry"
                ).InMemoryTelemetry
    return _TELEMETRY_CLASS


def _copy_message(item: Any) -> dict[str, str]:
    if isinstance(item, Mapping):
        return {
            "role": str(item.get("role", "user")),
            "content": str(item.get("content", "")),
        }
    return {
        "role": str(getattr(item, "role", "user")),
        "content": str(getattr(item, "content", "")),
    }


class _RequestScopedTelemetry:
    """Routes node telemetry into the active request's isolated telemetry sink."""

    @property
    def events(self) -> list[Any]:
        req_ctx = _REQUEST_EXECUTION_CONTEXT.get()
        if req_ctx is not None and req_ctx.telemetry is not None:
            return list(req_ctx.telemetry.events)
        return []

    def record(self, *args, **kwargs) -> None:
        req_ctx = _REQUEST_EXECUTION_CONTEXT.get()
        if req_ctx is not None and req_ctx.telemetry is not None:
            req_ctx.telemetry.record(*args, **kwargs)


class _ProvidedMemoryAgent:
    """Stateless memory adapter reading the active request's memory context."""

    def __init__(self, context: Sequence[str] = ()):
        self._default_context = tuple(context)

    @property
    def context(self) -> list[str]:
        req_ctx = _REQUEST_EXECUTION_CONTEXT.get()
        if req_ctx is not None:
            return list(req_ctx.memory_context)
        return list(self._default_context)

    def retrieve(self, request: str) -> list[str]:
        return self.context


class _ProductionReasoningAdapter:
    def __init__(
        self,
        llm_adapter: Any,
        system_instruction: str | None = None,
        messages: Sequence[Mapping[str, str]] = (),
        timing: dict[str, Any] | None = None,
    ):
        self.llm_adapter = llm_adapter
        self.system_instruction = system_instruction
        self.messages = list(messages)
        self.timing = timing

    def _system_instruction_for_state(
        self,
        state,
        *,
        system_instruction: str | None = None,
    ) -> str:
        base_instruction = (
            system_instruction
            if system_instruction is not None
            else self.system_instruction
        )
        sections = [base_instruction] if base_instruction else []
        memory = [item for item in state.memory_context if str(item).strip()]
        evidence = [
            {
                "source_url": item.source_url,
                "title": item.title,
                "facts": list(item.extracted_facts),
                "uncertainties": list(item.uncertainties),
            }
            for item in state.web_evidence
        ]
        if memory:
            sections.append(
                "Verified retrieved user memory (prefer this over assumptions; "
                "do not contradict it):\n"
                + "\n".join(f"- {item}" for item in memory)
            )
        if evidence:
            sections.append(
                "Fresh web evidence (use these sources for current-information answers):\n"
                + "\n".join(
                    f"- {item['title']} ({item['source_url']}): "
                    f"{'; '.join(item['facts'])}"
                    for item in evidence
                )
            )
        elif state.canonical_intent and state.canonical_intent.requires_web:
            sections.append(
                "Fresh web retrieval failed or returned no evidence. "
                "State clearly that current data could not be retrieved; "
                "do not invent a current answer."
            )
        if state.errors:
            sections.append(
                "Unresolved workflow failures:\n"
                + "\n".join(f"- {error.node}: {error.message}" for error in state.errors)
            )
        return "\n\n".join(section for section in sections if section)

    def reason(self, state):
        req_ctx = _REQUEST_EXECUTION_CONTEXT.get()
        system_instruction = (
            req_ctx.system_instruction
            if req_ctx is not None
            else self.system_instruction
        )
        messages = (
            [dict(item) for item in req_ctx.messages]
            if req_ctx is not None
            else list(self.messages)
        )
        timing = req_ctx.timing if req_ctx is not None else self.timing

        route_kwargs = {
            "system_instruction": self._system_instruction_for_state(
                state,
                system_instruction=system_instruction,
            ),
            "messages": messages,
            "latency_sensitive": False,
            "max_tokens": None,
            "task_hint": "reasoning",
        }
        if timing is not None:
            route_kwargs["timing_callback"] = timing.setdefault(
                "llm_events", []
            ).append
        raw = self.llm_adapter.route_text(state.original_request, **route_kwargs)
        proposal_type = type(
            "ResponseProposal",
            (),
            {
                "response_text": raw["text"],
                "confidence": 1.0,
                "evidence_refs": [item.source_url for item in state.web_evidence],
                "unresolved_items": [error.message for error in state.errors],
                "follow_up_required": False,
            },
        )
        return proposal_type()


class ProductionLangGraphBrain:
    """Brain-compatible standalone LangGraph wrapper (Brain B — NEXUS fully decoupled).

    Brain A (VennelaBrain / NEXUS) is no longer referenced here. All requests
    are handled by Brain B's LangGraph execution engine. If the graph cannot
    support a request, a structured BrainResult failure is returned directly.
    """

    backend = "langgraph-production"

    def __init__(
        self,
        llm_adapter: Any,
        adjuster: Any,
        *,
        pc_gateway: Any | None = None,
        android_gateway: Any | None = None,
        web_agent: Any | None = None,
    ):
        self.llm_adapter = llm_adapter
        self.adjuster = adjuster
        self.pc_gateway = pc_gateway
        self.android_gateway = android_gateway
        self.web_agent = web_agent
        self._graph = None
        self._graph_build_lock = RLock()

    def _supports_graph_request(self, request: str) -> bool:
        intent = _resolve_lab_intent()(request)
        return (
            not intent.requires_pc or self.pc_gateway is not None
        ) and (
            not intent.requires_android or self.android_gateway is not None
        ) and (
            not intent.requires_web or self.web_agent is not None
        )

    def _get_graph(
        self,
        memory_context: Sequence[str] = (),
        system_instruction: str | None = None,
        messages: Sequence[Mapping[str, str]] = (),
    ):
        """Return the shared compiled Brain B graph without mutating request state."""
        if self._graph is None:
            with self._graph_build_lock:
                if self._graph is None:
                    graph_class = _langgraph_brain_class()
                    graph = graph_class(
                        intelligence_mode="DETERMINISTIC",
                        memory=_ProvidedMemoryAgent(),
                        pc=self._production_pc_agent(),
                        android=self._production_android_agent(),
                        web=self._production_web_agent(),
                        telemetry=_RequestScopedTelemetry(),
                    )
                    graph.nodes["reasoning"].set_reasoning_adapter(
                        _ProductionReasoningAdapter(self.llm_adapter),
                    )
                    self._graph = graph
        return self._graph

    def _production_pc_agent(self):
        if self.pc_gateway is None:
            return None
        from production_capability_adapters import ProductionPCAgent

        return ProductionPCAgent(self.pc_gateway)

    def _production_android_agent(self):
        if self.android_gateway is None:
            return None
        from production_capability_adapters import ProductionAndroidAgent

        return ProductionAndroidAgent(self.android_gateway)

    def _production_web_agent(self):
        if self.web_agent is None:
            return None
        from production_capability_adapters import ProductionWebAgent

        return ProductionWebAgent(self.web_agent)

    def _run_graph_sync(
        self,
        task: str,
        request_ctx: _RequestExecutionContext,
    ):
        """Execute the synchronous LangGraph invocation inside an isolated request scope."""
        graph = self._get_graph(
            request_ctx.memory_context,
            request_ctx.system_instruction,
            request_ctx.messages,
        )
        token = _REQUEST_EXECUTION_CONTEXT.set(request_ctx)
        try:
            return graph.run(
                task,
                session_id=request_ctx.session_id,
                user_id=request_ctx.user_id,
                messages=[dict(item) for item in request_ctx.messages],
                memory_context=list(request_ctx.memory_context),
                request_id=request_ctx.request_id or None,
            )
        finally:
            _REQUEST_EXECUTION_CONTEXT.reset(token)

    async def process(
        self,
        task: str,
        *,
        request_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        messages: Sequence[Mapping[str, str]] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        memory_context: Sequence[str] | None = None,
        timing: dict[str, Any] | None = None,
        **kwargs,
    ) -> BrainResult:
        started = perf_counter()
        context = dict(context or {})
        timing = timing or context.pop("_timing", None)
        session_id = session_id or context.pop("_session_id", None)
        user_id = user_id or context.pop("_user_id", None)
        memory_context = memory_context or context.pop("_memory_context", None)
        try:
            capability_check_started = perf_counter()
            graph_supported = self._supports_graph_request(task)
            capability_check_ms = round((perf_counter() - capability_check_started) * 1000, 3)
        except Exception as exc:
            logger.warning(
                "LangGraph capability check unavailable; using NEXUS fallback: %s",
                type(exc).__name__,
            )
            graph_supported = False
        if not graph_supported:
            # Brain A is fully decoupled — return a structured failure.
            # Callers may surface a user-facing message or retry with reduced capabilities.
            logger.warning(
                "Brain B does not support this request (missing capability). "
                "request_id=%s task_prefix=%.60r",
                request_id,
                task,
            )
            return BrainResult(
                request_id=request_id or "",
                status="failed",
                task=task,
                decision=DelegationType.DIRECT,
                error={
                    "code": "UNSUPPORTED_REQUEST",
                    "message": (
                        "Brain B does not support this request type. "
                        "Required capabilities are unavailable."
                    ),
                    "stage": "routing",
                    "retryable": False,
                },
            )

        try:
            system_instruction = context.get("_system_instruction")
            history = tuple(
                _copy_message(item)
                for item in (messages or [{"role": "user", "content": task}])
            )
            memory_items = tuple(str(item) for item in (memory_context or ()))
            telemetry_cls = _in_memory_telemetry_class()
            request_ctx = _RequestExecutionContext(
                request_id=request_id or "",
                user_id=user_id,
                session_id=session_id or "production-session",
                system_instruction=system_instruction,
                messages=history,
                memory_context=memory_items,
                timing=timing,
                telemetry=telemetry_cls(),
            )
            graph_started = perf_counter()
            state = await asyncio.to_thread(
                self._run_graph_sync,
                task,
                request_ctx,
            )
            graph_execution_ms = round((perf_counter() - graph_started) * 1000, 3)
            reasoning_errors = [
                error for error in state.errors if error.node == "reasoning"
            ]
            if reasoning_errors:
                return BrainResult(
                    request_id=state.request_id,
                    status="failed",
                    task=task,
                    decision=DelegationType.DIRECT,
                    error={
                        "code": "PROVIDER_ERROR",
                        "message": "LangGraph reasoning failed.",
                        "stage": "reasoning",
                        "retryable": any(
                            error.retryable for error in reasoning_errors
                        ),
                    },
                )
            if state.status != "completed" or not state.response:
                raise RuntimeError("LangGraph completed without a response")
            return BrainResult(
                request_id=state.request_id,
                status="completed",
                task=task,
                decision=DelegationType.DIRECT,
                response=state.response,
                metadata={
                    "execution": "langgraph",
                    "backend": self.backend,
                    "session_id": state.session_id,
                    "memory_count": len(state.memory_context),
                    "history_count": len(state.messages),
                    "timings_ms": {
                        "capability_check": capability_check_ms,
                        "graph_execution": graph_execution_ms,
                        "total": round((perf_counter() - started) * 1000, 3),
                    },
                },
            )
        except Exception as exc:
            logger.error(
                "Brain B LangGraph execution failed — no fallback available. "
                "error=%s request_id=%s",
                type(exc).__name__,
                request_id,
                exc_info=True,
            )
            # Brain A is fully decoupled — return a structured failure response.
            return BrainResult(
                request_id=request_id or "",
                status="failed",
                task=task,
                decision=DelegationType.DIRECT,
                error={
                    "code": "EXECUTION_ERROR",
                    "message": f"Brain B execution failed: {type(exc).__name__}",
                    "stage": "graph_execution",
                    "retryable": True,
                },
            )
