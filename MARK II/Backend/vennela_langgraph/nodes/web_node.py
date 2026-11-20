from vennela_langgraph.core.contracts import Provenance, StateUpdate, WebEvidence
from vennela_langgraph.core.errors import FailureCategory
from collections.abc import Mapping
from ._base import BaseNode


class WebNode(BaseNode):
    name = "web"

    def __init__(self, telemetry, agent):
        super().__init__(telemetry)
        self.agent = agent

    def execute(self, state):
        try:
            if hasattr(self.agent, "search_with_context"):
                result = self.agent.search_with_context(
                    state.original_request,
                    state.request_id,
                )
            else:
                result = self.agent.search(state.original_request)
            if isinstance(result, Mapping):
                evidence = [
                    self._to_evidence(item)
                    for item in result.get("evidence", [])
                ]
                return StateUpdate(values={
                    "web_evidence": evidence,
                    "tool_results": {"web": dict(result)},
                })
            return StateUpdate(values={"web_evidence": result})
        except Exception as exc:
            return StateUpdate(failures=[self.failure(state, FailureCategory.NETWORK, str(exc), True)])

    @staticmethod
    def _to_evidence(item):
        return WebEvidence(
            source_url=item["source_url"],
            title=item["title"],
            extracted_facts=list(item.get("extracted_facts", [])),
            confidence=float(item.get("confidence", 0.0)),
            provenance=Provenance(**item["provenance"]),
            uncertainties=list(item.get("uncertainties", [])),
        )
