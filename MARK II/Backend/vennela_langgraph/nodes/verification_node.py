from vennela_langgraph.core.contracts import StateUpdate, VerificationResult
from vennela_langgraph.core.errors import FailureCategory
from ._base import BaseNode


class VerificationNode(BaseNode):
    name = "verification"

    def execute(self, state):
        results = []
        for agent, result in state.tool_results.items():
            ok = (
                bool(result.get("verified", result.get("executed")))
                if isinstance(result, dict)
                else False
            )
            results.append(VerificationResult(
                status="success" if ok else "failed",
                action=result.get("action") if isinstance(result, dict) else None,
                message=(
                    result.get("error") or "Action completed and passed production verification"
                    if ok else
                    result.get("error") or "Action did not verify."
                ),
                evidence=[str(result)],
            ))
        if state.canonical_intent and state.canonical_intent.requires_tools and not results:
            agent_errors = [error for error in state.errors
                            if error.node == state.canonical_intent.target_agent]
            if agent_errors:
                results.append(VerificationResult(
                    status="failed",
                    action=state.canonical_intent.action,
                    message="The executable agent reported a failure.",
                    evidence=[agent_errors[-1].message],
                ))
        if not results:
            results.append(VerificationResult(status="unknown", message="No executable action required."))
        failures = [] if all(r.status in {"success", "unknown"} for r in results) else [
            self.failure(state, FailureCategory.VERIFICATION, "One or more actions failed verification")
        ]
        return StateUpdate(values={"verification_results": results, "status": "verified"}, failures=failures)
