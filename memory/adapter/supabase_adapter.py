"""Synchronous PostgreSQL adapter for the existing public.memories table (Supabase)

This adapter exposes a very small Firestore-like subset used by the memory code:
- get_db() -> returns a client with collection(...).document(...).get()/set()/delete()

Design notes:
- The adapter uses DATABASE_URL env var to connect via psycopg2 (sync).
- It does not create or modify schema. It WILL NOT create tables.
- For M1 the adapter stores/reads an aggregated memory under memory_type 'knowledge' when set(data, merge=True)
  and will assemble memory documents from existing rows when reading.
- The adapter is intentionally minimal and defensive; it returns None or empty structures on errors.
"""
from __future__ import annotations

import os
import json
import uuid
import logging
from typing import Optional, Any, Dict, List

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool
except Exception:  # pragma: no cover - dependency optional for local dev
    psycopg2 = None
    pool = None

logger = logging.getLogger(__name__)

_DATABASE_POOL: Optional[pool.SimpleConnectionPool] = None


class DocumentSnapshot:
    def __init__(self, exists: bool, data: Optional[Dict] = None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self) -> Dict:
        return self._data


class DocumentProxy:
    def __init__(self, conn_pool: pool.SimpleConnectionPool, collection: str, doc_id: str):
        self._pool = conn_pool
        self._collection = collection
        self._doc_id = doc_id

    def _get_conn(self):
        return self._pool.getconn()

    def _put_conn(self, conn):
        try:
            self._pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def get(self) -> DocumentSnapshot:
        """Assemble a memory document for the user_id from public.memories rows."""
        if not self._pool:
            return DocumentSnapshot(False, {})

        conn = self._get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                """
                SELECT memory_type, content, importance, confidence, metadata, created_at, updated_at
                FROM public.memories
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (self._doc_id,)
            )
            rows = cur.fetchall()

            if not rows:
                return DocumentSnapshot(False, {})

            # default memory structure similar to existing smart_memory
            memory = {
                "profile": {},
                "short_term": [],
                "long_term": [],
                "episodic": [],
                "emotions": {},
                "sentiments": {},
                "importance": [],
                "summary": "",
                "embeddings": []
            }

            for r in rows:
                mtype = r["memory_type"]
                content_raw = r["content"]
                importance = r.get("importance")
                confidence = r.get("confidence")
                metadata = r.get("metadata")

                # try to decode JSON content when possible
                try:
                    parsed = json.loads(content_raw)
                except Exception:
                    parsed = content_raw

                if mtype == "profile":
                    if isinstance(parsed, dict):
                        memory["profile"].update(parsed)
                    else:
                        # store as text field
                        memory["profile"]["text"] = str(parsed)

                elif mtype == "episodic":
                    # treat episodic as events
                    memory["episodic"].append({
                        "event": parsed,
                        "timestamp": r.get("created_at"),
                        "importance": importance,
                    })

                elif mtype in {"preference", "goal", "project", "knowledge", "decision"}:
                    # treat these as long-term entries
                    memory["long_term"].append(parsed)

                else:
                    # fallback - append to long_term
                    memory["long_term"].append(parsed)

                # importance tracking
                memory["importance"].append({
                    "text": parsed if isinstance(parsed, (str, dict)) else str(parsed),
                    "score": float(importance) if importance is not None else 0.0,
                    "confidence": float(confidence) if confidence is not None else 0.0,
                    "metadata": metadata,
                })

            return DocumentSnapshot(True, memory)

        except Exception as exc:
            logger.warning("Supabase adapter read error: %s", exc)
            return DocumentSnapshot(False, {})
        finally:
            try:
                cur.close()
            except Exception:
                pass
            self._put_conn(conn)

    def set(self, data: Dict[str, Any], merge: bool = True) -> bool:
        """Store parts of the provided memory document into public.memories as rows.

        Behavior (M1):
        - profile -> upsert a single memory_type='profile' row for the user (replace existing profile row)
        - episodic -> append rows with memory_type='episodic' for each entry in data['episodic']
        - long_term -> append rows with memory_type='knowledge' for each entry in data['long_term']

        merge flag controls whether profile is merged (True will update existing profile row) and
        episodic/long_term entries are appended.
        This function will not serialize the entire document into a single row.
        """
        if not self._pool:
            return False

        ALLOWED_TYPES = {"profile", "preference", "goal", "project", "episodic", "decision", "knowledge"}

        conn = self._get_conn()
        try:
            cur = conn.cursor()

            # 1) Profile handling (single row)
            profile = data.get("profile")
            if profile is not None:
                profile_content = json.dumps(profile) if not isinstance(profile, str) else profile
                # try to find existing profile row
                cur.execute("SELECT id FROM public.memories WHERE user_id = %s AND memory_type = 'profile' LIMIT 1", (self._doc_id,))
                row = cur.fetchone()
                if row:
                    # update existing profile
                    cur.execute("UPDATE public.memories SET content = %s, updated_at = NOW() WHERE id = %s", (profile_content, row[0]))
                else:
                    new_id = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO public.memories (id, user_id, memory_type, content, created_at, updated_at) VALUES (%s, %s, %s, %s, NOW(), NOW())",
                        (new_id, self._doc_id, 'profile', profile_content)
                    )

            # 2) Episodic entries (append)
            episodic = data.get("episodic") or []
            for entry in episodic:
                content = json.dumps(entry) if not isinstance(entry, str) else entry
                new_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO public.memories (id, user_id, memory_type, content, created_at, updated_at) VALUES (%s, %s, %s, %s, NOW(), NOW())",
                    (new_id, self._doc_id, 'episodic', content)
                )

            # 3) Long-term entries -> map to knowledge by default
            long_term = data.get("long_term") or []
            for entry in long_term:
                content = json.dumps(entry) if not isinstance(entry, str) else entry
                new_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO public.memories (id, user_id, memory_type, content, created_at, updated_at) VALUES (%s, %s, %s, %s, NOW(), NOW())",
                    (new_id, self._doc_id, 'knowledge', content)
                )

            # 4) Preferences/goals/projects if present in data, allow explicit types
            for t in ("preference", "goal", "project", "decision", "knowledge"):
                items = data.get(t) or []
                for item in items:
                    content = json.dumps(item) if not isinstance(item, str) else item
                    new_id = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO public.memories (id, user_id, memory_type, content, created_at, updated_at) VALUES (%s, %s, %s, %s, NOW(), NOW())",
                        (new_id, self._doc_id, t, content)
                    )

            conn.commit()
            return True
        except Exception as exc:
            logger.warning("Supabase adapter write error: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass
            self._put_conn(conn)

    def delete(self) -> bool:
        if not self._pool:
            return False
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM public.memories WHERE user_id = %s", (self._doc_id,))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("Supabase adapter delete error: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass
            self._put_conn(conn)

    def delete(self) -> bool:
        if not self._pool:
            return False
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM public.memories WHERE user_id = %s", (self._doc_id,))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("Supabase adapter delete error: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass
            self._put_conn(conn)


class CollectionProxy:
    def __init__(self, conn_pool: pool.SimpleConnectionPool, name: str):
        self._pool = conn_pool
        self._name = name

    def document(self, doc_id: str) -> DocumentProxy:
        return DocumentProxy(self._pool, self._name, doc_id)


class SupabaseClient:
    def __init__(self, conn_pool: pool.SimpleConnectionPool):
        self._pool = conn_pool

    def collection(self, name: str) -> CollectionProxy:
        return CollectionProxy(self._pool, name)

    # Row-level operations expected by M1
    def create_memory(self, user_id: str, memory_type: str, content: Any, importance: Optional[float] = None, confidence: Optional[float] = None, metadata: Optional[Dict] = None) -> Optional[str]:
        """Insert a new memory row and return the new UUID id. Returns None on error."""
        ALLOWED_TYPES = {"profile", "preference", "goal", "project", "episodic", "decision", "knowledge"}
        if memory_type not in ALLOWED_TYPES:
            raise ValueError(f"Invalid memory_type: {memory_type}")
        conn = self._pool.getconn()
        try:
            cur = conn.cursor()
            new_id = str(uuid.uuid4())
            content_val = json.dumps(content) if not isinstance(content, str) else content
            # Importance and confidence are NOT NULL in the DB schema; default to 0.0 when not provided
            importance_val = float(importance) if importance is not None else 0.0
            confidence_val = float(confidence) if confidence is not None else 0.0
            # Ensure metadata is never NULL in the DB; use empty JSON object when not provided
            metadata_val = json.dumps(metadata) if metadata is not None else json.dumps({})
            cur.execute(
                "INSERT INTO public.memories (id, user_id, memory_type, content, importance, confidence, metadata, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
                (new_id, user_id, memory_type, content_val, importance_val, confidence_val, metadata_val)
            )
            conn.commit()
            return new_id
        except Exception as exc:
            logger.warning("Supabase create_memory error: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return None
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                self._pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_memory_by_id(self, mem_id: str) -> Optional[Dict]:
        conn = self._pool.getconn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                "SELECT id, user_id, memory_type, content, importance, confidence, metadata, created_at, updated_at FROM public.memories WHERE id = %s",
                (mem_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            try:
                content = json.loads(row['content'])
            except Exception:
                content = row['content']
            return {
                'id': row['id'],
                'user_id': row['user_id'],
                'memory_type': row['memory_type'],
                'content': content,
                'importance': row.get('importance'),
                'confidence': row.get('confidence'),
                'metadata': row.get('metadata'),
                'created_at': row.get('created_at'),
                'updated_at': row.get('updated_at')
            }
        except Exception as exc:
            logger.warning("Supabase get_memory_by_id error: %s", exc)
            return None
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                self._pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def list_memories_for_user(self, user_id: str) -> List[Dict]:
        conn = self._pool.getconn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                "SELECT id, user_id, memory_type, content, importance, confidence, metadata, created_at, updated_at FROM public.memories WHERE user_id = %s ORDER BY created_at ASC",
                (user_id,)
            )
            rows = cur.fetchall()
            results = []
            for row in rows:
                try:
                    content = json.loads(row['content'])
                except Exception:
                    content = row['content']
                results.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'memory_type': row['memory_type'],
                    'content': content,
                    'importance': row.get('importance'),
                    'confidence': row.get('confidence'),
                    'metadata': row.get('metadata'),
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at')
                })
            return results
        except Exception as exc:
            logger.warning("Supabase list_memories_for_user error: %s", exc)
            return []
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                self._pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def update_memory_by_id(self, mem_id: str, content: Any = None, importance: Optional[float] = None, confidence: Optional[float] = None, metadata: Optional[Dict] = None) -> bool:
        conn = self._pool.getconn()
        try:
            cur = conn.cursor()
            parts = []
            vals = []
            if content is not None:
                parts.append("content = %s")
                vals.append(json.dumps(content) if not isinstance(content, str) else content)
            if importance is not None:
                parts.append("importance = %s")
                vals.append(importance)
            if confidence is not None:
                parts.append("confidence = %s")
                vals.append(confidence)
            if metadata is not None:
                parts.append("metadata = %s")
                vals.append(json.dumps(metadata))
            if not parts:
                return False
            vals.append(mem_id)
            sql = f"UPDATE public.memories SET {', '.join(parts)}, updated_at = NOW() WHERE id = %s"
            cur.execute(sql, tuple(vals))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("Supabase update_memory_by_id error: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                self._pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def delete_memory_by_id(self, mem_id: str) -> bool:
        conn = self._pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM public.memories WHERE id = %s", (mem_id,))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("Supabase delete_memory_by_id error: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                self._pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass


def _init_pool() -> Optional[pool.SimpleConnectionPool]:
    global _DATABASE_POOL

    # Check for DATABASE_URL/SUPABASE_DB_URL first. Tests expect None when these are absent,
    # even if a previous pool exists.
    database_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set for Supabase adapter")
        return None

    # If a pool already exists and a database URL is present, reuse it.
    if _DATABASE_POOL is not None:
        return _DATABASE_POOL

    if psycopg2 is None or pool is None:
        logger.warning("psycopg2 is not installed; Supabase adapter unavailable")
        return None

    try:
        # Simple connection pool: min 1, max 5 connections
        _DATABASE_POOL = psycopg2.pool.SimpleConnectionPool(1, 5, dsn=database_url)
        return _DATABASE_POOL
    except Exception as exc:
        logger.warning("Failed to initialize Postgres pool: %s", exc)
        _DATABASE_POOL = None
        return None


def get_db() -> Optional[SupabaseClient]:
    pool_obj = _init_pool()
    if not pool_obj:
        return None
    return SupabaseClient(pool_obj)
