from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from memory import (
    AuthContext,
    ConflictResult,
    ConsolidationResult,
    InMemoryMemoryRepository,
    IntelligentMemory,
    MemoryAPI,
    MemoryAuthorizationError,
    MemoryCategory,
    MemoryDomain,
    MemoryRecord,
    RelationalMemory,
    ScoredMemory,
)
from memory.embedding_engine import get_embedding


@pytest.fixture
def memory_api():
    return MemoryAPI(InMemoryMemoryRepository())


@pytest.fixture
def relational(memory_api):
    return RelationalMemory(memory_api)


@pytest.fixture
def intelligent(memory_api, relational):
    return IntelligentMemory(memory_api, relational=relational)


def add(
    memory_api,
    context,
    text,
    category="Fact",
    domain="boss_personal",
    session_id=None,
    importance=0.5,
    memory_id=None,
    updated_at=None,
):
    record = memory_api.create(
        context,
        {"text": text, "importance": importance, "classification": category},
        category,
        domain,
        session_id,
        memory_id,
    )
    if updated_at is not None:
        raw_record = memory_api.repository.get(record.memory_id)
        fixed_record = MemoryRecord(
            raw_record.memory_id,
            raw_record.owner_id,
            raw_record.domain,
            raw_record.category,
            raw_record.content,
            raw_record.session_id,
            raw_record.created_at,
            updated_at,
            raw_record.active,
        )
        memory_api.repository.update(fixed_record)
        return fixed_record
    return record


# ============================================================================
# EMBEDDING TESTS
# ============================================================================

def test_embedding_generation_and_properties():
    vec = get_embedding("Artificial intelligence and robotics")
    assert isinstance(vec, list)
    assert len(vec) == 128
    assert all(isinstance(x, float) for x in vec)

    # Empty and invalid inputs return stable zero vector
    assert get_embedding("") == [0.0] * 128
    assert get_embedding(None) == [0.0] * 128


def test_embedding_cosine_similarity():
    v1 = get_embedding("machine learning with python")
    v2 = get_embedding("machine learning with python")
    v3 = get_embedding("completely unrelated baking cake sugar")

    sim_identical = IntelligentMemory._cosine_similarity(v1, v2)
    sim_unrelated = IntelligentMemory._cosine_similarity(v1, v3)

    assert sim_identical > 0.99
    assert sim_identical > sim_unrelated


# ============================================================================
# SEMANTIC RETRIEVAL TESTS
# ============================================================================

def test_semantic_retrieval_finds_relevant_memory(memory_api, intelligent):
    context = AuthContext("boss")
    rec1 = add(memory_api, context, "I develop machine learning algorithms in Python", "Skill")
    rec2 = add(memory_api, context, "I like Italian pasta with marinara sauce", "Preference")

    results = intelligent.retrieve_semantic(context, "Python machine learning coding", limit=5)

    assert len(results) >= 1
    assert results[0].record.memory_id == rec1.memory_id
    assert results[0].semantic_similarity > 0.3


def test_semantic_retrieval_bounded_by_limit(memory_api, intelligent):
    context = AuthContext("boss")
    for i in range(10):
        add(memory_api, context, f"Autonomous drone navigation waypoint {i}", "Project", memory_id=f"m{i}")

    results = intelligent.retrieve_semantic(context, "drone navigation", limit=3)
    assert len(results) == 3


def test_semantic_retrieval_enforces_authorization(memory_api, intelligent):
    boss = AuthContext("boss")
    intruder = AuthContext("intruder")

    add(memory_api, boss, "Boss top secret neural network architecture", "Project")

    intruder_results = intelligent.retrieve_semantic(intruder, "neural network architecture", limit=5)
    assert intruder_results == []


def test_semantic_retrieval_includes_core_when_authorized(memory_api, intelligent):
    core_context = AuthContext("system", scopes=frozenset({"memory:core"}))
    add(memory_api, core_context, "Supabase cluster configuration and schema", "Fact", domain="vennela_core")

    # Caller without scope cannot retrieve core
    boss = AuthContext("boss")
    boss_results = intelligent.retrieve_semantic(boss, "Supabase configuration", include_core=True)
    assert boss_results == []

    # Caller with scope retrieves core
    core_results = intelligent.retrieve_semantic(core_context, "Supabase configuration", include_core=True)
    assert len(core_results) == 1
    assert core_results[0].record.domain is MemoryDomain.VENNELA_CORE


