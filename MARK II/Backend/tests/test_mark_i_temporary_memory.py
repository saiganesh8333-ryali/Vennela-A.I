"""Vennela AI MARK-II — Temporary MARK-I Memory & Brain B Integration Test Suite."""

import logging
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("VENNELA_BOSS_ID", "boss_test_user")
os.environ.setdefault("VENNELA_AGENT_TOKEN", "token-test-secret-123456789")
os.environ["LIGHTWEIGHT_MODE"] = "true"
os.environ["LLM_ROUTER_MOCK"] = "true"

from fastapi.testclient import TestClient

import app as app_module
from core.memory_contracts import (
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    TemporaryMarkIMemoryProvider,
    get_memory_subsystem,
    reset_memory_subsystem,
)
from llm_router.adapter import VennelaLLMAdapter
from memory.api import MemoryAPI
from memory.models import AuthContext, MemoryCategory, MemoryDomain
from memory.repository import (
    InMemoryMemoryRepository,
    SupabaseMemoryRepository,
    normalize_memory_category,
    parse_iso_timestamp,
    parse_memory_row,
)


class _RowsSupabaseClient:
    """Table-level mock returning raw database rows (including malformed rows) without filtering inside mock."""

    def __init__(self, rows_by_domain: dict[str, list[dict]] | None = None):
        self.rows_by_domain = rows_by_domain or {}
        self.recorded_filters: list[list[tuple[str, object]]] = []

    def table(self, name: str):
        assert name == "memories"
        outer = self

        class Query:
            def __init__(self):
                self._filters: list[tuple[str, object]] = []

            def select(self, cols="*"):
                return self

            def eq(self, col, val):
                self._filters.append((col, val))
                return self

            def order(self, col, desc=False):
                return self

            def limit(self, n):
                return self

            def execute(self):
                outer.recorded_filters.append(list(self._filters))
                filter_map = dict(self._filters)
                domain = str(filter_map.get("domain", "boss_personal"))
                owner = filter_map.get("owner_id")
                rows = outer.rows_by_domain.get(domain, [])
                # Only filter by owner when row has owner_id matching or testing owner scope
                matched = [
                    r for r in rows
                    if owner is None or r.get("owner_id") in (owner, None, "")
                ]
                return SimpleNamespace(data=matched, error=None)

        return Query()


