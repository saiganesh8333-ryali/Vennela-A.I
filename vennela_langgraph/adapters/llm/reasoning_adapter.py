import json
from .contracts import LLMRequest, ResponseProposal


class LLMReasoningAdapter:
    def __init__(self, router):
        self.router = router

    def reason(self, state) -> ResponseProposal:
        evidence_refs = [e.source_url for e in state.web_evidence]
        unresolved = [f"{error.node}: {error.message}" for error in state.errors]
        if state.canonical_intent and state.canonical_intent.ambiguous:
            fallback = "I need more detail to determine what you want me to do."
        else:
            parts = list(state.reasoning_context)
            if not parts:
                parts = ["I could not produce a response."]
            fallback = parts[-1]
        response = self.router.generate(LLMRequest(
            task="reasoning", request_id=state.request_id,
            payload={
                "user_request": state.original_request,
                "canonical_intent": state.canonical_intent.model_dump() if state.canonical_intent else None,
                "execution_plan": state.plan_details.model_dump() if state.plan_details else None,
                "capability_results": state.tool_results,
                "memory_context": state.memory_context,
                "web_evidence": [item.model_dump() for item in state.web_evidence],
                "verification_results": [item.model_dump() for item in state.verification_results],
                "failures": [item.model_dump() for item in state.errors],
                "fallback_response": fallback,
                "evidence_refs": evidence_refs,
                "unresolved_items": unresolved,
            },
        ))
        proposal = ResponseProposal.model_validate(json.loads(response.content))
        if not set(proposal.evidence_refs).issubset(set(evidence_refs)):
            raise ValueError("reasoning referenced evidence that was not present in state")
        return proposal
