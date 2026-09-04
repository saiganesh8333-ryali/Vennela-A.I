from memory.orchestrator import MemoryOrchestrator
from memory.retrieval import retrieve_memories
from memory_semantic_linker import link_related_memories, update_memory_links
from core.memory_core import process_memory
from memory.smart_memory import update_memory


def test_orchestrator_classifies_and_consolidates_duplicates():
    orchestrator = MemoryOrchestrator()
    first = orchestrator.process("I like robotics", {})
    second = orchestrator.process("I like robotics", first["memory"])

    assert first["classification"] == "preference"
    assert second["duplicate"] is True
    assert len(second["memory"]["long_term"]) == 1


def test_linker_accepts_legacy_strings_and_malformed_records():
    memory = {"long_term": ["robotics is useful", {"content": "robotics is useful"}], "short_term": [None]}
    updated = update_memory_links(memory)

    assert "semantic_links" in updated
    assert link_related_memories("robotics is useful", ["robotics is useful", None]) == []


def test_retrieval_ranks_importance_with_semantic_match():
    memory = {
        "embeddings": [
            {"text": "robotics project", "vector": [1.0, 0.0], "importance": 0.2},
            {"text": "robotics goal", "vector": [1.0, 0.0], "importance": 0.9},
        ]
    }

    results = retrieve_memories(memory, "robotics", threshold=0.1, top_k=2)

    assert [result["text"] for result in results] == ["robotics goal", "robotics project"]


def test_explicit_remember_statement_is_durable_and_retrievable():
    statement = "Remember this: my favorite project codename is Project Nova."
    processed = process_memory(statement)
    assert processed["type"] == "preference"
    assert processed["should_store"] is True

    memory = update_memory("user-1", statement, "Saved.", {})
    results = retrieve_memories(
        memory,
        "What was the project codename I told you to remember?",
        threshold=0.1,
    )
    assert results
    assert "Project Nova" in results[0]["text"]
