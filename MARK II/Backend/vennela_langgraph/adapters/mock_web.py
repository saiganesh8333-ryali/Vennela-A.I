from datetime import datetime, timezone
from vennela_langgraph.core.contracts import Provenance, WebEvidence


class MockWebAgent:
    def __init__(self, fail: bool = False, partial: bool = False):
        self.fail, self.partial = fail, partial

    def search(self, request: str) -> list[WebEvidence]:
        if self.fail:
            raise RuntimeError("web provider unavailable")
        sources = [
            WebEvidence(source_url="https://example.test/one", title="Primary source",
                        extracted_facts=["The lab uses explicit typed state."], confidence=0.92,
                        provenance=Provenance(source="mock-web", method="deterministic")),
            WebEvidence(source_url="https://example.test/two", title="Secondary source",
                        extracted_facts=["Verification records structured outcomes."], confidence=0.78,
                        provenance=Provenance(source="mock-web", method="deterministic"),
                        uncertainties=["This source is a prototype citation."]),
        ]
        return sources[:1] if self.partial else sources