class TestTemporaryMarkIMemoryIntegration(unittest.TestCase):
    """Comprehensive tests for MARK-I memory recovery and Brain B integration."""

    def setUp(self):
        reset_memory_subsystem()
        self.repo = InMemoryMemoryRepository()
        self.api = MemoryAPI(self.repo)
        self.boss_id = os.environ["VENNELA_BOSS_ID"]
        self.token = os.environ["VENNELA_AGENT_TOKEN"]
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        self.provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        app_module._brain_instance = None
        app_module._llm_adapter_instance = VennelaLLMAdapter(mock=True)
        self.client = TestClient(app_module.app)

    def tearDown(self):
        reset_memory_subsystem()

    def test_01_mark_i_initialization_and_mode(self):
        self.assertEqual(self.provider.mode, MemoryIsolationMode.MARK_I_TEMPORARY)

    def test_02_store_retrieve_update_delete_and_deduplication(self):
        stored = self.provider.store(
            "My name is Sai and I prefer Python",
            user_id=self.boss_id,
            session_id="sess-1",
            metadata={"store_session": True},
        )
        self.assertTrue(stored)

        # Duplicate write should not create duplicate records
        self.provider.store(
            "My name is Sai and I prefer Python",
            user_id=self.boss_id,
            session_id="sess-1",
            metadata={"store_session": True},
        )

        resp = self.provider.retrieve(
            MemoryRetrievalRequest(
                query="What is my name and language preference?",
                user_id=self.boss_id,
                session_id="sess-1",
            )
        )
        self.assertEqual(resp.mode, MemoryIsolationMode.MARK_I_TEMPORARY)
        self.assertGreater(resp.memory_count, 0)
        joined = "\n".join(resp.context_strings)
        self.assertIn("Sai", joined)

        # Direct update & delete through provider
        ctx = AuthContext(user_id=self.boss_id, authenticated=True, session_id="sess-1")
        records = self.api.retrieve(ctx, domain=MemoryDomain.BOSS_PERSONAL.value, limit=10)
        self.assertEqual(len(records), 1)
        rec_id = records[0].memory_id

        self.assertTrue(
            self.provider.update(
                rec_id,
                {"text": "My name is Sai and I prefer Rust"},
                user_id=self.boss_id,
                category=MemoryCategory.PREFERENCE.value,
            )
        )
        updated_resp = self.provider.retrieve(
            MemoryRetrievalRequest(query="language", user_id=self.boss_id)
        )
        self.assertIn("Rust", "\n".join(updated_resp.context_strings))

        self.assertTrue(self.provider.delete(rec_id, user_id=self.boss_id))
        after_delete = self.api.retrieve(ctx, domain=MemoryDomain.BOSS_PERSONAL.value, limit=10)
        self.assertEqual(len(after_delete), 0)

    def test_03_user_and_session_isolation(self):
        self.provider.store(
            "My secret project is Apollo",
            user_id="user_a",
            session_id="sess_a",
            metadata={"store_session": True},
        )
        self.provider.store(
            "I prefer dark mode",
            user_id="user_b",
            session_id="sess_b",
            metadata={"store_session": True},
        )

        # User B must never see User A's memories
        resp_b = self.provider.retrieve(
            MemoryRetrievalRequest(query="Apollo", user_id="user_b", session_id="sess_a")
        )
        self.assertNotIn("Apollo", "\n".join(resp_b.context_strings))

        # Session B must not see Session A's session-scoped memories
        self.api.create(
            AuthContext(user_id="user_a", authenticated=True, session_id="sess_a"),
            {"text": "Session A temporary note"},
            category=MemoryCategory.EVENT.value,
            domain=MemoryDomain.SESSION.value,
            session_id="sess_a",
        )
        resp_a_other_sess = self.provider.retrieve(
            MemoryRetrievalRequest(query="temporary note", user_id="user_a", session_id="sess_other")
        )
        self.assertNotIn("Session A temporary note", "\n".join(resp_a_other_sess.context_strings))

        # Cross-user update/delete must fail
        user_a_recs = self.api.retrieve(
            AuthContext(user_id="user_a", authenticated=True),
            domain=MemoryDomain.BOSS_PERSONAL.value,
        )
        self.assertFalse(
            self.provider.delete(user_a_recs[0].memory_id, user_id="user_b")
        )

    def test_04_fail_closed_without_user_id(self):
        with self.assertRaises(ValueError):
            self.provider.store("My name is Test", user_id="")
        with self.assertRaises(ValueError):
            self.provider.update("id-1", "new", user_id="  ")
        with self.assertRaises(ValueError):
            self.provider.delete("id-1", user_id="")

    def test_05_memory_failure_degrades_safely(self):
        def broken_factory():
            raise RuntimeError("Supabase unreachable")

        broken_provider = TemporaryMarkIMemoryProvider(api_factory=broken_factory)
        resp = broken_provider.retrieve(
            MemoryRetrievalRequest(query="hello", user_id=self.boss_id)
        )
        self.assertEqual(resp.memory_count, 0)
        self.assertEqual(resp.context_strings, [])
        self.assertEqual(resp.metadata.get("status"), "retrieval_failed")
        self.assertFalse(broken_provider.store("My name is Boss", user_id=self.boss_id))

    def test_06_sync_and_stream_chat_with_mark_i_memory(self):
        with patch.dict(
            os.environ,
            {"VENNELA_MEMORY_PROVIDER": "mark_i", "VENNELA_MEMORY_ENABLED": "true"},
        ):
            reset_memory_subsystem()
            app_module._memory_subsystem_instance = self.provider
            with patch("core.memory_contracts._memory_subsystem_instance", self.provider):
                # 1. Sync chat persists eligible turn
                res1 = self.client.post(
                    "/chat",
                    json={"message": "Remember my favorite framework is FastAPI", "session_id": "s-sync"},
                    headers=self.auth_headers,
                )
                self.assertEqual(res1.status_code, 200)

                # 2. Streaming chat retrieves and persists eligible turn
                res2 = self.client.post(
                    "/chat/stream",
                    json={"message": "I prefer concise engineering summaries", "session_id": "s-stream"},
                    headers=self.auth_headers,
                )
                self.assertEqual(res2.status_code, 200)
                self.assertTrue(len(res2.text) > 0)

                # Verify both memories were persisted for authenticated boss_id
                retrieved = self.provider.retrieve(
                    MemoryRetrievalRequest(query="FastAPI summaries", user_id=self.boss_id)
                )
                joined = "\n".join(retrieved.context_strings)
                self.assertIn("FastAPI", joined)
                self.assertIn("concise engineering summaries", joined)

    def test_07_health_reports_brain_b_and_mark_i(self):
        with patch("app.get_memory_subsystem", return_value=self.provider):
            res = self.client.get("/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["brain"], "brain_b_langgraph")
            self.assertEqual(data["memory_mode"], "MARK_I_TEMPORARY")

    def test_08_brain_a_deactivated_in_active_paths(self):
        self.assertNotIn("agents", sys.modules)
        self.assertNotIn("archive.brain_a_nexus", sys.modules)

    def test_09_category_normalization_and_safe_rejection(self):
        """Category D: normalize valid case/whitespace, fallback None/empty to Fact, reject invalid labels."""
        # Valid case & whitespace normalization
        self.assertEqual(normalize_memory_category("preference"), MemoryCategory.PREFERENCE)
        self.assertEqual(normalize_memory_category(" FACT "), MemoryCategory.FACT)
        self.assertEqual(normalize_memory_category("profile"), MemoryCategory.PROFILE)

        # Missing / empty fallback to Fact
        self.assertEqual(normalize_memory_category(None, memory_id="m-null"), MemoryCategory.FACT)
        self.assertEqual(normalize_memory_category("", memory_id="m-empty"), MemoryCategory.FACT)
        self.assertEqual(normalize_memory_category("   ", memory_id="m-blank"), MemoryCategory.FACT)

        # Non-category domain labels & arbitrary invalid categories must be rejected safely (not fabricated)
        for bad_cat in ("Personal", "personal", " PERSONAL ", "Core", "session", "InvalidCategory"):
            with self.assertRaises(ValueError):
                normalize_memory_category(bad_cat, memory_id="m-bad")

    def test_10_timestamp_normalization_variations(self):
        """Category E: support UTC, Z, offsets, naive ISO, datetime objects, cross-fallback, reject malformed."""
        dt_utc = parse_iso_timestamp("2026-11-27T12:00:00+00:00")
        self.assertEqual(dt_utc, datetime(2026, 11, 27, 12, 0, 0, tzinfo=timezone.utc))

        dt_z = parse_iso_timestamp("2026-11-27T12:00:00Z")
        self.assertEqual(dt_z, dt_utc)

        dt_z_lower = parse_iso_timestamp("2026-11-27T12:00:00z")
        self.assertEqual(dt_z_lower, dt_utc)

        dt_offset = parse_iso_timestamp("2026-11-27T17:30:00+05:30")
        self.assertEqual(dt_offset, dt_utc)

        dt_naive_str = parse_iso_timestamp("2026-11-27T12:00:00")
        self.assertEqual(dt_naive_str, dt_utc)

        dt_naive_obj = parse_iso_timestamp(datetime(2026, 11, 27, 12, 0, 0))
        self.assertEqual(dt_naive_obj, dt_utc)

        with self.assertRaises(ValueError):
            parse_iso_timestamp("not-a-timestamp")
        with self.assertRaises(ValueError):
            parse_iso_timestamp("")

        # Optional timestamp fallback (created_at present, updated_at omitted)
        row_only_created = parse_memory_row({
            "memory_id": "m-ts-1",
            "owner_id": self.boss_id,
            "domain": "boss_personal",
            "category": "Fact",
            "content": {"text": "Has created_at only"},
            "created_at": "2026-11-27T12:00:00Z",
        })
        self.assertEqual(row_only_created.updated_at, dt_utc)

        # Both timestamps missing must fail instead of fabricating historical timestamps
        with self.assertRaises(ValueError):
            parse_memory_row({
                "memory_id": "m-ts-missing",
                "owner_id": self.boss_id,
                "domain": "boss_personal",
                "category": "Fact",
                "content": {"text": "Missing both timestamps"},
            })

    def test_11_malformed_row_resilience_and_privacy_safe_diagnostics(self):
        """Categories C, F, G: isolate malformed rows, return all surrounding valid rows, and protect privacy."""
        canary_secret_content = "PRIVATE_CANARY_MEMORY_TEXT_774411"
        mixed_rows = [
            {
                "memory_id": "m-valid-1",
                "owner_id": self.boss_id,
                "domain": "boss_personal",
                "category": " preference ",
                "content": {"text": "Boss prefers dark blue UI"},
                "session_id": None,
                "created_at": "2026-11-26T10:00:00Z",
                "updated_at": "2026-11-26T10:00:00Z",
                "active": True,
            },
            {
                "memory_id": "m-bad-cat",
                "owner_id": self.boss_id,
                "domain": "boss_personal",
                "category": "Personal",
                "content": {"text": canary_secret_content},
                "created_at": "2026-11-26T10:00:00Z",
                "updated_at": "2026-11-26T10:00:00Z",
                "active": True,
            },
            {
                "memory_id": "m-bad-ts",
                "owner_id": self.boss_id,
                "domain": "boss_personal",
                "category": "Fact",
                "content": {"text": canary_secret_content},
                "created_at": "corrupted-timestamp",
                "updated_at": "2026-11-26T10:00:00Z",
                "active": True,
            },
            {
                "memory_id": "m-bad-domain",
                "owner_id": self.boss_id,
                "domain": "unknown_domain",
                "category": "Fact",
                "content": {"text": canary_secret_content},
                "created_at": "2026-11-26T10:00:00Z",
                "updated_at": "2026-11-26T10:00:00Z",
                "active": True,
            },
            {
                "memory_id": "m-missing-content",
                "owner_id": self.boss_id,
                "domain": "boss_personal",
                "category": "Fact",
                "content": None,
                "created_at": "2026-11-26T10:00:00Z",
                "updated_at": "2026-11-26T10:00:00Z",
                "active": True,
            },
            {
                "memory_id": "m-valid-2",
                "owner_id": self.boss_id,
                "domain": "boss_personal",
                "category": None,
                "content": {"text": "Boss is building Vennela MARK-II"},
                "session_id": None,
                "created_at": "2026-11-27T08:00:00+05:30",
                "updated_at": None,
                "active": True,
            },
        ]

        fake_client = _RowsSupabaseClient(rows_by_domain={"boss_personal": mixed_rows})
        repo = SupabaseMemoryRepository(fake_client)
        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: MemoryAPI(repo))

        with self.assertLogs("core.memory_contracts", level="INFO") as cm_contracts, \
             self.assertLogs("memory.repository", level="WARNING") as cm_repo:
            resp = provider.retrieve(
                MemoryRetrievalRequest(
                    query="Vennela UI",
                    user_id=self.boss_id,
                    metadata={"request_id": "req-mixed-1"},
                )
            )

        joined_context = "\n".join(resp.context_strings)
        self.assertIn("Boss prefers dark blue UI", joined_context)
        self.assertIn("Boss is building Vennela MARK-II", joined_context)
        self.assertNotIn(canary_secret_content, joined_context)

        self.assertEqual(resp.metadata["owner_id_queried"], self.boss_id)
        self.assertEqual(resp.metadata["raw_rows_fetched"], 6)
        self.assertEqual(resp.metadata["valid_rows_parsed"], 2)
        self.assertEqual(resp.metadata["skipped_rows_count"], 4)
        self.assertEqual(resp.metadata["retrieval_status"], "partial_success")

        all_logs = "\n".join(cm_contracts.output + cm_repo.output)
        self.assertIn('"owner_id_queried":', all_logs)
        self.assertIn('"raw_rows_fetched": 6', all_logs)
        self.assertIn('"valid_rows_parsed": 2', all_logs)
        self.assertIn('"skipped_rows_count": 4', all_logs)
        self.assertIn('"status": "partial_success"', all_logs)
        # Mandatory privacy rule: never log memory content or full rows
        self.assertNotIn(canary_secret_content, all_logs)
        self.assertNotIn("Boss prefers dark blue UI", all_logs)
        self.assertNotIn("Boss is building Vennela MARK-II", all_logs)

    def test_12_zero_row_retrieval_emits_diagnostic_warning(self):
        """Category G: zero rows fetched emits diagnostic warning listing possible causes."""
        empty_client = _RowsSupabaseClient(rows_by_domain={"boss_personal": []})
        repo = SupabaseMemoryRepository(empty_client)
        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: MemoryAPI(repo))

        with self.assertLogs("core.memory_contracts", level="WARNING") as cm:
            resp = provider.retrieve(MemoryRetrievalRequest(query="hello", user_id=self.boss_id))

        self.assertEqual(resp.memory_count, 0)
        self.assertEqual(resp.metadata["raw_rows_fetched"], 0)
        self.assertEqual(resp.metadata["retrieval_status"], "empty")
        warn_text = "\n".join(cm.output)
        self.assertIn("SUPABASE_KEY", warn_text)
        self.assertIn("service_role", warn_text)
        self.assertIn("VENNELA_BOSS_ID", warn_text)
        self.assertIn(self.boss_id, warn_text)


if __name__ == "__main__":
    unittest.main()
