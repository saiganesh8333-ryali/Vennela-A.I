from vennela_langgraph.core.contracts import StateUpdate
from ._base import BaseNode


class ReasoningNode(BaseNode):
    name = "reasoning"

    def __init__(self, telemetry, llm):
        super().__init__(telemetry)
        self.llm = llm
        self.reasoning_adapter = None

    def set_reasoning_adapter(self, adapter):
        self.reasoning_adapter = adapter

    def execute(self, state):
        intent = state.canonical_intent
        if intent and intent.ambiguous:
            return StateUpdate(values={
                "reasoning_context": ["I need more detail to determine what you want me to do."],
                "status": "needs_clarification",
            })
        if self.reasoning_adapter:
            proposal = self.reasoning_adapter.reason(state)
            return StateUpdate(values={
                "reasoning_context": [proposal.response_text],
                "response_metadata": {
                    "confidence": proposal.confidence,
                    "evidence_refs": proposal.evidence_refs,
                    "unresolved_items": proposal.unresolved_items,
                    "follow_up_required": proposal.follow_up_required,
                },
                "status": "reasoned",
            })
        context = [str(state.fusion_context)] if state.fusion_context else (
            state.memory_context + [f"tool result: {v}" for v in state.tool_results.values()]
        )
        response = self.llm.generate(state.original_request, context, state.web_evidence,
                                     intent.reasoning_level.value if intent else "simple")
        return StateUpdate(values={"reasoning_context": [response], "status": "reasoned"},
                           events=[{"provider": self.llm.provider, "model": self.llm.model}])
