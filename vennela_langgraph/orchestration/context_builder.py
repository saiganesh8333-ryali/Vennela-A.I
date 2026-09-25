from typing import Any, Dict


def build_llm_context(state) -> Dict[str, Any]:
    """Build explicit, labeled context; no uncontrolled prompt concatenation."""
    return {
        "USER_REQUEST": state.original_request,
        "CONVERSATION_CONTEXT": [message.model_dump() for message in state.messages],
        "CANONICAL_INTENT": state.canonical_intent.model_dump() if state.canonical_intent else None,
        "EXECUTION_PLAN": state.plan_details.model_dump() if state.plan_details else None,
        "MEMORY": list(state.memory_context),
        "CAPABILITY_RESULTS": dict(state.tool_results),
        "WEB_EVIDENCE": [item.model_dump() for item in state.web_evidence],
        "VERIFICATION": [item.model_dump() for item in state.verification_results],
        "FAILURES": [item.model_dump() for item in state.errors],
    }
