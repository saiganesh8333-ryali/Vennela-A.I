from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest

from core.temporal.context import TemporalContext
from core.nexus_intent import NexusIntentClassifier, NexusIntent, execute_nexus_intent
from vennela_langgraph.core.intent import resolve_intent
from vennela_langgraph.core.state import VennelaState
from vennela_langgraph.core.contracts import WebEvidence, Provenance
from vennela_langgraph.core.errors import BrainFailure, FailureCategory
from production_langgraph_adapter import _ProductionReasoningAdapter


def test_what_year_is_it_deterministic_temporal_handling():
    fixed = datetime(2026, 9, 25, 18, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    temporal = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    classifier = NexusIntentClassifier(temporal)
    
    # Check variations
    for query in ["What year is it?", "What year is this?", "What is the current year?", "Which year is it?"]:
        res = classifier.classify(query)
        assert res.intent == NexusIntent.DATE_QUERY, f"Failed on query: {query}"
        assert res.entities.get("query_type") == "year"
        
        # Execute nexus intent
        output = execute_nexus_intent(res, None, None, "test-user", temporal)
        assert output == "It is 2026.", f"Expected 'It is 2026.' but got '{output}' for {query}"


def test_what_is_todays_date_deterministic_temporal_handling():
    fixed = datetime(2026, 9, 25, 18, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    temporal = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    classifier = NexusIntentClassifier(temporal)
    
    res = classifier.classify("What is today's date?")
    assert res.intent == NexusIntent.DATE_QUERY
    assert res.entities.get("query_type") == "date"
    
    output = execute_nexus_intent(res, None, None, "test-user", temporal)
    assert "25 September 2026" in output
    assert "Friday" in output


def test_current_chief_minister_requires_web_routing():
    intent = resolve_intent("Who is the current Chief Minister of Andhra Pradesh?")
    assert intent.requires_web is True
    assert "web.research" in intent.requested_capabilities


def test_latest_ai_developments_preserves_web_routing():
    intent = resolve_intent("What are the latest AI developments?")
    assert intent.requires_web is True
    assert "web.research" in intent.requested_capabilities


def test_current_web_failure_does_not_invent_answer():
    intent = resolve_intent("Who is the current Chief Minister of Andhra Pradesh?")
    assert intent.requires_web is True

    class CapturingLLM:
        def __init__(self):
            self.system_instruction = None

        def route_text(self, prompt, **kwargs):
            self.system_instruction = kwargs["system_instruction"]
            return {
                "text": "I cannot verify current information.",
                "model_id": "test-model",
                "provider": "test-provider",
                "latency_ms": 0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    llm = CapturingLLM()
    adapter = _ProductionReasoningAdapter(llm, "Base prompt", [{"role": "user", "content": "test"}])
    state = VennelaState(
        original_request="Who is the current Chief Minister of Andhra Pradesh?",
        canonical_intent=intent,
        web_evidence=[],
        errors=[BrainFailure(
            category=FailureCategory.NETWORK,
            message="search provider unreachable",
            node="web",
            request_id="test-req-fail",
            recoverable=True,
            attempt=1,
        )],
    )
    adapter.reason(state)

    assert "Fresh web retrieval failed or returned no evidence." in llm.system_instruction
    assert "do not invent a current answer" in llm.system_instruction
    assert "web: search provider unreachable" in llm.system_instruction


def test_temporal_context_injected_into_reasoning_system_instruction():
    class CapturingLLM:
        def __init__(self):
            self.system_instruction = None

        def route_text(self, prompt, **kwargs):
            self.system_instruction = kwargs["system_instruction"]
            return {
                "text": "reasoning output",
                "model_id": "test-model",
                "provider": "test-provider",
                "latency_ms": 0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    llm = CapturingLLM()
    adapter = _ProductionReasoningAdapter(llm, "Base personality instruction", [])
    state = VennelaState(
        original_request="What is the context?",
        canonical_intent=resolve_intent("Hello"),
    )
    adapter.reason(state)

    assert "Runtime Temporal Context:" in llm.system_instruction
    assert "Current Date:" in llm.system_instruction
    assert "Current Year:" in llm.system_instruction
    assert "For relative temporal questions, trust the supplied runtime temporal context." in llm.system_instruction
    assert "Do not answer the current year/date/time from pretrained knowledge." in llm.system_instruction


# ---------------------------------------------------------------------------
# Test G – Existing memory regression (father-name / cross-session fix)
# ---------------------------------------------------------------------------

def test_memory_regression_father_name_cross_session():
    """Verify the existing brain correctness memory fix is still intact.

    Stores a fact in one session, retrieves it from a different session under
    the same user, and confirms another user cannot access it.
    """
    from memory import (
        AuthContext,
        IntelligentMemory,
        InMemoryMemoryRepository,
        MemoryAPI,
        SmartMemory,
    )

    api = MemoryAPI(InMemoryMemoryRepository())
    writer_ctx = AuthContext(user_id="user-one", authenticated=True, session_id="write-session")
    SmartMemory(api).store(
        writer_ctx,
        "Remember my father's name is Nageswara Rao.",
        domain="boss_personal",
    )

    def _embedder(text):
        tokens = ("father", "name", "nageswara", "rao")
        return [1.0 if tok in text.lower() else 0.0 for tok in tokens]

    reader = IntelligentMemory(api, embedder=_embedder)

    # Same user, different session — should still recall
    new_session_results = reader.retrieve_semantic(
        AuthContext(user_id="user-one", authenticated=True, session_id="independent-session"),
        "What is my father's name?",
        min_similarity=0.05,
    )
    assert new_session_results, "Cross-session memory retrieval failed"
    assert "Nageswara Rao" in new_session_results[0].record.content["text"]

    # Different user — must be empty
    other_user_results = reader.retrieve_semantic(
        AuthContext(user_id="user-two", authenticated=True, session_id="independent-session"),
        "What is my father's name?",
        min_similarity=0.0,
    )
    assert other_user_results == [], "Memory leaked across user boundary"


# ---------------------------------------------------------------------------
# Edge-case temporal routing tests (pure temporal must not go to web)
# ---------------------------------------------------------------------------

def test_what_is_today_does_not_route_to_web():
    """'What is today?' is a server-answerable temporal query; must NOT require web."""
    intent = resolve_intent("What is today?")
    assert intent.requires_web is False, (
        "'What is today?' must not route to web; got requires_web=True"
    )


def test_tell_me_todays_date_does_not_route_to_web():
    """'Tell me today's date' is deterministic; must NOT require web research."""
    for query in ("Tell me today's date", "Tell me the date"):
        intent = resolve_intent(query)
        assert intent.requires_web is False, (
            f"{query!r} must not route to web; got requires_web=True"
        )


def test_nexus_classifies_what_is_today_as_date_query():
    """'What is today?' must be intercepted by NEXUS as a DATE_QUERY."""
    fixed = datetime(2026, 9, 25, 18, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    temporal = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    classifier = NexusIntentClassifier(temporal)

    res = classifier.classify("What is today?")
    assert res.intent == NexusIntent.DATE_QUERY
    output = execute_nexus_intent(res, None, None, "test-user", temporal)
    assert "25 September 2026" in output


def test_nexus_classifies_tell_me_todays_date_as_date_query():
    """'Tell me today's date' / 'Tell me the date' must be caught by NEXUS."""
    fixed = datetime(2026, 9, 25, 18, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    temporal = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    classifier = NexusIntentClassifier(temporal)

    for query in ("Tell me today's date", "Tell me the date"):
        res = classifier.classify(query)
        assert res.intent == NexusIntent.DATE_QUERY, (
            f"{query!r} was not classified as DATE_QUERY"
        )
        output = execute_nexus_intent(res, None, None, "test-user", temporal)
        assert "25 September 2026" in output, (
            f"Expected date string in output for {query!r}, got: {output!r}"
        )
