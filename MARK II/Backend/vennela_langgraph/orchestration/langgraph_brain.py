"""Real LangGraph orchestration over the lab's existing node contracts."""

from typing import Annotated, List, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.errors import BrainFailure, FailureCategory
from vennela_langgraph.core.state import VennelaState
from vennela_langgraph.adapters.llm.real_provider import LLMProviderError
from vennela_langgraph.nodes.intent_node import IntentNode
from vennela_langgraph.nodes.planner_node import PlannerNode
from vennela_langgraph.nodes.memory_node import MemoryNode
from vennela_langgraph.nodes.web_node import WebNode
from vennela_langgraph.nodes.pc_node import PCNode
from vennela_langgraph.nodes.android_node import AndroidNode
from vennela_langgraph.nodes.reasoning_node import ReasoningNode
from vennela_langgraph.nodes.fusion_node import ContextFusionNode
from vennela_langgraph.nodes.verification_node import VerificationNode
from vennela_langgraph.nodes.response_node import ResponseNode
from .plain_brain import PlainBrain


def merge_states(left: VennelaState, right: VennelaState) -> VennelaState:
    """Reducer for parallel branches; merge only branch-owned collections."""
    if left is None:
        return right
    data = left.model_dump()
    right_data = right.model_dump()
    for field in ("messages", "web_evidence", "verification_results", "reasoning_context"):
        combined = data[field] + [item for item in right_data[field] if item not in data[field]]
        data[field] = combined
    for field in ("errors",):
        combined = data[field] + [item for item in right_data[field] if item not in data[field]]
        data[field] = combined
    data["tool_results"] = {**data["tool_results"], **right_data["tool_results"]}
    data["attempts"] = {**data["attempts"], **right_data["attempts"]}
    data["fusion_context"] = {**data["fusion_context"], **right_data["fusion_context"]}
    for field in ("canonical_intent", "execution_plan", "selected_agents", "status", "response",
                  "response_metadata", "plan_id", "plan_details", "plan_steps",
                  "dependencies", "parallel_groups"):
        if right_data[field] not in (None, [], {}, "created"):
            data[field] = right_data[field]
    return VennelaState.model_validate(data)


class GraphState(TypedDict):
    brain_state: Annotated[VennelaState, merge_states]


class LangGraphBrain(PlainBrain):
    backend = "langgraph"
    max_retries = 1

    def __init__(self, *args, max_retries: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_retries = max_retries
        self.nodes["fusion"] = ContextFusionNode(self.telemetry)
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()

    def _run(self, name: str, state: VennelaState) -> VennelaState:
        try:
            return state.apply(self.nodes[name].run(state))
        except LLMProviderError as exc:
            failure = BrainFailure(
                category=exc.category,
                message=str(exc),
                node=name,
                request_id=state.request_id,
                recoverable=exc.retryable,
                attempt=state.attempts.get(name, 1),
            )
            return state.apply(StateUpdate(failures=[failure], values={"status": "failed"}))
        except Exception as exc:
            failure = BrainFailure(
                category=FailureCategory.UNKNOWN,
                message=f"{name} failed unexpectedly: {exc}",
                node=name,
                request_id=state.request_id,
                recoverable=False,
                attempt=state.attempts.get(name, 1),
            )
            return state.apply(StateUpdate(failures=[failure], values={"status": "failed"}))

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(GraphState)

        def intent(state):
            return {"brain_state": self._run("intent", state["brain_state"])}

        def planner(state):
            return {"brain_state": self._run("planner", state["brain_state"])}

        def route(state):
            return {"brain_state": state["brain_state"]}

        def branch(name):
            return lambda state: {"brain_state": self._run(name, state["brain_state"])}

        def verification(state):
            return {"brain_state": self._run("verification", state["brain_state"])}

        def reasoning(state):
            return {"brain_state": self._run("reasoning", state["brain_state"])}

        def fusion(state):
            return {"brain_state": self._run("fusion", state["brain_state"])}

        def response(state):
            return {"brain_state": self._run("response", state["brain_state"])}

        def initial_routes(state) -> List[str]:
            current = state["brain_state"]
            plan = current.plan_details
            completed = {"web.research", "web-research"} if current.web_evidence else set()
            completed.update({"pc.battery_status", "pc.open_app", "pc.device_time"}
                             if "pc" in current.tool_results else set())
            completed.update({"android.flashlight", "android.device_status"}
                             if "android" in current.tool_results else set())
            branches = []
            for step in plan.steps if plan else []:
                capability_node = step.capability.split(".", 1)[0]
                if capability_node in {"memory", "web", "pc", "android"} and all(
                    dependency in completed for dependency in step.depends_on
                ):
                    branches.append(capability_node)
            return branches or ["reasoning"]

        def recovery_route(state) -> str:
            current = state["brain_state"]
            last = current.verification_results[-1] if current.verification_results else None
            target = current.canonical_intent.target_agent if current.canonical_intent else None
            attempts = current.attempts.get(target or "", 0)
            if last and last.status == "failed" and target in {"pc", "android"} and attempts <= self.max_retries:
                return target
            plan = current.plan_details
            completed = {"web.research", "web-research"} if current.web_evidence else set()
            completed.update({"pc.battery_status", "pc.open_app", "pc.device_time"}
                             if "pc" in current.tool_results else set())
            for step in plan.steps if plan else []:
                if step.capability.startswith("pc.") and "pc" not in current.tool_results and current.attempts.get("pc", 0) == 0 and all(
                    dependency in completed for dependency in step.depends_on
                ):
                    return "pc"
            return "reasoning"

        graph.add_node("intent", intent)
        graph.add_node("planner", planner)
        graph.add_node("route", route)
        for name in ("memory", "web", "pc", "android"):
            graph.add_node(name, branch(name))
        graph.add_node("verification", verification)
        graph.add_node("reasoning", reasoning)
        graph.add_node("fusion", fusion)
        graph.add_node("response", response)
        graph.add_edge(START, "intent")
        graph.add_edge("intent", "planner")
        graph.add_edge("planner", "route")
        for name in ("memory", "web", "pc", "android"):
            graph.add_edge(name, "verification")
        graph.add_conditional_edges("verification", recovery_route, {"pc": "pc", "android": "android", "reasoning": "fusion"})
        graph.add_conditional_edges("route", initial_routes, {
            "memory": "memory", "web": "web", "pc": "pc", "android": "android", "reasoning": "fusion"
        })
        graph.add_edge("fusion", "reasoning")
        graph.add_edge("reasoning", "response")
        graph.add_edge("response", END)
        return graph

    def run(self, request: str, session_id: str = "lab-session", user_id=None,
            messages=None, memory_context=None, request_id=None) -> VennelaState:
        initial = VennelaState(
            request_id=request_id or str(uuid4()),
            original_request=request,
            session_id=session_id,
            user_id=user_id,
            messages=messages or [{"role": "user", "content": request}],
            memory_context=memory_context or [],
        )
        result = self.compiled_graph.invoke({"brain_state": initial})
        return result["brain_state"]

    def stream(self, request: str, session_id: str = "lab-session", user_id=None):
        initial = VennelaState(
            original_request=request,
            session_id=session_id,
            user_id=user_id,
            messages=[{"role": "user", "content": request}],
        )
        for update in self.compiled_graph.stream({"brain_state": initial}, stream_mode="updates"):
            yield update

    def graph_structure(self) -> str:
        graph = self.compiled_graph.get_graph()
        return "\n".join(f"{edge.source} -> {edge.target}" for edge in graph.edges)
