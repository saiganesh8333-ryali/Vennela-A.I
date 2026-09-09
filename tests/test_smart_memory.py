import pytest

from memory import AuthContext, InMemoryMemoryRepository, MemoryAPI, MemoryDomain, SmartMemory


@pytest.fixture
def smart():
    return SmartMemory(MemoryAPI(InMemoryMemoryRepository()))


def test_classifies_and_creates_a_canonical_preference(smart):
    context = AuthContext("boss")
    decision = smart.store(context, "I like robotics")

    assert decision.action == "create"
    assert decision.record.domain is MemoryDomain.BOSS_PERSONAL
    assert decision.record.category.value == "Preference"
    assert decision.record.content == {
        "text": "I like robotics", "importance": 0.7, "classification": "Preference",
    }


def test_transient_question_is_ignored(smart):
    decision = smart.store(AuthContext("boss"), "Can you explain embeddings?")

    assert decision.action == "ignore"
    assert decision.reason == "transient"
    assert decision.record is None


def test_exact_duplicate_updates_instead_of_creating(smart):
    context = AuthContext("boss")
    first = smart.store(context, "Remember this: I prefer Python.")
    second = smart.store(context, "Remember this: I prefer Python.")

    records = smart.api.retrieve(context)
    assert first.action == "create"
    assert second.action == "update"
    assert second.duplicate_of == first.record.memory_id
    assert len(records) == 1


def test_session_memory_is_scoped_to_the_session(smart):
    context = AuthContext("boss", session_id="session-1")
    decision = smart.store(context, "Remember this: the meeting starts at nine.",
                           domain="session", session_id="session-1")

    assert decision.record.domain is MemoryDomain.SESSION
    assert decision.record.session_id == "session-1"