# ============================================================================
# RELEVANCE RANKING TESTS
# ============================================================================

def test_ranking_semantic_similarity_influences_score(memory_api, intelligent):
    context = AuthContext("boss")
    m_high = add(memory_api, context, "Expert in deep neural network optimization", "Skill")
    m_low = add(memory_api, context, "Casual hobby playing chess on weekends", "Interest")

    ranked = intelligent.rank(context, "neural network optimization", [m_high, m_low])
    assert ranked[0].record.memory_id == m_high.memory_id
    assert ranked[0].score > ranked[1].score


def test_ranking_importance_influences_score(memory_api, intelligent):
    context = AuthContext("boss")
    # Same topic text, different importance
    m_low = add(memory_api, context, "autonomous drone mission", "Project", importance=0.2, memory_id="low")
    m_high = add(memory_api, context, "autonomous drone mission", "Project", importance=0.9, memory_id="high")

    ranked = intelligent.rank(context, "autonomous drone", [m_low, m_high])
    assert ranked[0].record.memory_id == "high"
    assert ranked[0].importance == 0.9


def test_ranking_recency_influences_score(memory_api, intelligent):
    context = AuthContext("boss")
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=90)

    m_old = add(memory_api, context, "robotics arm gripper", "Project", updated_at=old_time, memory_id="old")
    m_new = add(memory_api, context, "robotics arm gripper", "Project", updated_at=now, memory_id="new")

    ranked = intelligent.rank(context, "robotics gripper", [m_old, m_new], now=now)
    assert ranked[0].record.memory_id == "new"
    assert ranked[0].recency > ranked[1].recency


def test_ranking_session_boost(memory_api, intelligent):
    context = AuthContext("boss", session_id="s1")
    now = datetime.now(timezone.utc)
    m_personal = add(memory_api, context, "deploy kubernetes cluster", "Task", domain="boss_personal", updated_at=now, memory_id="p1")
    m_session = add(memory_api, context, "deploy kubernetes cluster", "Task", domain="session", session_id="s1", updated_at=now, memory_id="s1")

    ranked = intelligent.rank(context, "kubernetes cluster", [m_personal, m_session], session_id="s1", now=now)
    # Session memory receives boost in active session
    assert ranked[0].record.memory_id == "s1"
    assert ranked[0].session_boost == 0.10


def test_ranking_relational_boost(memory_api, relational, intelligent):
    context = AuthContext("boss")
    proj = add(memory_api, context, "Project Apollo", "Project", memory_id="p_apollo")
    goal1 = add(memory_api, context, "Moon landing trajectory", "Goal", memory_id="g_apollo")
    goal2 = add(memory_api, context, "Moon landing trajectory", "Goal", memory_id="g_isolated")

    # Connect goal1 to proj in L4
    relational.create_relationship(context, proj.memory_id, goal1.memory_id, "PROJECT_GOAL")

    ranked = intelligent.rank(context, "Moon landing", [proj, goal1, goal2])
    goal1_scored = next(s for s in ranked if s.record.memory_id == "g_apollo")
    goal2_scored = next(s for s in ranked if s.record.memory_id == "g_isolated")

    assert goal1_scored.relational_boost > 0.0
    assert goal2_scored.relational_boost == 0.0
    assert goal1_scored.score > goal2_scored.score


def test_ranking_deterministic_ordering(memory_api, intelligent):
    context = AuthContext("boss")
    now = datetime.now(timezone.utc)
    m1 = add(memory_api, context, "data pipeline spark", "Project", importance=0.8, updated_at=now, memory_id="m1")
    m2 = add(memory_api, context, "data pipeline spark", "Project", importance=0.8, updated_at=now, memory_id="m2")

    ranked_1 = intelligent.rank(context, "spark", [m1, m2], now=now)
    ranked_2 = intelligent.rank(context, "spark", [m2, m1], now=now)

    assert [s.record.memory_id for s in ranked_1] == [s.record.memory_id for s in ranked_2]


# ============================================================================
# MEMORY CONSOLIDATION TESTS
# ============================================================================

