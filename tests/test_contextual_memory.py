from datetime import datetime, timedelta, timezone

import pytest

from memory import (
    AuthContext,
    ContextualMemory,
    InMemoryMemoryRepository,
    MemoryAPI,
    MemoryCategory,
    MemoryDomain,
    MemoryRecord,
)


@pytest.fixture
def memory_api():
    return MemoryAPI(InMemoryMemoryRepository())


def add(memory_api, context, text, category="Fact", domain="boss_personal", session_id=None,
        importance=0.5, memory_id=None):
    return memory_api.create(
        context,
        {"text": text, "importance": importance, "classification": category},
        category,
        domain,
        session_id,
        memory_id,
    )


def test_same_session_memory_is_recalled_and_prioritized(memory_api):
    context = AuthContext("boss", session_id="s1")
    add(memory_api, context, "robotics project note", "Project")
    session = add(memory_api, context, "robotics project meeting", "Event", "session", "s1")

    records = ContextualMemory(memory_api).select(context, "robotics project", limit=2)

    assert records[0].memory_id == session.memory_id
    assert {record.domain for record in records} == {MemoryDomain.BOSS_PERSONAL, MemoryDomain.SESSION}


def test_different_session_memory_is_excluded(memory_api):
    owner = AuthContext("boss", session_id="s1")
    add(memory_api, owner, "robotics private session", "Event", "session", "s1")
    other_session = AuthContext("boss", session_id="s2")

    assert ContextualMemory(memory_api).select(other_session, "robotics") == []


def test_long_term_memory_survives_session_changes(memory_api):
    first = AuthContext("boss", session_id="s1")
    add(memory_api, first, "favorite robotics project", "Project")
    second = AuthContext("boss", session_id="s2")

    records = ContextualMemory(memory_api).select(second, "robotics project")

    assert [record.domain for record in records] == [MemoryDomain.BOSS_PERSONAL]


def test_core_domain_requires_core_scope(memory_api):
    core = AuthContext("system", scopes=frozenset({"memory:core"}))
    add(memory_api, core, "supabase architecture", domain="vennela_core")
    selector = ContextualMemory(memory_api)

    assert selector.select(AuthContext("system"), "supabase", include_core=True) == []
    assert selector.select(core, "supabase", include_core=True)[0].domain is MemoryDomain.VENNELA_CORE


def test_importance_and_recency_rank_relevant_memories(memory_api):
    context = AuthContext("boss")
    old = datetime.now(timezone.utc) - timedelta(days=60)
    repository = memory_api.repository
    repository.create(MemoryRecord("old", "boss", MemoryDomain.BOSS_PERSONAL, MemoryCategory.PROJECT,
                                   {"text": "robotics project", "importance": 0.2}, None, old, old))
    recent = add(memory_api, context, "robotics project", "Project", importance=0.9, memory_id="recent")

    records = ContextualMemory(memory_api).select(context, "robotics project")

    assert records[0].memory_id == recent.memory_id


def test_irrelevant_records_are_excluded_and_results_are_bounded(memory_api):
    context = AuthContext("boss")
    for index in range(8):
        add(memory_api, context, f"robotics project item {index}", "Project", memory_id=f"m{index}")
    add(memory_api, context, "cooking recipe", memory_id="irrelevant")

    records = ContextualMemory(memory_api).select(context, "robotics project", limit=3)

    assert len(records) == 3
    assert all(record.memory_id != "irrelevant" for record in records)
