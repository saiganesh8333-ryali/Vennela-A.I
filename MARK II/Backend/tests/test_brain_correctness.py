from __future__ import annotations

from memory import AuthContext, IntelligentMemory, InMemoryMemoryRepository, MemoryAPI, SmartMemory
from production_langgraph_adapter import _ProductionReasoningAdapter
from vennela_langgraph.core.contracts import Provenance, WebEvidence
from vennela_langgraph.core.errors import BrainFailure, FailureCategory
from vennela_langgraph.core.intent import resolve_intent
from vennela_langgraph.core.state import VennelaState


def _memory_service():
    return MemoryAPI(InMemoryMemoryRepository())


def _context(user_id: str, session_id: str):
    return AuthContext(user_id=user_id, authenticated=True, session_id=session_id)


def test_explicit_memory_is_retrieved_across_sessions_and_isolated_by_user():
    api = _memory_service()
    writer = _context("user-one", "write-session")
    SmartMemory(api).store(
        writer,
        "Remember my father's name is Nageswara Rao.",
        domain="boss_personal",
    )

    reader = IntelligentMemory(api, embedder=lambda text: [1.0 if token in text.lower() else 0.0 for token in ("father", "name", "nageswara", "rao")])
    same_session = reader.retrieve_semantic(
        _context("user-one", "write-session"),
        "What is my father's name?",
        min_similarity=0.05,
    )
    new_session = reader.retrieve_semantic(
        _context("user-one", "independent-session"),
        "What is my father's name?",
        min_similarity=0.05,
    )
    other_user = reader.retrieve_semantic(
        _context("user-two", "independent-session"),
        "What is my father's name?",
        min_similarity=0.0,
    )

    assert same_session and new_session
    assert "Nageswara Rao" in new_session[0].record.content["text"]
    assert other_user == []


def test_latest_question_routes_to_web_and_preserves_evidence_in_reasoning_context():
    intent = resolve_intent("What are the latest AI developments?")
    assert intent.requires_web is True
    assert "web.research" in intent.requested_capabilities

    evidence = WebEvidence(
        source_url="https://example.test/ai",
        title="Mock AI source",
        extracted_facts=["A verified current finding."],
        confidence=1.0,
        provenance=Provenance(source="mock", method="test"),
    )

    class CapturingLLM:
        def __init__(self):
            self.system_instruction = None

        def route_text(self, prompt, **kwargs):
            self.system_instruction = kwargs["system_instruction"]
            return {
                "text": "grounded answer",
                "model_id": "test",
                "provider": "test",
                "latency_ms": 0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    llm = CapturingLLM()
    adapter = _ProductionReasoningAdapter(llm, "base policy", [{"role": "user", "content": "latest"}])
    state = VennelaState(
        original_request="What are the latest AI developments?",
        canonical_intent=intent,
        memory_context=["User prefers concise answers"],
        web_evidence=[evidence],
    )
    adapter.reason(state)

    assert "User prefers concise answers" in llm.system_instruction
    assert "A verified current finding." in llm.system_instruction
    assert "Fresh web evidence" in llm.system_instruction


def test_memory_and_web_failures_are_explicitly_grounded_for_final_reasoning():
    intent = resolve_intent("What are the latest AI developments?")

    class CapturingLLM:
        def __init__(self):
            self.system_instruction = None

        def route_text(self, prompt, **kwargs):
            self.system_instruction = kwargs["system_instruction"]
            return {
                "text": "I cannot verify current data.",
                "model_id": "test",
                "provider": "test",
                "latency_ms": 0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    llm = CapturingLLM()
    adapter = _ProductionReasoningAdapter(llm, None, [])
    state = VennelaState(
        original_request="What are the latest AI developments?",
        canonical_intent=intent,
        errors=[BrainFailure(
            category=FailureCategory.NETWORK,
            message="provider unavailable",
            node="web",
            request_id="request-1",
            recoverable=True,
            attempt=1,
        )],
    )
    adapter.reason(state)

    assert "current data could not be retrieved" in llm.system_instruction
    assert "web: provider unavailable" in llm.system_instruction
