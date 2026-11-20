from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.errors import FailureCategory
from ._base import BaseNode


class MemoryNode(BaseNode):
    name = "memory"

    def __init__(self, telemetry, agent):
        super().__init__(telemetry)
        self.agent = agent

    def execute(self, state):
        try:
            return StateUpdate(values={"memory_context": self.agent.retrieve(state.original_request)})
        except Exception as exc:
            return StateUpdate(failures=[self.failure(state, FailureCategory.AGENT, str(exc), True)])