def test_consolidation_merges_redundant_memories_safely(memory_api, intelligent):
    context = AuthContext("boss")
    # Two almost identical memories in same category
    m1 = add(memory_api, context, "I prefer developing in Python for all backend services", "Preference", importance=0.6, memory_id="m1")
    m2 = add(memory_api, context, "I prefer developing in Python for all backend services", "Preference", importance=0.8, memory_id="m2")

    results = intelligent.consolidate(context, domain="boss_personal", similarity_threshold=0.85)

    assert len(results) == 1
    res = results[0]
    # Primary record selected (m2 had higher importance)
    assert res.primary_record.memory_id == "m2"
    assert len(res.consolidated_records) == 1
    assert res.consolidated_records[0].memory_id == "m1"

    # Verify primary record retains max importance and increased reinforcement count
    updated_primary = memory_api.repository.get("m2")
    assert updated_primary.content["importance"] == 0.8
    assert updated_primary.content["reinforcement_count"] == 2
    assert "m1" in updated_primary.content["consolidated_from"]

    # Secondary record was non-destructively deactivated
    deactivated = memory_api.repository.get("m1")
    assert deactivated.active is False


def test_consolidation_ignores_distinct_memories(memory_api, intelligent):
    context = AuthContext("boss")
    add(memory_api, context, "I like Python programming", "Preference")
    add(memory_api, context, "I like rock climbing in Utah", "Preference")

    results = intelligent.consolidate(context, domain="boss_personal", similarity_threshold=0.90)
    assert results == []


# ============================================================================
# CONFLICT RESOLUTION TESTS
# ============================================================================

def test_conflict_resolution_supersedes_older_contradiction(memory_api, intelligent):
    context = AuthContext("boss")
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    new_time = datetime.now(timezone.utc)

    # Older memory: likes coffee; Newer memory: hates coffee
    m_old = add(memory_api, context, "I love coffee in the morning", "Preference", updated_at=old_time, memory_id="old_pref")
    m_new = add(memory_api, context, "I hate coffee in the morning", "Preference", updated_at=new_time, memory_id="new_pref")

    results = intelligent.resolve_conflicts(context, domain="boss_personal")

    assert len(results) == 1
    res = results[0]
    assert res.status == "superseded"
    assert res.winning_record.memory_id == "new_pref"
    assert res.conflicting_records[0].memory_id == "old_pref"

    # Verify older memory deactivated and newer memory recorded supersession
    old_rec = memory_api.repository.get("old_pref")
    assert old_rec.active is False
    new_rec = memory_api.repository.get("new_pref")
    assert new_rec.content["supersedes"] == "old_pref"


def test_conflict_resolution_preserves_ambiguous_contradiction(memory_api, intelligent):
    context = AuthContext("boss")
    same_time = datetime.now(timezone.utc)

    # Opposing preferences with identical timestamp and equal importance
    m1 = add(memory_api, context, "I love drinking tea", "Preference", importance=0.8, updated_at=same_time, memory_id="ambig_1")
    m2 = add(memory_api, context, "I hate drinking tea", "Preference", importance=0.8, updated_at=same_time, memory_id="ambig_2")

    results = intelligent.resolve_conflicts(context, domain="boss_personal")

    assert len(results) == 1
    res = results[0]
    assert res.status == "ambiguous"
    assert res.winning_record is None
    assert len(res.conflicting_records) == 2

    # Both records remain active
    rec1 = memory_api.repository.get("ambig_1")
    rec2 = memory_api.repository.get("ambig_2")
    assert rec1.active is True
    assert rec2.active is True
    assert rec1.content.get("conflict_status") == "ambiguous"
    assert rec2.content.get("conflict_status") == "ambiguous"


def test_conflict_resolution_mutually_exclusive_attributes(memory_api, intelligent):
    context = AuthContext("boss")
    old_time = datetime.now(timezone.utc) - timedelta(days=5)
    new_time = datetime.now(timezone.utc)

    # Favorite language attribute changed
    m1 = add(memory_api, context, "my favorite language is Python", "Preference", updated_at=old_time, memory_id="fav_py")
    m2 = add(memory_api, context, "my favorite language is Rust", "Preference", updated_at=new_time, memory_id="fav_rust")

    results = intelligent.resolve_conflicts(context, domain="boss_personal")
    assert len(results) == 1
    assert results[0].status == "superseded"
    assert results[0].winning_record.memory_id == "fav_rust"


# ============================================================================
# SCHEMA & CONTRACT TESTS
# ============================================================================

def test_intelligent_memory_schema_contract():
    schema = Path(__file__).parents[1] / "migrations" / "004_intelligent_memory.sql"
    assert schema.exists()
    sql = schema.read_text()
    assert "memories_content_gin_idx" in sql
