import pytest

from memory import storage_adapter


def test_defaults_to_supabase_and_never_selects_firebase(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    module = storage_adapter._backend_module()
    assert module.__name__ == "memory.adapters.supabase_adapter"


def test_explicit_supabase_selection(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    assert storage_adapter._backend_module().__name__ == "memory.adapters.supabase_adapter"


def test_other_backend_fails_clearly(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "firebase")
    with pytest.raises(RuntimeError, match="expected 'supabase'"):
        storage_adapter._backend_module()
