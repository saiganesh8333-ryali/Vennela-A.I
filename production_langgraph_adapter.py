"""Production compatibility boundary for the LangGraph Brain.

The lab graph keeps its existing contracts and node implementations. This
adapter supplies production conversation, memory, and LLM services without
making the lab mocks part of the production path.
"""

from __future__ import annotations

from contextlib import contextmanager
import importlib
import logging
from threading import RLock
from time import perf_counter
from typing import Any, Mapping, Sequence

from agents.models import DelegationType
from agents.brain import BrainResult


logger = logging.getLogger(__name__)
_LAB_IMPORT_LOCK = RLock()
_LANGGRAPH_CLASS = None
_RESOLVE_INTENT = None


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


class _ProvidedMemoryAgent:
    def __init__(self, context: Sequence[str]):
        self.context = list(context)

    def retrieve(self, request: str) -> list[str]:
        return list(self.context)


class _ProductionReasoningAdapter:
    def __init__(
        self,
        llm_adapter: Any,
        system_instruction: str | None,
        messages: Sequence[Mapping[str, str]],
        timing: dict[str, Any] | None = None,
    ):
        self.llm_adapter = llm_adapter
        self.system_instruction = system_instruction
        self.messages = list(messages)
        self.timing = timing

    def _system_instruction_for_state(self, state) -> str:
        sections = [self.system_instruction] if self.system_instruction else []
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
        route_kwargs = {
            "system_instruction": self._system_instruction_for_state(state),
            "messages": self.messages,
            "latency_sensitive": False,
            "max_tokens": None,
            "task_hint": "reasoning",
        }
        if self.timing is not None:
            route_kwargs["timing_callback"] = self.timing.setdefault(
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
    """Brain-compatible LangGraph wrapper with a legacy fallback."""

    backend = "langgraph-production"

    def __init__(
        self,
        legacy_brain: Any,
        llm_adapter: Any,
        adjuster: Any,
        *,
        pc_gateway: Any | None = None,
        android_gateway: Any | None = None,
        web_agent: Any | None = None,
    ):
        self.legacy_brain = legacy_brain
        self.llm_adapter = llm_adapter
        self.adjuster = adjuster
        self.pc_gateway = pc_gateway
        self.android_gateway = android_gateway
        self.web_agent = web_agent
        self._graph = None
        self._graph_execution_lock = RLock()

    def _supports_graph_request(self, request: str) -> bool:
        intent = _resolve_lab_intent()(request)
        return (
            not intent.requires_pc or self.pc_gateway is not None
        ) and (
            not intent.requires_android or self.android_gateway is not None
        ) and (
            not intent.requires_web or self.web_agent is not None
        )

    def _get_graph(self, memory_context, system_instruction, messages):
        if self._graph is None:
            graph_class = _langgraph_brain_class()
            self._graph = graph_class(
                intelligence_mode="DETERMINISTIC",
                memory=_ProvidedMemoryAgent(memory_context),
                pc=self._production_pc_agent(),
                android=self._production_android_agent(),
                web=self._production_web_agent(),
            )
            self._graph.nodes["reasoning"].set_reasoning_adapter(
                _ProductionReasoningAdapter(
                    self.llm_adapter,
                    system_instruction,
                    messages,
                ),
            )
        else:
            self._graph.nodes["memory"].agent.context = list(memory_context)
            self._graph.nodes["reasoning"].reasoning_adapter = _ProductionReasoningAdapter(
                self.llm_adapter,
                system_instruction,
                messages,
            )
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
            return await self.legacy_brain.process(
                task,
                request_id=request_id,
                context=context,
                messages=list(messages or []),
                **kwargs,
            )

        try:
            with self._graph_execution_lock:
                system_instruction = (context or {}).get("_system_instruction")
                history = list(messages or [{"role": "user", "content": task}])
                graph = self._get_graph(
                    list(memory_context or []),
                    system_instruction,
                    history,
                )
                graph_nodes = getattr(graph, "nodes", {})
                reasoning_node = graph_nodes.get("reasoning")
                if reasoning_node is not None:
                    reasoning_adapter = getattr(
                        reasoning_node, "reasoning_adapter", None
                    )
                    if reasoning_adapter is not None:
                        reasoning_adapter.timing = timing
                graph_started = perf_counter()
                state = graph.run(
                    task,
                    session_id=session_id or "production-session",
                    user_id=user_id,
                    messages=history,
                    memory_context=list(memory_context or []),
                    request_id=request_id,
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
            logger.warning(
                "LangGraph execution unavailable; using NEXUS fallback: %s",
                type(exc).__name__,
            )
            return await self.legacy_brain.process(
                task,
                request_id=request_id,
                context=context,
                messages=list(messages or []),
                **kwargs,
            )
