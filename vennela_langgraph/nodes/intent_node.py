from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.intent import resolve_intent
from ._base import BaseNode


class IntentNode(BaseNode):
    name = "intent"

    def __init__(self, telemetry, resolver=None):
        super().__init__(telemetry)
        self.resolver = resolver

    def execute(self, state):
        if self.resolver:
            intent = self.resolver.resolve(
                state.original_request, state.request_id,
                [message.content for message in state.messages], state.memory_context,
            )
        else:
            intent = resolve_intent(
                state.original_request,
                [message.content for message in state.messages],
                state.memory_context,
            )
        return StateUpdate(values={"canonical_intent": intent, "status": "intent_resolved"})
