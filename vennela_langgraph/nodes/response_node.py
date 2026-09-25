from vennela_langgraph.core.contracts import StateUpdate
from ._base import BaseNode


class ResponseNode(BaseNode):
    name = "response"

    def execute(self, state):
        answer = state.reasoning_context[-1] if state.reasoning_context else "I could not produce a response."
        if state.errors:
            failed_nodes = ", ".join(sorted({error.node for error in state.errors}))
            answer += f" Some workflow steps failed ({failed_nodes}); their results are not being reported as successes."
        return StateUpdate(values={
            "response": answer, "status": "completed",
            "response_metadata": {
                **state.response_metadata,
                "evidence_count": len(state.web_evidence),
                "verification_statuses": [r.status for r in state.verification_results],
            },
        })
