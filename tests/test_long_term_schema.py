import time
import logging
from memory.smart_memory import _normalize_memory, update_memory, _default_memory
from memory_semantic_linker import update_memory_links
from memory_importance_scorer import ImportanceScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_new_long_term_entry():
    """New long_term memories must be stored as canonical dict entries"""
    mem = _default_memory()
    user_msg = "I remember my dream project"

    updated = update_memory("user_1", user_msg, "", mem)

    lt = updated.get("long_term", [])[-1]
    assert isinstance(lt, dict), "long_term entry must be a dict"
    assert lt.get("text") == "I remember my dream project"
    assert lt.get("timestamp") is not None, "timestamp must be set for new entries"
    assert isinstance(lt.get("importance"), (int, float))


def test_legacy_string_normalized():
    """Legacy plain-string long_term entries are converted to canonical dicts"""
    raw = {"long_term": ["old memory text"]}
    mem = _normalize_memory(raw)
    assert isinstance(mem.get("long_term")[0], dict)
    lt = mem.get("long_term")[0]
    assert lt.get("text") == "old memory text"
    assert lt.get("timestamp") is None
    assert lt.get("importance") == 0.0


def test_existing_canonical_preserved():
    """Existing dict long_term entries preserve metadata"""
    raw = {"long_term": [{"text": "keep me", "timestamp": "2020-01-01T00:00:00", "importance": 0.9, "extra": "meta"}]}
    mem = _normalize_memory(raw)
    lt = mem.get("long_term")[0]
    assert lt.get("text") == "keep me"
    assert lt.get("timestamp") == "2020-01-01T00:00:00"
    assert lt.get("importance") == 0.9
    assert lt.get("extra") == "meta"


def test_duplicate_detection():
    """Duplicate text should not be inserted twice"""
    mem = _default_memory()
    mem["long_term"].append({"text": "duplicate", "timestamp": None, "importance": 0.0})

    updated = update_memory("user_2", "duplicate", "", mem)

    texts = [it.get("text") for it in updated.get("long_term", []) if isinstance(it, dict)]
    assert texts.count("duplicate") == 1


def test_consumers_with_canonical_entries():
    """Ensure semantic linker and importance scorer operate on canonical long_term entries"""
    mem = _default_memory()
    mem["long_term"].append({"text": "I love robotics", "timestamp": time.time(), "importance": 0.8})

    updated = update_memory_links(mem)
    assert isinstance(updated, dict)
    assert "semantic_links" in updated

    scorer = ImportanceScorer()
    all_mem = mem.get("short_term", []) + mem.get("long_term", [])
    scored = scorer.score_all_memories(all_mem, mem.get("emotions", {}))
    assert isinstance(scored, list)
