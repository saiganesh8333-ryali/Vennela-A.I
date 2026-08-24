import os
import json
import pytest

from memory.adapter import supabase_adapter

DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set; skipping supabase adapter integration tests")


def test_supabase_adapter_roundtrip():
    client = supabase_adapter.get_db()
    assert client is not None, "Supabase client should be available"

    user_id = f"test-user-{os.getpid()}"
    coll = client.collection("memory")
    doc = coll.document(user_id)

    # ensure delete to start from clean slate
    doc.delete()

    data = {
        "profile": {"name": "Test User"},
        "long_term": ["note A", "note B"],
        "episodic": [{"event": "e1"}],
    }

    ok = doc.set(data, merge=True)
    assert ok, "set should succeed"

    snap = doc.get()
    assert snap.exists
    loaded = snap.to_dict()
    # basic assertions on structure
    assert loaded.get("profile"), "profile should be present"
    assert isinstance(loaded.get("long_term"), list)

    # cleanup
    doc.delete()
