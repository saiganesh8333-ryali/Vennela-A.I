from datetime import datetime, timezone

import pytest

from memory import (
    AuthContext,
    InMemoryMemoryRepository,
    MemoryAPI,
    MemoryCategory,
    MemoryDomain,
    MemoryRecord,
    MemoryStatus,
)


def make_record(**overrides):
    values = {
        "memory_id": "memory-1",
        "owner_id": "boss",
        "domain": MemoryDomain.BOSS_PERSONAL,
        "category": MemoryCategory.FACT,
        "content": "Likes robotics",
    }
    values.update(overrides)
    return MemoryRecord(**values)


def test_canonical_defaults_and_utc_normalization():
    naive = datetime(2026, 9, 7, 10, 0)
    record = make_record(created_at=naive, updated_at="2026-09-07T10:01:00+05:30")
    assert record.status is MemoryStatus.CANDIDATE
    assert record.created_at.tzinfo is timezone.utc
    assert record.updated_at.tzinfo is timezone.utc
    assert record.last_accessed_at is None
    assert record.expires_at is None


@pytest.mark.parametrize("field", ["confidence", "importance"])
def test_scores_must_be_between_zero_and_one(field):
    with pytest.raises(ValueError, match=field):
        make_record(**{field: 1.1})


def test_content_and_metadata_are_validated():
    with pytest.raises(ValueError, match="content"):
        make_record(content={})
    with pytest.raises(ValueError, match="JSON"):
        make_record(content=object())
    with pytest.raises(ValueError, match="snapshot"):
        make_record(metadata={"long_term": []})


def test_domain_session_contract():
    with pytest.raises(ValueError, match="session_id"):
        make_record(domain=MemoryDomain.SESSION)
    with pytest.raises(ValueError, match="only valid"):
        make_record(session_id="s1")
    assert make_record(domain=MemoryDomain.SESSION, session_id="s1")


def test_lifecycle_transitions_and_deleted_tombstone():
    record = make_record()
    active = record.transition(MemoryStatus.ACTIVE)
    stale = active.transition(MemoryStatus.STALE)
    archived = stale.transition(MemoryStatus.ARCHIVED)
    deleted = archived.transition(MemoryStatus.DELETED)
    assert deleted.status is MemoryStatus.DELETED
    with pytest.raises(ValueError, match="transition"):
        deleted.transition(MemoryStatus.ACTIVE)


def test_repository_crud_lifecycle_and_domain_isolation():
    repository = InMemoryMemoryRepository()
    personal = make_record().transition(MemoryStatus.ACTIVE)
    core = make_record(
        memory_id="core-1", owner_id="system", domain=MemoryDomain.VENNELA_CORE
    ).transition(MemoryStatus.ACTIVE)
    session = make_record(
        memory_id="session-1", domain=MemoryDomain.SESSION, session_id="s1"
    ).transition(MemoryStatus.ACTIVE)
    for record in (personal, core, session):
        repository.create(record)

    assert [item.memory_id for item in repository.list("boss", MemoryDomain.BOSS_PERSONAL)] == ["memory-1"]
    assert repository.list("boss", MemoryDomain.VENNELA_CORE) == []
    session_records = repository.list("boss", MemoryDomain.SESSION, "s1")
    assert [item.memory_id for item in session_records] == ["session-1"]
    assert repository.list("boss", MemoryDomain.SESSION, "s2") == []

    updated = personal.with_updates(content="Updated")
    assert repository.update(updated).content == "Updated"
    assert repository.transition_status("memory-1", MemoryStatus.ARCHIVED).status is MemoryStatus.ARCHIVED
    assert repository.retrieve("boss", MemoryDomain.BOSS_PERSONAL) == []
    assert repository.forget("memory-1") is True
    assert repository.get("memory-1").status is MemoryStatus.DELETED


def test_api_creates_active_records_and_soft_deletes():
    api = MemoryAPI(InMemoryMemoryRepository())
    record = api.create(AuthContext("boss"), "private", "Fact")
    assert record.status is MemoryStatus.ACTIVE
    updated = api.update(AuthContext("boss"), record.memory_id, "changed")
    assert updated.created_at == record.created_at
    assert updated.updated_at >= record.updated_at
    assert api.delete(AuthContext("boss"), record.memory_id) is True
    assert api.repository.get(record.memory_id).status is MemoryStatus.DELETED
