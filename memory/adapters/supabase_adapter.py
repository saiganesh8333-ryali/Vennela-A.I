"""Supabase persistence for canonical Vennela memory snapshots."""

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Dict, Iterable, List, Optional

TABLE_NAME = "memories"
MEMORY_FIELDS = (
    "profile", "short_term", "long_term", "episodic", "emotions",
    "sentiments", "importance", "summary", "embeddings",
)


class SupabaseConfigurationError(RuntimeError):
    """Raised when Supabase cannot be configured."""


class SupabaseOperationError(RuntimeError):
    """Raised when a Supabase operation fails."""


def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {}, "short_term": [], "long_term": [], "episodic": [],
        "emotions": {}, "sentiments": {}, "importance": [], "summary": "",
        "embeddings": [],
    }


def _normalize_entry(item: Any) -> Optional[Dict[str, Any]]:
    if isinstance(item, dict):
        entry = dict(item)
        text = entry.get("text") or entry.get("content") or entry.get("event") or entry.get("message")
        if not isinstance(text, str) or not text.strip():
            return None
        entry["text"] = text.strip()
        entry.setdefault("timestamp", None)
        entry.setdefault("importance", 0.0)
        return entry
    if isinstance(item, str) and item.strip():
        return {"text": item.strip(), "timestamp": None, "importance": 0.0}
    return None


def _normalize_memory(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    memory = _default_memory()
    if not isinstance(data, dict):
        return memory
    for field in MEMORY_FIELDS:
        if field != "long_term" and field in data:
            memory[field] = deepcopy(data[field])
    seen = set()
    for item in data.get("long_term") or []:
        entry = _normalize_entry(item)
        if entry and entry["text"] not in seen:
            seen.add(entry["text"])
            memory["long_term"].append(entry)
    return memory


def _client():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SupabaseConfigurationError(
            "Supabase configuration missing: SUPABASE_URL and SUPABASE_KEY are required"
        )
    try:
        from supabase import create_client
    except Exception as exc:
        raise SupabaseConfigurationError(
            f"Supabase client unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    return create_client(url, key)


def _check_response(response: Any) -> List[Dict[str, Any]]:
    error = getattr(response, "error", None)
    status_code = getattr(response, "status_code", None)
    if error:
        raise SupabaseOperationError(f"Supabase {error}")
    if isinstance(status_code, int) and status_code >= 400:
        raise SupabaseOperationError(f"Supabase request failed with status {status_code}")
    rows = getattr(response, "data", None)
    return rows if isinstance(rows, list) else []


def _fetch_row(client: Any, user_id: str) -> Optional[Dict[str, Any]]:
    response = client.table(TABLE_NAME).select("*").eq("user_id", user_id).limit(1).execute()
    rows = _check_response(response)
    return rows[0] if rows and isinstance(rows[0], dict) else None


def load_memory(user_id: str) -> Dict[str, Any]:
    row = _fetch_row(_client(), user_id)
    return _normalize_memory(row)


def save_memory(user_id: str, data: Dict[str, Any]) -> bool:
    client = _client()
    existing = _fetch_row(client, user_id)
    merged = _normalize_memory(existing or {})
    if isinstance(data, dict):
        for field in MEMORY_FIELDS:
            if field in data:
                merged[field] = deepcopy(data[field])
    merged = _normalize_memory(merged)
    now = datetime.now(timezone.utc).isoformat()
    payload = {"user_id": user_id, **merged, "updated_at": now}
    payload["created_at"] = (existing or {}).get("created_at") or now
    _check_response(client.table(TABLE_NAME).upsert(payload, on_conflict="user_id").execute())
    return True


def delete_memory(user_id: str) -> bool:
    _check_response(_client().table(TABLE_NAME).delete().eq("user_id", user_id).execute())
    return True


def list_user_ids() -> Iterable[str]:
    rows = _check_response(_client().table(TABLE_NAME).select("user_id").execute())
    return [str(row["user_id"]) for row in rows if isinstance(row, dict) and row.get("user_id") is not None]
