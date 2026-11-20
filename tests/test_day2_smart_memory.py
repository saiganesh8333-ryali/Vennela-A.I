import pytest

from core.memory_core import process_memory
from memory import AuthContext, MemoryAPI, MemoryCategory, MemoryDomain, InMemoryMemoryRepository
from memory.compatibility_adapter import MemoryCompatibilityAdapter


def test_transient_questions_are_not_persistent_memory():
    result = process_memory("Can you explain how embeddings work?")

    assert result["lifecycle"] == "temporary"
    assert result["should_store"] is False


def test_smart_memory_emits_canonical_classification_and_domain():
    result = process_memory("Remember this: my favorite project is Project Nova.")

    assert result["type"] == "preference"
    assert result["category"] == "Preference"
    assert result["domain"] == MemoryDomain.BOSS_PERSONAL.value
    assert result["lifecycle"] == "persistent"


def test_explicit_core_domain_is_preserved_by_compatibility_adapter():
    processed = process_memory(
        "The Vennela Core system architecture uses Supabase as the source of truth."
    )
    adapter = MemoryCompatibilityAdapter()

    record = adapter.to_record(
        AuthContext("system", scopes=frozenset({"memory:core"})),
        "ignored raw text",
        processed,
    )

    assert record is not None
    assert record.domain is MemoryDomain.VENNELA_CORE
    assert record.category is MemoryCategory.FACT


def test_invalid_smart_memory_domain_is_rejected():
    with pytest.raises(ValueError, match="invalid memory domain"):
        process_memory("Remember this preference.", domain="other")


def test_compatibility_adapter_does_not_store_string_false():
    adapter = MemoryCompatibilityAdapter()

    assert adapter.to_record(
        AuthContext("boss"),
        "temporary",
        {"should_store": "false"},
    ) is None


def test_canonical_api_keeps_domains_separate():
    api = MemoryAPI(InMemoryMemoryRepository())
    personal = AuthContext("boss")
    core = AuthContext("system", scopes=frozenset({"memory:core"}))

    api.create(personal, "likes robotics", "Preference")
    api.create(core, "Supabase is canonical", "Fact", "vennela_core")

    assert [record.content for record in api.retrieve(personal)] == ["likes robotics"]
    assert [record.content for record in api.retrieve(core, "vennela_core")] == [
        "Supabase is canonical"
    ]
