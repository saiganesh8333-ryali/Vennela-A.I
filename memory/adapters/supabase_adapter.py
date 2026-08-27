"""Supabase persistence for canonical Vennela memory snapshots."""

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Dict, Iterable, List, Optional

TABLE_NAME = "memories"
MEMORY_FIELDS = (
    "profile",
    "short_term",
    "long_term",
    "episodic",
    "emotions",
    "sentiments",
    "importance",
    "summary",
    "embeddings",
)


class SupabaseConfigurationError(RuntimeError):
    """Raised when the Supabase client cannot be configured."""


class SupabaseOperationError(RuntimeError):
    """Raised when a Supabase operation fails."""


def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {},
        "short_term": [],
        "long_term": [],
        "episodic": [],
        "emotions": {},
        "sentiments": {},
        "importance": [],
        "summary": "",
        "embeddings": [],
    }


def _normalize_long_term_entry(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        entry = dict(item)
        text = (
            entry.get("text")
            or entry.get("content")
            or entry.get("event")
            or entry.get("message")
            or ""
        )
        entry["text"] = str(text)
        entry.setdefault("timestamp", None)
        entry.setdefault("importance", 0.0)
        return entry
    return {"text": str(item), "timestamp": None, "importance": 0.0}


def _normalize_memory(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    memory = _default_memory()
    if not isinstance(data, dict):
        return memory

    for field in MEMORY_FIELDS:
        if field != "long_term" and field in data:
            memory[field] = deepcopy(data[field])

    seen = set()
    for item in data.get("long_term") or []:
        entry = _normalize_long_term_entry(item)
        text = entry["text"]
        if text and text not in seen:
            seen.add(text)
            memory["long_term"].append(entry)
    return memory


def _client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
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
    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = _check_response(response)
    return rows[0] if rows and isinstance(rows[0], dict) else None


def load_memory(user_id: str) -> Dict[str, Any]:
    row = _fetch_row(_client(), user_id)
    if row is None:
        return _default_memory()
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
    payload = {"user_id": user_id, **merged}
    now = datetime.now(timezone.utc).isoformat()
    if existing and existing.get("created_at"):
        payload["created_at"] = existing["created_at"]
    else:
        payload["created_at"] = now
    payload["updated_at"] = now

    response = client.table(TABLE_NAME).upsert(payload, on_conflict="user_id").execute()
    _check_response(response)
    return True


def delete_memory(user_id: str) -> bool:
    response = (
        _client().table(TABLE_NAME).delete().eq("user_id", user_id).execute()
    )
    _check_response(response)
    return True


def list_user_ids() -> Iterable[str]:
    response = _client().table(TABLE_NAME).select("user_id").execute()
    return [
        str(row["user_id"])
        for row in _check_response(response)
        if isinstance(row, dict) and row.get("user_id") is not None
    ]
