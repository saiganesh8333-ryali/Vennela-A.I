from datetime import datetime, timezone
from pathlib import Path
import pytest

from memory import (
    AuthContext,
    InMemoryMemoryRepository,
    MemoryAPI,
    MemoryAuthorizationError,
    MemoryCategory,
    MemoryDomain,
    MemoryNotFoundError,
    MemoryRelationship,
    RelationalMemory,
    RelationshipType,
)


@pytest.fixture
def memory_api():
    return MemoryAPI(InMemoryMemoryRepository())


@pytest.fixture
def relational(memory_api):
    return RelationalMemory(memory_api)


def create_mem(
    memory_api,
    context,
    text,
    category="Fact",
    domain="boss_personal",
    session_id=None,
    memory_id=None,
):
    return memory_api.create(
        context,
        {"text": text, "classification": category},
        category,
        domain,
        session_id,
        memory_id,
    )


# ============================================================================
# CREATION TESTS
# ============================================================================

def test_create_valid_relationship(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Project Antigravity", "Project")
    goal = create_mem(memory_api, context, "Autonomous coding agent", "Goal")

    rel = relational.create_relationship(
        context,
        source_memory_id=proj.memory_id,
        target_memory_id=goal.memory_id,
        relationship_type="PROJECT_GOAL",
        strength=0.85,
        metadata={"priority": "high"},
    )

    assert rel.relationship_id is not None
    assert rel.source_memory_id == proj.memory_id
    assert rel.target_memory_id == goal.memory_id
    assert rel.relationship_type == RelationshipType.PROJECT_GOAL
    assert rel.strength == 0.85
    assert rel.confidence == 0.85
    assert rel.active is True
    assert rel.metadata == {"priority": "high"}
    assert isinstance(rel.created_at, datetime)
    assert isinstance(rel.updated_at, datetime)


def test_create_relationship_invalid_source(memory_api, relational):
    context = AuthContext("boss")
    goal = create_mem(memory_api, context, "Goal 1", "Goal")

    with pytest.raises((KeyError, ValueError, MemoryNotFoundError)):
        relational.create_relationship(
            context,
            source_memory_id="nonexistent-id",
            target_memory_id=goal.memory_id,
            relationship_type=RelationshipType.PROJECT_GOAL,
        )


def test_create_relationship_invalid_target(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Project 1", "Project")

    with pytest.raises((KeyError, ValueError, MemoryNotFoundError)):
        relational.create_relationship(
            context,
            source_memory_id=proj.memory_id,
            target_memory_id="nonexistent-target-id",
            relationship_type=RelationshipType.PROJECT_GOAL,
        )


def test_create_relationship_self_linking_rejected(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Self Project", "Project")

    with pytest.raises(ValueError, match="distinct|itself"):
        relational.create_relationship(
            context,
            source_memory_id=proj.memory_id,
            target_memory_id=proj.memory_id,
            relationship_type=RelationshipType.RELATED_TO,
        )


def test_create_relationship_invalid_type(memory_api, relational):
    context = AuthContext("boss")
    m1 = create_mem(memory_api, context, "Memory 1", "Fact")
    m2 = create_mem(memory_api, context, "Memory 2", "Fact")

    with pytest.raises(ValueError, match="invalid relationship type"):
        relational.create_relationship(
            context,
            source_memory_id=m1.memory_id,
            target_memory_id=m2.memory_id,
            relationship_type="COMPLETELY_INVALID_TYPE",
        )


def test_create_relationship_invalid_strength(memory_api, relational):
    context = AuthContext("boss")
    m1 = create_mem(memory_api, context, "Memory 1", "Fact")
    m2 = create_mem(memory_api, context, "Memory 2", "Fact")

    with pytest.raises(ValueError, match="strength"):
        relational.create_relationship(
            context,
            source_memory_id=m1.memory_id,
            target_memory_id=m2.memory_id,
            relationship_type=RelationshipType.RELATED_TO,
            strength=-0.1,
        )

    with pytest.raises(ValueError, match="strength"):
        relational.create_relationship(
            context,
            source_memory_id=m1.memory_id,
            target_memory_id=m2.memory_id,
            relationship_type=RelationshipType.RELATED_TO,
            strength=1.5,
        )


def test_create_relationship_duplicate_rejected(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Project 1", "Project")
    goal = create_mem(memory_api, context, "Goal 1", "Goal")

    first = relational.create_relationship(
        context,
        source_memory_id=proj.memory_id,
        target_memory_id=goal.memory_id,
        relationship_type="PROJECT_GOAL",
        strength=0.8,
    )
    assert first is not None

    with pytest.raises(ValueError, match="relationship already exists"):
        relational.create_relationship(
            context,
            source_memory_id=proj.memory_id,
            target_memory_id=goal.memory_id,
            relationship_type="PROJECT_GOAL",
            strength=0.9,
        )


# ============================================================================
# RETRIEVAL TESTS
# ============================================================================

def test_retrieve_by_source_and_target(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Vennela AI", "Project")
    goal = create_mem(memory_api, context, "Voice Assistant", "Goal")
    pref = create_mem(memory_api, context, "Fast Response", "Preference")

    rel1 = relational.create_relationship(context, proj.memory_id, goal.memory_id, "PROJECT_GOAL")
    rel2 = relational.create_relationship(context, proj.memory_id, pref.memory_id, "PROJECT_PREFERENCE")

    # Source retrieval
    source_rels = relational.get_relationships(context, source_memory_id=proj.memory_id)
    assert len(source_rels) == 2
    assert {r.relationship_id for r in source_rels} == {rel1.relationship_id, rel2.relationship_id}

    # Target retrieval
    target_rels = relational.get_relationships(context, target_memory_id=goal.memory_id)
    assert len(target_rels) == 1
    assert target_rels[0].relationship_id == rel1.relationship_id


def test_retrieve_by_memory_id_and_direction(memory_api, relational):
    context = AuthContext("boss")
    m1 = create_mem(memory_api, context, "Node 1", "Fact")
    m2 = create_mem(memory_api, context, "Node 2", "Fact")
    m3 = create_mem(memory_api, context, "Node 3", "Fact")

    rel_out = relational.create_relationship(context, m2.memory_id, m3.memory_id, "RELATED_TO")
    rel_in = relational.create_relationship(context, m1.memory_id, m2.memory_id, "RELATED_TO")

    # Both directions
    all_m2 = relational.get_relationships(context, memory_id=m2.memory_id, direction="both")
    assert len(all_m2) == 2

    # Outgoing only
    out_m2 = relational.get_relationships(context, memory_id=m2.memory_id, direction="outgoing")
    assert len(out_m2) == 1
    assert out_m2[0].relationship_id == rel_out.relationship_id

    # Incoming only
    in_m2 = relational.get_relationships(context, memory_id=m2.memory_id, direction="incoming")
    assert len(in_m2) == 1
    assert in_m2[0].relationship_id == rel_in.relationship_id


def test_retrieve_filtered_by_relationship_type(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Alpha", "Project")
    goal = create_mem(memory_api, context, "Beta", "Goal")
    pref = create_mem(memory_api, context, "Gamma", "Preference")

    relational.create_relationship(context, proj.memory_id, goal.memory_id, "PROJECT_GOAL")
    relational.create_relationship(context, proj.memory_id, pref.memory_id, "PROJECT_PREFERENCE")

    filtered = relational.get_relationships(
        context,
        source_memory_id=proj.memory_id,
        relationship_type="PROJECT_PREFERENCE",
    )
    assert len(filtered) == 1
    assert filtered[0].relationship_type == RelationshipType.PROJECT_PREFERENCE


def test_retrieve_deterministic_ordering(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Core Project", "Project")
    g1 = create_mem(memory_api, context, "Goal 1", "Goal")
    g2 = create_mem(memory_api, context, "Goal 2", "Goal")
    g3 = create_mem(memory_api, context, "Goal 3", "Goal")

    rel1 = relational.create_relationship(context, proj.memory_id, g1.memory_id, "PROJECT_GOAL", strength=0.4)
    rel2 = relational.create_relationship(context, proj.memory_id, g2.memory_id, "PROJECT_GOAL", strength=0.9)
    rel3 = relational.create_relationship(context, proj.memory_id, g3.memory_id, "PROJECT_GOAL", strength=0.7)

    results = relational.get_relationships(context, source_memory_id=proj.memory_id)
    # Highest strength first
    assert [r.relationship_id for r in results] == [rel2.relationship_id, rel3.relationship_id, rel1.relationship_id]


# ============================================================================
# UPDATE TESTS
# ============================================================================

def test_update_relationship_strength_and_metadata(memory_api, relational):
    context = AuthContext("boss")
    p = create_mem(memory_api, context, "Project P", "Project")
    g = create_mem(memory_api, context, "Goal G", "Goal")

    created = relational.create_relationship(
        context, p.memory_id, g.memory_id, "PROJECT_GOAL", strength=0.5, metadata={"step": 1}
    )

    updated = relational.update_relationship(
        context,
        relationship_id=created.relationship_id,
        strength=0.95,
        metadata={"step": 2, "verified": True},
    )

    assert updated.relationship_id == created.relationship_id
    assert updated.strength == 0.95
    assert updated.confidence == 0.95
    assert updated.metadata == {"step": 2, "verified": True}
    assert updated.updated_at >= created.updated_at

    fetched = relational.get_relationship(context, created.relationship_id)
    assert fetched.strength == 0.95
    assert fetched.metadata["verified"] is True


def test_update_relationship_invalid_strength(memory_api, relational):
    context = AuthContext("boss")
    p = create_mem(memory_api, context, "P", "Project")
    g = create_mem(memory_api, context, "G", "Goal")
    rel = relational.create_relationship(context, p.memory_id, g.memory_id, "PROJECT_GOAL")

    with pytest.raises(ValueError, match="strength"):
        relational.update_relationship(context, rel.relationship_id, strength=2.0)


# ============================================================================
# REMOVAL TESTS
# ============================================================================

def test_remove_relationship(memory_api, relational):
    context = AuthContext("boss")
    p = create_mem(memory_api, context, "Project P", "Project")
    g = create_mem(memory_api, context, "Goal G", "Goal")

    rel = relational.create_relationship(context, p.memory_id, g.memory_id, "PROJECT_GOAL")
    assert relational.get_relationship(context, rel.relationship_id) is not None

    removed = relational.remove_relationship(context, rel.relationship_id)
    assert removed is True

    # Active retrieval excludes it
    assert relational.get_relationship(context, rel.relationship_id) is None
    assert relational.get_relationships(context, source_memory_id=p.memory_id) == []


def test_remove_nonexistent_relationship(relational):
    context = AuthContext("boss")
    with pytest.raises(KeyError):
        relational.remove_relationship(context, "nonexistent-id")


# ============================================================================
# TRAVERSAL TESTS
# ============================================================================

def test_traversal_direct_relationship(memory_api, relational):
    context = AuthContext("boss")
    proj = create_mem(memory_api, context, "Project Antigravity", "Project")
    goal = create_mem(memory_api, context, "Autonomous Intelligence", "Goal")

    relational.create_relationship(context, proj.memory_id, goal.memory_id, "PROJECT_GOAL")

    result = relational.traverse(context, start_memory_id=proj.memory_id, max_depth=1)
    assert len(result) == 1
    assert result[0].memory_id == goal.memory_id
    assert result[0].depth == 1
    assert result.visited_memory_ids == [goal.memory_id]
    assert result.depths == {goal.memory_id: 1}


def test_traversal_multi_hop(memory_api, relational):
    context = AuthContext("boss")
    # Path: Project -> Goal -> Preference
    proj = create_mem(memory_api, context, "Project Vennela", "Project")
    goal = create_mem(memory_api, context, "Full Automation", "Goal")
    pref = create_mem(memory_api, context, "Python 3.11+", "Preference")

    relational.create_relationship(context, proj.memory_id, goal.memory_id, "PROJECT_GOAL")
    relational.create_relationship(context, goal.memory_id, pref.memory_id, "GOAL_PREFERENCE")

    result = relational.traverse(context, start_memory_id=proj.memory_id, max_depth=2)
    assert len(result) == 2
    assert result.visited_memory_ids == [goal.memory_id, pref.memory_id]
    assert result.depths[goal.memory_id] == 1
    assert result.depths[pref.memory_id] == 2


def test_traversal_bounded_by_max_depth(memory_api, relational):
    context = AuthContext("boss")
    m1 = create_mem(memory_api, context, "M1", "Fact")
    m2 = create_mem(memory_api, context, "M2", "Fact")
    m3 = create_mem(memory_api, context, "M3", "Fact")
    m4 = create_mem(memory_api, context, "M4", "Fact")

    relational.create_relationship(context, m1.memory_id, m2.memory_id, "RELATED_TO")
    relational.create_relationship(context, m2.memory_id, m3.memory_id, "RELATED_TO")
    relational.create_relationship(context, m3.memory_id, m4.memory_id, "RELATED_TO")

    # Depth 1 only reaches m2
    res_depth_1 = relational.traverse(context, start_memory_id=m1.memory_id, max_depth=1)
    assert res_depth_1.visited_memory_ids == [m2.memory_id]

    # Depth 2 reaches m2 and m3
    res_depth_2 = relational.traverse(context, start_memory_id=m1.memory_id, max_depth=2)
    assert res_depth_2.visited_memory_ids == [m2.memory_id, m3.memory_id]


def test_traversal_cycle_handling(memory_api, relational):
    context = AuthContext("boss")
    # Cycle: A -> B -> C -> A
    mA = create_mem(memory_api, context, "Cycle Node A", "Fact")
    mB = create_mem(memory_api, context, "Cycle Node B", "Fact")
    mC = create_mem(memory_api, context, "Cycle Node C", "Fact")

    relational.create_relationship(context, mA.memory_id, mB.memory_id, "RELATED_TO")
    relational.create_relationship(context, mB.memory_id, mC.memory_id, "RELATED_TO")
    relational.create_relationship(context, mC.memory_id, mA.memory_id, "RELATED_TO")

    # Traversal should terminate without infinite loop and not duplicate mA
    result = relational.traverse(context, start_memory_id=mA.memory_id, max_depth=5)
    assert len(result) == 2
    assert result.visited_memory_ids == [mB.memory_id, mC.memory_id]


def test_traversal_deterministic_ordering(memory_api, relational):
    context = AuthContext("boss")
    start = create_mem(memory_api, context, "Hub", "Project")
    child_low = create_mem(memory_api, context, "Low strength child", "Goal")
    child_high = create_mem(memory_api, context, "High strength child", "Goal")

    relational.create_relationship(context, start.memory_id, child_low.memory_id, "PROJECT_GOAL", strength=0.3)
    relational.create_relationship(context, start.memory_id, child_high.memory_id, "PROJECT_GOAL", strength=0.9)

    result = relational.traverse(context, start_memory_id=start.memory_id, max_depth=1)
    # High strength child explored first
    assert result.visited_memory_ids == [child_high.memory_id, child_low.memory_id]


# ============================================================================
# SECURITY & AUTHORIZATION TESTS
# ============================================================================

def test_unauthorized_source_access_rejected(memory_api, relational):
    boss = AuthContext("boss")
    intruder = AuthContext("intruder")

    boss_proj = create_mem(memory_api, boss, "Secret Project", "Project")
    intruder_goal = create_mem(memory_api, intruder, "Intruder Goal", "Goal")

    with pytest.raises(MemoryAuthorizationError):
        relational.create_relationship(
            intruder,
            source_memory_id=boss_proj.memory_id,
            target_memory_id=intruder_goal.memory_id,
            relationship_type="PROJECT_GOAL",
        )


def test_unauthorized_target_access_rejected(memory_api, relational):
    boss = AuthContext("boss")
    intruder = AuthContext("intruder")

    boss_goal = create_mem(memory_api, boss, "Secret Goal", "Goal")
    intruder_proj = create_mem(memory_api, intruder, "Intruder Project", "Project")

    with pytest.raises(MemoryAuthorizationError):
        relational.create_relationship(
            intruder,
            source_memory_id=intruder_proj.memory_id,
            target_memory_id=boss_goal.memory_id,
            relationship_type="PROJECT_GOAL",
        )


def test_cross_owner_relationship_rejected(memory_api, relational):
    boss = AuthContext("boss")
    other = AuthContext("other_user")

    boss_mem = create_mem(memory_api, boss, "Boss Memory", "Fact")
    other_mem = create_mem(memory_api, other, "Other Memory", "Fact")

    with pytest.raises(MemoryAuthorizationError):
        relational.create_relationship(
            boss,
            source_memory_id=boss_mem.memory_id,
            target_memory_id=other_mem.memory_id,
            relationship_type="RELATED_TO",
        )


def test_vennela_core_authorization(memory_api, relational):
    boss = AuthContext("boss")
    core_context = AuthContext("system", scopes=frozenset({"memory:core"}))

    core_mem1 = create_mem(memory_api, core_context, "Core architecture", "Fact", domain="vennela_core")
    core_mem2 = create_mem(memory_api, core_context, "Core persistence", "Fact", domain="vennela_core")

    # Boss without memory:core cannot create relationship between core memories
    with pytest.raises(MemoryAuthorizationError):
        relational.create_relationship(
            boss,
            source_memory_id=core_mem1.memory_id,
            target_memory_id=core_mem2.memory_id,
            relationship_type="RELATED_TO",
        )

    # Core context with memory:core scope succeeds
    rel = relational.create_relationship(
        core_context,
        source_memory_id=core_mem1.memory_id,
        target_memory_id=core_mem2.memory_id,
        relationship_type="RELATED_TO",
    )
    assert rel is not None

    # Boss cannot retrieve core relationship when querying core memory ID
    with pytest.raises(MemoryAuthorizationError):
        relational.get_relationships(boss, memory_id=core_mem1.memory_id)

    # Broad query by boss excludes core relationship
    assert relational.get_relationships(boss) == []

    # Core context can retrieve it
    core_rels = relational.get_relationships(core_context, memory_id=core_mem1.memory_id)
    assert len(core_rels) == 1
    assert core_rels[0].relationship_id == rel.relationship_id


def test_session_isolation(memory_api, relational):
    sess1 = AuthContext("boss", session_id="session-1")
    sess2 = AuthContext("boss", session_id="session-2")

    m1 = create_mem(memory_api, sess1, "Meeting start", "Event", domain="session", session_id="session-1")
    m2 = create_mem(memory_api, sess1, "Meeting notes", "Event", domain="session", session_id="session-1")

    rel = relational.create_relationship(
        sess1,
        source_memory_id=m1.memory_id,
        target_memory_id=m2.memory_id,
        relationship_type="RELATED_TO",
    )
    assert rel is not None

    # Another session cannot access this relationship
    with pytest.raises(MemoryAuthorizationError):
        relational.get_relationships(sess2, memory_id=m1.memory_id)


# ============================================================================
# SCHEMA & CONTRACT TESTS
# ============================================================================

def test_relationship_type_and_schema_contract():
    assert len(RelationshipType) == 6
    assert RelationshipType.PROJECT_GOAL.value == "PROJECT_GOAL"
    assert RelationshipType.PROJECT_PREFERENCE.value == "PROJECT_PREFERENCE"
    assert RelationshipType.PROJECT_EVENT.value == "PROJECT_EVENT"
    assert RelationshipType.GOAL_PREFERENCE.value == "GOAL_PREFERENCE"
    assert RelationshipType.EVENT_PROJECT.value == "EVENT_PROJECT"
    assert RelationshipType.RELATED_TO.value == "RELATED_TO"

    schema = Path(__file__).parents[1] / "migrations" / "003_relational_memory.sql"
    assert schema.exists()
    sql = schema.read_text()
    assert "create table if not exists memory_relationships" in sql
    assert "relationship_id text primary key" in sql
    assert "source_memory_id text not null references memories(memory_id)" in sql
    assert "target_memory_id text not null references memories(memory_id)" in sql
    assert "check (source_memory_id <> target_memory_id)" in sql
    assert "memory_relationships_active_unique_idx" in sql
