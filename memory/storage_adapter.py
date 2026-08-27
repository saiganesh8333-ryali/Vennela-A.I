"""Backend-neutral memory storage interface.

Supabase is intentionally the only supported application backend in Phase 2.
Firebase is not imported or selected here.
"""

import os
from typing import Any, Dict, Iterable


def _backend_module():
    backend = os.getenv("STORAGE_BACKEND", "supabase").strip().lower()
    if backend != "supabase":
        raise RuntimeError(
            f"Unsupported memory storage backend '{backend}'; expected 'supabase'"
        )
    from memory.adapters import supabase_adapter
    return supabase_adapter


def load_memory(user_id: str) -> Dict[str, Any]:
    return _backend_module().load_memory(user_id)


def save_memory(user_id: str, data: Dict[str, Any]) -> bool:
    return _backend_module().save_memory(user_id, data)


def delete_memory(user_id: str) -> bool:
    return _backend_module().delete_memory(user_id)


def list_user_ids() -> Iterable[str]:
    return _backend_module().list_user_ids()
