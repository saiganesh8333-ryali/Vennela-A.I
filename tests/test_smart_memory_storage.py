import pytest

from memory import smart_memory


def test_get_memory_uses_storage_adapter_and_normalizes(monkeypatch):
    calls = []
    raw_memory = {
        "long_term": ["legacy memory", {"text": "legacy memory"}],
        "summary": "summary",
    }

    def fake_load(user_id):
        calls.append(user_id)
        return raw_memory

    monkeypatch.setattr(smart_memory.storage_adapter, "load_memory", fake_load)

    result = smart_memory.get_memory("user-1")

    assert calls == ["user-1"]
    assert result["long_term"] == [
        {"text": "legacy memory", "timestamp": None, "importance": 0.0}
    ]
    assert result["summary"] == "summary"


def test_save_memory_uses_storage_adapter_with_canonical_data(monkeypatch):
    calls = []

    def fake_save(user_id, data):
        calls.append((user_id, data))
        return True

    monkeypatch.setattr(smart_memory.storage_adapter, "save_memory", fake_save)

    result = smart_memory.save_memory(
        "user-2",
        {"long_term": ["new memory"], "summary": "summary"},
    )

    assert result is True
    assert calls == [
        (
            "user-2",
            {
                "profile": {},
                "short_term": [],
                "long_term": [
                    {"text": "new memory", "timestamp": None, "importance": 0.0}
                ],
                "episodic": [],
                "emotions": {},
                "sentiments": {},
                "importance": [],
                "summary": "summary",
                "embeddings": [],
            },
        )
    ]


def test_storage_configuration_errors_are_not_swallowed(monkeypatch):
    error = RuntimeError("Supabase configuration missing")
    monkeypatch.setattr(
        smart_memory.storage_adapter,
        "load_memory",
        lambda user_id: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError, match="Supabase configuration missing"):
        smart_memory.get_memory("user-3")
