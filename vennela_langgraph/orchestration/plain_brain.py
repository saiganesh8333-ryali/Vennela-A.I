from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.errors import BrainFailure, FailureCategory
from vennela_langgraph.core.state import VennelaState
from vennela_langgraph.observability.telemetry import InMemoryTelemetry
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
from vennela_langgraph.adapters.mock_llm import MockLLM
from vennela_langgraph.adapters.mock_memory import MockMemoryAgent
from vennela_langgraph.adapters.mock_web import MockWebAgent
from vennela_langgraph.adapters.mock_pc import MockPCAgent
from vennela_langgraph.adapters.mock_android import MockAndroidAgent
from vennela_langgraph.adapters.llm import DeterministicMockProvider, LLMRouter
from vennela_langgraph.adapters.llm.intent_resolver import LLMIntentResolver
from vennela_langgraph.adapters.llm.planner_adapter import LLMPlannerAdapter
from vennela_langgraph.adapters.llm.reasoning_adapter import LLMReasoningAdapter
from vennela_langgraph.adapters.llm.real_provider import LLMProviderError


class PlainBrain:
    def __init__(self, memory=None, web=None, pc=None, android=None, llm=None, telemetry=None,
                 intelligence_mode="DETERMINISTIC", llm_router=None):
        self.telemetry = telemetry or InMemoryTelemetry()
        self.intelligence_mode = intelligence_mode
        effective_mode = intelligence_mode.upper()
        self.llm_router = llm_router or (
            LLMRouter.from_environment(mode_override="REAL") if effective_mode == "REAL"
            else LLMRouter({"mock": DeterministicMockProvider()})
        )
        resolver = LLMIntentResolver(self.llm_router) if effective_mode in {"LLM_ASSISTED", "REAL"} else None
        planner = LLMPlannerAdapter(self.llm_router) if effective_mode in {"LLM_ASSISTED", "REAL"} else None
        self.nodes = {
            "intent": IntentNode(self.telemetry, resolver),
            "planner": PlannerNode(self.telemetry, planner),
            "memory": MemoryNode(self.telemetry, memory or MockMemoryAgent()),
            "web": WebNode(self.telemetry, web or MockWebAgent()),
            "pc": PCNode(self.telemetry, pc or MockPCAgent()),
            "android": AndroidNode(self.telemetry, android or MockAndroidAgent()),
            "reasoning": ReasoningNode(self.telemetry, llm or MockLLM()),
            "fusion": ContextFusionNode(self.telemetry),
            "verification": VerificationNode(self.telemetry),
            "response": ResponseNode(self.telemetry),
        }
        if effective_mode in {"LLM_ASSISTED", "REAL"}:
            self.nodes["reasoning"].set_reasoning_adapter(LLMReasoningAdapter(self.llm_router))

    def run(self, request: str, session_id: str = "lab-session", user_id=None) -> VennelaState:
        state = VennelaState(
            original_request=request, session_id=session_id, user_id=user_id,
            messages=[{"role": "user", "content": request}],
        )
        state = self._run_node(state, "intent")
        state = self._run_node(state, "planner")
        plan = state.execution_plan
        for step in plan[1:]:
            if step == "verification" and not state.canonical_intent.requires_verification:
                continue
            if step == "reasoning" and not state.fusion_context:
                state = self._run_node(state, "fusion")
            state = self._run_node(state, step)
        return state

    def _run_node(self, state: VennelaState, name: str) -> VennelaState:
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
            )
            return state.apply(StateUpdate(failures=[failure], values={"status": "failed"}))
