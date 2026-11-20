import pytest
from pathlib import Path
import app

from memory import (
    AuthContext, InMemoryMemoryRepository, MemoryAPI, MemoryAuthorizationError,
    MemoryCategory,
)


@pytest.fixture
def api():
    return MemoryAPI(InMemoryMemoryRepository())


def test_create_retrieve_update_and_forget(api):
    context = AuthContext("boss")
    record = api.store(context, "Likes robotics", "Preference")
    assert api.retrieve(context)[0].memory_id == record.memory_id
    updated = api.update(context, record.memory_id, "Likes robotics and astronomy")
    assert updated.content.endswith("astronomy")
    assert api.forget(context, record.memory_id)
    assert api.retrieve(context) == []


def test_category_validation(api):
    with pytest.raises(ValueError, match="category"):
        api.create(AuthContext("boss"), "x", "Unknown")


def test_owner_and_core_authorization(api):
    record = api.create(AuthContext("boss"), "private", "Fact")
    with pytest.raises(MemoryAuthorizationError):
        api.update(AuthContext("other"), record.memory_id, "changed")
    with pytest.raises(MemoryAuthorizationError):
        api.create(AuthContext("boss"), "identity", "Fact", "vennela_core")
    core = AuthContext("system", scopes=frozenset({"memory:core"}))
    assert api.create(core, "identity", "Fact", "vennela_core")


def test_session_isolation(api):
    owner = AuthContext("boss", session_id="s1")
    record = api.create(owner, "temporary", "Event", "session", "s1")
    assert api.retrieve(owner, "session", "s1")[0].memory_id == record.memory_id
    with pytest.raises(MemoryAuthorizationError):
        api.retrieve(AuthContext("boss", session_id="s2"), "session", "s1")


def test_category_and_schema_contract():
    assert len(MemoryCategory) == 10
    schema = Path(__file__).parents[1] / "migrations" / "001_basic_memory.sql"
    sql = schema.read_text()
    assert "memory_id text primary key" in sql
    assert "owner_id text not null" in sql
    assert "domain text not null" in sql
    assert "category text not null" in sql
    assert "active boolean not null" in sql


def test_chat_memory_uses_server_boss_identity(monkeypatch):
    monkeypatch.setenv("VENNELA_BOSS_ID", "configured-boss")
    context = app._basic_memory_context()
    assert context.user_id == "configured-boss"
    assert context.session_id is None
    assert context.scopes == frozenset()


def test_chat_memory_ignores_client_identity():
    names = app.chat.__code__.co_names
    constants = app.chat.__code__.co_consts
    assert "smart_memory" not in names
    assert "retrieval" not in names
    assert "x-user-id" not in constants
    assert "x-session-id" not in constants
