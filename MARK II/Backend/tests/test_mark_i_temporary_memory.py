"""Vennela AI MARK-II — Temporary MARK-I Memory & Brain B Integration Test Suite."""

import os
import sys
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
from memory.repository import InMemoryMemoryRepository


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


if __name__ == "__main__":
    unittest.main()
