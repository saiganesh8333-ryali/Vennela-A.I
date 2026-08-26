from typing import Callable, Dict, Iterable, Tuple, Optional
from collections import Counter
import os

try:
    # Lazy import to avoid heavy firebase init during test collection
    from firebase.firebase_db import get_db as get_firebase_db
except Exception:  # pragma: no cover - firebase may be absent in test env
    get_firebase_db = None


def _sanitize_exception(exc: Exception) -> Dict[str, str]:
    """Return a safe, diagnostic-friendly summary of an exception."""
    exc_type = type(exc).__name__
    message = str(exc).strip()
    if not message:
        message = "unknown error"
    return {"error_type": exc_type, "error_message": message}


def _is_canonical(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return False
    if not isinstance(entry.get("text"), str):
        return False
    if not isinstance(entry.get("timestamp"), str):
        return False
    if not isinstance(entry.get("importance"), (int, float)):
        return False
    return True


def _supabase_docs_generator(sample_limit: Optional[int] = None):
    """
    Yield (id, dict) pairs from Supabase memory tables in a safe, read-only manner.
    Requires SUPABASE_URL and SUPABASE_KEY environment variables.
    """
    try:
        from supabase import create_client  # lazy import
    except Exception as exc:
        sanitized = _sanitize_exception(exc)
        raise RuntimeError(
            f"Supabase client not available ({sanitized['error_type']}: {sanitized['error_message']})"
        ) from exc

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase configuration missing (SUPABASE_URL/SUPABASE_KEY)")

    client = create_client(url, key)

    limit = sample_limit or 100
    try:
        resp = client.table("memories").select("id,long_term").limit(limit).execute()
        if hasattr(resp, "error") and resp.error:
            raise RuntimeError(f"Supabase query error: {resp.error}")
        status_code = getattr(resp, "status_code", None)
        if isinstance(status_code, int) and status_code >= 400:
            raise RuntimeError(f"Supabase query failed with status {status_code}")
        rows = getattr(resp, "data", None) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            doc_id = row.get("id") or row.get("user_id") or "unknown"
            yield str(doc_id), row
    except Exception as exc:
        sanitized = _sanitize_exception(exc)
        raise RuntimeError(
            f"Supabase table 'public.memories' unavailable ({sanitized['error_type']}: {sanitized['error_message']})"
        ) from exc


def validate_long_term_schema(
    documents: Optional[Iterable[Tuple[str, Dict]]] = None,
    sample_limit: Optional[int] = None,
):
    """
    Inspect memory documents and report statistics about long_term schema types.

    Args:
        documents: Optional iterable of (doc_id, doc_dict) pairs. When provided, this
            will be used instead of reading from the live datastore. Use this in tests
            or when a custom sampling mechanism is required.
        sample_limit: Optional maximum number of documents to scan (read-only).

    Returns:
        A dict with schema statistics. Never includes memory text or other PII.
    """
    scanned_docs = 0
    total_entries = 0
    canonical_count = 0
    legacy_count = 0
    malformed_count = 0
    missing_field_counter = Counter()

    if documents is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if supabase_url and supabase_key:
            try:
                documents = _supabase_docs_generator(sample_limit=sample_limit)
            except Exception as e:
                sanitized = _sanitize_exception(e)
                return {
                    "available": False,
                    "scanned_docs": None,
                    "total_entries": None,
                    "canonical_count": None,
                    "canonical_pct": None,
                    "legacy_count": None,
                    "legacy_pct": None,
                    "malformed_count": None,
                    "malformed_pct": None,
                    "missing_field_counts": None,
                    "error_type": sanitized["error_type"],
                    "error_message": sanitized["error_message"],
                    "message": f"Supabase access failed: {sanitized['error_type']}: {sanitized['error_message']}",
                }

        if documents is None and get_firebase_db is not None:
            db = get_firebase_db()
            if db is not None:
                docs_iter = db.collection("memory").stream()

                def _iter_firebase():
                    for d in docs_iter:
                        yield d.id, d.to_dict()

                documents = _iter_firebase()

        if documents is None:
            return {
                "available": False,
                "scanned_docs": None,
                "total_entries": None,
                "canonical_count": None,
                "canonical_pct": None,
                "legacy_count": None,
                "legacy_pct": None,
                "malformed_count": None,
                "malformed_pct": None,
                "missing_field_counts": None,
                "error": "No datastore client available (SUPABASE not configured and FIREBASE disabled/unconfigured)",
                "message": "No datastore client available (SUPABASE not configured and FIREBASE disabled/unconfigured)",
            }

    try:
        for doc_id, doc in documents:
            if sample_limit is not None and scanned_docs >= sample_limit:
                break
            scanned_docs += 1

            if not isinstance(doc, dict):
                continue

            long_term = doc.get("long_term", [])
            if isinstance(long_term, str):
                try:
                    import json
                    parsed = json.loads(long_term)
                    long_term = parsed
                except Exception:
                    long_term = [long_term]

            if not isinstance(long_term, list):
                malformed_count += 1
                continue

            for entry in long_term:
                total_entries += 1
                if isinstance(entry, str):
                    legacy_count += 1
                    continue
                if isinstance(entry, dict):
                    if _is_canonical(entry):
                        canonical_count += 1
                        continue
                    malformed_count += 1
                    if not isinstance(entry.get("text"), str):
                        missing_field_counter["text"] += 1
                    if not isinstance(entry.get("timestamp"), str):
                        missing_field_counter["timestamp"] += 1
                    if not isinstance(entry.get("importance"), (int, float)):
                        missing_field_counter["importance"] += 1
                    continue
                malformed_count += 1
    except Exception as exc:
        sanitized = _sanitize_exception(exc)
        return {
            "available": False,
            "scanned_docs": None,
            "total_entries": None,
            "canonical_count": None,
            "canonical_pct": None,
            "legacy_count": None,
            "legacy_pct": None,
            "malformed_count": None,
            "malformed_pct": None,
            "missing_field_counts": None,
            "error_type": sanitized["error_type"],
            "error_message": sanitized["error_message"],
            "message": f"Schema validation failed: {sanitized['error_type']}: {sanitized['error_message']}",
        }

    def pct(count):
        return round((count / total_entries) * 100.0, 2) if total_entries > 0 else 0.0

    return {
        "available": True,
        "scanned_docs": scanned_docs,
        "total_entries": total_entries,
        "canonical_count": canonical_count,
        "canonical_pct": pct(canonical_count),
        "legacy_count": legacy_count,
        "legacy_pct": pct(legacy_count),
        "malformed_count": malformed_count,
        "malformed_pct": pct(malformed_count),
        "missing_field_counts": dict(missing_field_counter),
    }
