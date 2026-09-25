from vennela_langgraph.core.contracts import StateUpdate
from ._base import BaseNode


class ContextFusionNode(BaseNode):
    name = "fusion"

    def execute(self, state):
        return StateUpdate(values={
            "fusion_context": {
                "intent": state.canonical_intent.model_dump() if state.canonical_intent else None,
                "plan_id": state.plan_id,
                "memory_context": list(state.memory_context),
                "capability_results": dict(state.tool_results),
                "web_evidence": [item.model_dump() for item in state.web_evidence],
                "verification_results": [item.model_dump() for item in state.verification_results],
                "failures": [item.model_dump() for item in state.errors],
            },
            "status": "fused",
        })
