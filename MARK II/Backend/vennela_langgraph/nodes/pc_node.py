from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.errors import FailureCategory
from ._base import BaseNode


class PCNode(BaseNode):
    name = "pc"

    def __init__(self, telemetry, agent):
        super().__init__(telemetry)
        self.agent = agent

    def execute(self, state):
        attempt = state.attempts.get(self.name, 0) + 1
        state = state.model_copy(update={"attempts": {**state.attempts, self.name: attempt}})
        try:
            if hasattr(self.agent, "execute_with_context"):
                result = self.agent.execute_with_context(
                    state.canonical_intent.action,
                    state.original_request,
                )
            else:
                result = self.agent.execute(state.canonical_intent.action)
            return StateUpdate(values={"tool_results": {"pc": result}, "attempts": {self.name: attempt}})
        except ValueError as exc:
            return StateUpdate(values={"attempts": {self.name: attempt}},
                               failures=[self.failure(state, FailureCategory.VALIDATION, str(exc))])
        except Exception as exc:
            return StateUpdate(values={"attempts": {self.name: attempt}},
                               failures=[self.failure(state, FailureCategory.AGENT, str(exc), True)])
