from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from memory import (
    AuthContext,
    InMemoryMemoryRepository,
    IntelligentMemory,
    JarvisMemory,
    MemoryAPI,
    MemoryAuthorizationError,
    MemoryCategory,
    MemoryDomain,
    MemoryLifecycleState,
    MemoryNotFoundError,
    MemoryRecord,
    PreferenceEvolutionResult,
    ProactiveMemory,
    ProactiveRecallPolicy,
    ProactiveRecallResult,
    RelationalMemory,
    UserModel,
)


@pytest.fixture
def memory_api():
    return MemoryAPI(InMemoryMemoryRepository())


@pytest.fixture
def relational(memory_api):
    return RelationalMemory(memory_api)


@pytest.fixture
def intelligent(memory_api, relational):
    return IntelligentMemory(memory_api, relational=relational)


@pytest.fixture
def jarvis(memory_api, relational, intelligent):
    policy = ProactiveRecallPolicy(min_score=0.50, min_semantic_similarity=0.20, max_recall=2, cooldown_seconds=60.0)
    return JarvisMemory(memory_api, relational=relational, intelligent=intelligent, policy=policy)


def add(
    memory_api,
    context,
    text,
    category="Fact",
    domain="boss_personal",
    session_id=None,
    importance=0.8,
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
# PROACTIVE RECALL TESTS
# ============================================================================

def test_proactive_recall_surfaces_relevant_memory(memory_api, jarvis):
    context = AuthContext("boss")
    proj = add(memory_api, context, "Leading Project Antigravity for autonomous coding", "Project", importance=0.9)
    unrelated = add(memory_api, context, "Likes pepperoni pizza on Fridays", "Preference", importance=0.4)

    result = jarvis.proactive_recall(context, "working on autonomous coding agent architecture")

    assert len(result) >= 1
    recalled_ids = [m.record.memory_id for m in result]
    assert proj.memory_id in recalled_ids
    assert unrelated.memory_id not in recalled_ids
    assert result[0].score >= jarvis.policy.min_score
    assert len(result[0].reason) > 0


def test_proactive_recall_rejects_low_confidence(memory_api, jarvis):
    context = AuthContext("boss")
    add(memory_api, context, "Baking sourdough bread at home", "Interest", importance=0.3)

    # Completely unrelated context
    result = jarvis.proactive_recall(context, "distributed database transactions and Raft consensus")
    assert len(result) == 0


def test_proactive_recall_bounded_by_max_recall(memory_api, jarvis):
    context = AuthContext("boss")
    for i in range(10):
        add(memory_api, context, f"Autonomous agent swarm task coordinator {i}", "Project", importance=0.9, memory_id=f"p{i}")

    result = jarvis.proactive_recall(context, "autonomous agent swarm coordinator")
    assert len(result) <= jarvis.policy.max_recall
    assert len(result) == 2


def test_proactive_recall_anti_spam_cooldown(memory_api, jarvis):
    context = AuthContext("boss")
    now = datetime.now(timezone.utc)
    proj = add(memory_api, context, "Project Jarvis Memory Intelligence architecture", "Project", importance=0.9)

    # First recall succeeds
    res1 = jarvis.proactive_recall(context, "Jarvis memory intelligence", now=now)
    assert len(res1) == 1
    assert res1[0].record.memory_id == proj.memory_id

    # Immediate second recall with same context is suppressed by cooldown
    res2 = jarvis.proactive_recall(context, "Jarvis memory intelligence", now=now + timedelta(seconds=10))
    assert len(res2) == 0
    assert res2.suppressed_count >= 1

    # After cooldown expires (60 seconds), it can be recalled again
    res3 = jarvis.proactive_recall(context, "Jarvis memory intelligence", now=now + timedelta(seconds=70))
    assert len(res3) == 1
    assert res3[0].record.memory_id == proj.memory_id


def test_proactive_recall_suppresses_in_context_duplicates(memory_api, jarvis):
    context = AuthContext("boss")
    text = "Deploying production cluster with Kubernetes on AWS"
    add(memory_api, context, text, "Project", importance=0.9)

    # Context already explicitly contains the memory content verbatim
    result = jarvis.proactive_recall(context, f"As we know, {text}, what are the next steps?")
    assert len(result) == 0
    assert result.suppressed_count >= 1


def test_proactive_recall_relational_boost(memory_api, relational, jarvis):
    context = AuthContext("boss")
    proj = add(memory_api, context, "Project Apollo mission", "Project", importance=0.8, memory_id="apollo_p")
    goal = add(memory_api, context, "Land on lunar surface", "Goal", importance=0.8, memory_id="apollo_g")

    # Link in Level 4
    relational.create_relationship(context, proj.memory_id, goal.memory_id, "PROJECT_GOAL")

    result = jarvis.proactive_recall(context, "Project Apollo mission goal")
    assert len(result) >= 1
    # Check that reason reflects connected nature or high relevance
    assert any("apollo" in m.record.memory_id for m in result)


# ============================================================================
# PREFERENCE EVOLUTION TESTS
# ============================================================================

def test_preference_evolution_active_and_historical(memory_api, jarvis):
    context = AuthContext("boss")

    # Day 1: User prefers Python
    res1 = jarvis.evolve_preference(context, "I prefer Python for backend services", topic="language", importance=0.8)
    assert res1.action_taken == "created"
    assert res1.current_preference is not None
    id_python = res1.current_preference.memory_id

    # Day 2: User explicitly changes preference to Rust
    res2 = jarvis.evolve_preference(context, "I prefer Rust for backend services", topic="language", importance=0.9)
    assert res2.action_taken == "evolved"
    assert res2.current_preference.content["text"] == "I prefer Rust for backend services"
    assert res2.current_preference.active is True

    # Previous Python preference is now historical, not active, but NOT deleted
    old_python = memory_api.repository.get(id_python)
    assert old_python.active is False
    assert old_python.content["evolution_state"] == "historical"
    assert old_python.content["superseded_by"] == res2.current_preference.memory_id

    # Query complete preference history
    history = jarvis.get_preference_history(context, topic="language")
    assert history.current_preference.memory_id == res2.current_preference.memory_id
    assert len(history.historical_preferences) == 1
    assert history.historical_preferences[0].memory_id == id_python


def test_preference_evolution_duplicate_reinforced(memory_api, jarvis):
    context = AuthContext("boss")
    res1 = jarvis.evolve_preference(context, "I prefer Dark Mode in IDE", topic="theme")
    assert res1.action_taken == "created"

    res2 = jarvis.evolve_preference(context, "I prefer Dark Mode in IDE", topic="theme")
    assert res2.action_taken == "reinforced"
    assert res2.current_preference.content["reinforcement_count"] == 2


# ============================================================================
# MEMORY LIFECYCLE & OBSOLESCENCE TESTS
# ============================================================================

def test_lifecycle_state_transitions(memory_api, jarvis):
    context = AuthContext("boss")
    rec = add(memory_api, context, "Temporary migration task", "Task")

    # ACTIVE -> REINFORCED
    r_reinf = jarvis.transition_lifecycle(context, rec.memory_id, MemoryLifecycleState.REINFORCED, reason="re-stated")
    assert r_reinf.active is True
    assert r_reinf.content["lifecycle_state"] == "REINFORCED"

    # REINFORCED -> SUPERSEDED
    r_sup = jarvis.transition_lifecycle(context, rec.memory_id, MemoryLifecycleState.SUPERSEDED, reason="replaced")
    assert r_sup.active is False
    assert r_sup.content["lifecycle_state"] == "SUPERSEDED"

    # Invalid transition from SUPERSEDED directly to REINFORCED
    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        jarvis.transition_lifecycle(context, rec.memory_id, MemoryLifecycleState.REINFORCED)


def test_mark_obsolete_preserves_metadata(memory_api, jarvis):
    context = AuthContext("boss")
    rec = add(memory_api, context, "Old office access badge code 1234", "Fact")

    obsoleted = jarvis.mark_obsolete(context, rec.memory_id, reason="Badge replaced with NFC card")

    assert obsoleted.active is False
    assert obsoleted.content["lifecycle_state"] == "OBSOLETE"
    assert obsoleted.content["obsolete_reason"] == "Badge replaced with NFC card"
    assert "obsoleted_at" in obsoleted.content

    # Active queries exclude obsolete record
    active_mems = memory_api.retrieve(context, "boss_personal")
    assert all(m.memory_id != rec.memory_id for m in active_mems)


def test_detect_obsolete_memories(memory_api, jarvis):
    context = AuthContext("boss")
    # Concluded task
    task_done = add(memory_api, context, "Database migration task completed", "Task")

    # Superseded record left active
    record_sup = add(memory_api, context, "Old server IP", "Fact")
    content = dict(record_sup.content)
    content["superseded_by"] = "new_ip_id"
    memory_api.repository.update(MemoryRecord(
        record_sup.memory_id, record_sup.owner_id, record_sup.domain, record_sup.category,
        content, record_sup.session_id, record_sup.created_at, record_sup.updated_at, True
    ))

    candidates = jarvis.detect_obsolete_memories(context, domain="boss_personal")
    candidate_ids = [c["record"].memory_id for c in candidates]
    assert task_done.memory_id in candidate_ids
    assert record_sup.memory_id in candidate_ids


# ============================================================================
# COHERENT USER MODEL TESTS
# ============================================================================

def test_user_model_generation(memory_api, relational, jarvis):
    context = AuthContext("boss")

    # Populate canonical categories
    p1 = add(memory_api, context, "Prefers Python for backends", "Preference", importance=0.9)
    g1 = add(memory_api, context, "Build autonomous AI", "Goal", importance=0.95)
    proj1 = add(memory_api, context, "Project Antigravity", "Project", importance=0.9)
    s1 = add(memory_api, context, "Python, Rust, Distributed Systems", "Skill", importance=0.85)
    f1 = add(memory_api, context, "Lead Architect at Vennela AI", "Fact", importance=0.9)
    e1 = add(memory_api, context, "Finished Level 5 checkpoint", "Event", importance=0.7)

    # Link Project and Goal in Level 4
    rel = relational.create_relationship(context, proj1.memory_id, g1.memory_id, "PROJECT_GOAL")

    # Obsolete memory should be excluded
    obs = add(memory_api, context, "Old deprecated requirement", "Fact")
    jarvis.mark_obsolete(context, obs.memory_id, "deprecated")

    model = jarvis.get_user_model(context)

    assert model.user_id == "boss"
    assert len(model.preferences) == 1
    assert model.preferences[0].memory_id == p1.memory_id
    assert len(model.goals) == 1
    assert model.goals[0].memory_id == g1.memory_id
    assert len(model.projects) == 1
    assert model.projects[0].memory_id == proj1.memory_id
    assert len(model.skills) == 1
    assert len(model.key_facts) == 1
    assert len(model.recent_events) == 1

    # Obsolete memory excluded
    all_model_ids = [m.memory_id for m in model.preferences + model.goals + model.projects + model.skills + model.key_facts + model.recent_events]
    assert obs.memory_id not in all_model_ids

    # Relationships included
    assert len(model.relationships) == 1
    assert model.relationships[0].relationship_id == rel.relationship_id

    # Summary prompt generated
    assert "[Coherent User Model: boss]" in model.summary_prompt
    assert "Prefers Python for backends" in model.summary_prompt
    assert "Project Antigravity" in model.summary_prompt


# ============================================================================
# SECURITY TESTS
# ============================================================================

def test_jarvis_security_boundaries(memory_api, jarvis):
    boss = AuthContext("boss")
    intruder = AuthContext("intruder")

    # Boss memory
    bm = add(memory_api, boss, "Boss private encryption key", "Fact", importance=0.9)

    # Intruder cannot proactively recall Boss memory
    intruder_recall = jarvis.proactive_recall(intruder, "private encryption key")
    assert len(intruder_recall) == 0

    # Intruder cannot see Boss memories in user model
    intruder_model = jarvis.get_user_model(intruder)
    assert intruder_model.user_id == "intruder"
    assert len(intruder_model.key_facts) == 0

    # Intruder cannot transition lifecycle of Boss memory
    with pytest.raises(MemoryAuthorizationError):
        jarvis.transition_lifecycle(intruder, bm.memory_id, MemoryLifecycleState.SUPERSEDED)


def test_jarvis_session_isolation(memory_api, jarvis):
    sess1 = AuthContext("boss", session_id="s1")
    sess2 = AuthContext("boss", session_id="s2")

    add(memory_api, sess1, "Session 1 confidential discussion", "Event", domain="session", session_id="s1")

    # Session 2 cannot proactively recall Session 1 event
    res = jarvis.proactive_recall(sess2, "confidential discussion", domain="session", session_id="s2")
    assert len(res) == 0


# ============================================================================
# SCHEMA & CONTRACT TESTS
# ============================================================================

def test_jarvis_memory_schema_contract():
    schema = Path(__file__).parents[1] / "migrations" / "005_jarvis_memory.sql"
    assert schema.exists()
    sql = schema.read_text()
    assert "memories_owner_active_category_idx" in sql
