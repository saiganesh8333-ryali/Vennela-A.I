"""Small, deterministic Phase 2 memory lifecycle orchestrator."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.memory_core import process_memory
from memory.retrieval import retrieve_memories
from memory.smart_memory import _normalize_memory
from memory.smart_memory import get_memory, save_memory
from memory_semantic_linker import update_memory_links


class MemoryOrchestrator:
    """Coordinate normalization, scoring, consolidation, linking, and retrieval."""

    def process(
        self,
        candidate: Any,
        memory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        current = _normalize_memory(memory)
        if not isinstance(candidate, str) or not candidate.strip():
            return {"memory": current, "stored": False, "reason": "empty"}

        text = candidate.strip()
        processed = process_memory(text)
        score = float(processed.get("importance", 0.0) or 0.0)
        entry = {
            "text": processed.get("compressed") or text,
            "type": processed.get("type", "general"),
            "topic": processed.get("topic", "general"),
            "importance": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        target = current["episodic"] if entry["type"] == "event" else current["long_term"]
        duplicate = next(
            (item for item in target if self._text(item) == entry["text"]),
            None,
        )
        if isinstance(duplicate, dict):
            duplicate["importance"] = max(float(duplicate.get("importance", 0.0) or 0.0), score)
            duplicate["reinforced_count"] = int(duplicate.get("reinforced_count", 1) or 1) + 1
            stored = False
        else:
            target.append(entry) if processed.get("should_store", False) else current["short_term"].append(entry)
            stored = bool(processed.get("should_store", False))
        linked = update_memory_links(current)
        return {
            "memory": linked,
            "stored": stored,
            "duplicate": duplicate is not None,
            "classification": entry["type"],
            "importance": score,
            "lifecycle": ["captured", "classified", "scored", "stored", "linked"],
        }

    def retrieve(self, memory: Dict[str, Any], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        normalized = _normalize_memory(memory)
        results = retrieve_memories(normalized, query, top_k=top_k)
        return results

    def process_and_save(
        self,
        user_id: str,
        candidate: Any,
        memory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a candidate and persist the resulting canonical snapshot."""
        current = get_memory(user_id) if memory is None else memory
        result = self.process(candidate, current)
        if result.get("reason") == "empty":
            return result
        result["saved"] = save_memory(user_id, result["memory"])
        return result

    @staticmethod
    def _text(item: Any) -> str:
        if isinstance(item, dict):
            value = item.get("text") or item.get("content") or item.get("event")
            return value.strip() if isinstance(value, str) else ""
        return item.strip() if isinstance(item, str) else ""
