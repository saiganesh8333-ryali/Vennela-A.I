import os
import json
import pytest

from memory.adapter import supabase_adapter

DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set; skipping supabase adapter integration tests")


def test_create_and_get_and_delete_memory():
    client = supabase_adapter.get_db()
    assert client is not None
    user_id = f"test-user-{os.getpid()}"

    # create profile memory
    profile_id = client.create_memory(user_id, 'profile', {'name': 'Alice'})
    assert profile_id is not None

    fetched = client.get_memory_by_id(profile_id)
    assert fetched is not None
    assert fetched['memory_type'] == 'profile'
    assert fetched['content'].get('name') == 'Alice'

    # delete
    ok = client.delete_memory_by_id(profile_id)
    assert ok
    assert client.get_memory_by_id(profile_id) is None


def test_create_project_and_list_and_update():
    client = supabase_adapter.get_db()
    assert client is not None
    user_id = f"test-user-{os.getpid()}"

    project_id = client.create_memory(user_id, 'project', {'title': 'Proj X'})
    assert project_id is not None

    listed = client.list_memories_for_user(user_id)
    # at least one (the inserted project)
    assert any(m['id'] == project_id for m in listed)

    # update content
    ok = client.update_memory_by_id(project_id, content={'title': 'Proj X v2'}, importance=0.9)
    assert ok
    updated = client.get_memory_by_id(project_id)
    assert updated is not None
    assert updated['content'].get('title') == 'Proj X v2'
    assert float(updated.get('importance') or 0) == pytest.approx(0.9, rel=1e-3)

    # cleanup
    assert client.delete_memory_by_id(project_id)


def test_invalid_memory_type_raises():
    client = supabase_adapter.get_db()
    assert client is not None
    user_id = f"test-user-{os.getpid()}"
    with pytest.raises(ValueError):
        client.create_memory(user_id, 'not-a-type', {'x':1})


def test_get_db_when_no_database_url(monkeypatch):
    # Temporarily unset DATABASE_URL
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    # calling get_db directly from adapter should return None
    client = supabase_adapter._init_pool()
    assert client is None
