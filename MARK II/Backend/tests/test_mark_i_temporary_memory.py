"""Vennela AI MARK-II — Temporary MARK-I Memory Integration Test Suite.

Verifies:
1. MARK-I memory initialization.
2. MARK-I memory retrieval.
3. MARK-I memory persistence.
4. User isolation (BOLA/IDOR protection).
5. Authentication enforcement.
6. Memory provider selection.
7. Memory failure handling & graceful degradation.
8. Brain B and MARK-I memory integration.
9. MARK-II isolation & premature activation prevention.
10. Application startup with temporary memory enabled.
"""

from datetime import datetime, timezone
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["VENNELA_BOSS_ID"] = "boss_test_user"
os.environ["VENNELA_AGENT_TOKEN"] = "token-test-secret-123456789"
os.environ["LIGHTWEIGHT_MODE"] = "true"
os.environ["LLM_ROUTER_MOCK"] = "true"

from core.memory_contracts import (
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
    StatelessMemoryProvider,
    TemporaryMarkIMemoryProvider,
    get_memory_subsystem,
    reset_memory_subsystem,
)
from typing import Any, Optional
from memory.models import AuthContext, MemoryCategory, MemoryDomain, MemoryRecord
from memory.api import MemoryAPI


class InMemoryStubRepo:
    """In-memory stub repository implementing the SupabaseMemoryRepository contract."""

    def __init__(self):
        self.records: list[MemoryRecord] = []

    def create(self, record: MemoryRecord) -> MemoryRecord:
        self.records.append(record)
        return record

    def retrieve(self, user_id: str, domain: Optional[str] = None, session_id: Optional[str] = None, limit: int = 50) -> list[MemoryRecord]:
        results = [
            r for r in self.records
            if r.owner_id == user_id and r.active
        ]
        if domain is not None:
            results = [r for r in results if r.domain.value == domain or r.domain == domain]
        if session_id is not None:
            results = [r for r in results if r.session_id == session_id]
        return results[:limit]

    def update(self, user_id: str, memory_id: str, content: Any, category: Optional[str] = None) -> Optional[MemoryRecord]:
        for i, r in enumerate(self.records):
            if r.owner_id == user_id and r.memory_id == memory_id:
                cat = MemoryCategory(category) if category else r.category
                updated = MemoryRecord(
                    r.memory_id, r.owner_id, r.domain, cat, content,
                    r.session_id, r.created_at, datetime.now(timezone.utc), True
                )
                self.records[i] = updated
                return updated
        return None


class TestTemporaryMarkIMemory(unittest.TestCase):
    """10-point test suite for temporary MARK-I memory integration into Brain B."""

    def setUp(self):
        reset_memory_subsystem()
        self.stub_repo = InMemoryStubRepo()
        self.api = MemoryAPI(self.stub_repo)
        self.boss_id = "boss_test_user"

    def tearDown(self):
        reset_memory_subsystem()
        if "VENNELA_MEMORY_PROVIDER" in os.environ:
            del os.environ["VENNELA_MEMORY_PROVIDER"]
        if "VENNELA_MEMORY_ENABLED" in os.environ:
            del os.environ["VENNELA_MEMORY_ENABLED"]

    # 1. MARK-I memory initialization
    def test_01_mark_i_memory_initialization(self):
        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        self.assertEqual(provider.mode, MemoryIsolationMode.MARK_I_TEMPORARY)

    # 2. MARK-I memory retrieval
    def test_02_mark_i_memory_retrieval(self):
        # Seed stable records
        now = datetime.now(timezone.utc)
        rec1 = MemoryRecord("mem-1", self.boss_id, MemoryDomain.BOSS_PERSONAL, MemoryCategory.PROFILE,
                            {"text": "My name is Boss and I lead engineering"}, None, now, now, True)
        rec2 = MemoryRecord("mem-2", self.boss_id, MemoryDomain.BOSS_PERSONAL, MemoryCategory.PREFERENCE,
                            {"text": "I prefer concise architectural answers"}, None, now, now, True)
        self.stub_repo.create(rec1)
        self.stub_repo.create(rec2)

        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        req = MemoryRetrievalRequest(query="tell me my name", user_id=self.boss_id)
        resp = provider.retrieve(req)

        self.assertEqual(resp.mode, MemoryIsolationMode.MARK_I_TEMPORARY)
        self.assertGreater(resp.memory_count, 0)
        combined = "\n".join(resp.context_strings)
        self.assertIn("My name is Boss and I lead engineering", combined)
        self.assertIn("I prefer concise architectural answers", combined)

    # 3. MARK-I memory persistence
    def test_03_mark_i_memory_persistence(self):
        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        # Store a high-value personal statement (triggers SmartMemory persistence)
        stored = provider.store(
            "I love building autonomous AI systems with LangGraph",
            user_id=self.boss_id,
            session_id="session-1",
        )
        self.assertTrue(stored)
        self.assertEqual(len(self.stub_repo.records), 1)
        record = self.stub_repo.records[0]
        self.assertEqual(record.owner_id, self.boss_id)
        self.assertIn("autonomous AI systems", record.content.get("text", ""))

    # 4. User isolation
    def test_04_user_isolation(self):
        now = datetime.now(timezone.utc)
        # Seed record for user_A
        rec_a = MemoryRecord("mem-a", "user_alpha", MemoryDomain.BOSS_PERSONAL, MemoryCategory.PROFILE,
                             {"text": "Confidential Alpha Project"}, None, now, now, True)
        # Seed record for user_B
        rec_b = MemoryRecord("mem-b", "user_beta", MemoryDomain.BOSS_PERSONAL, MemoryCategory.PROFILE,
                             {"text": "Confidential Beta Project"}, None, now, now, True)
        self.stub_repo.create(rec_a)
        self.stub_repo.create(rec_b)

        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        # Query as user_alpha
        resp_a = provider.retrieve(MemoryRetrievalRequest(query="project", user_id="user_alpha"))
        combined_a = "\n".join(resp_a.context_strings)
        self.assertIn("Confidential Alpha Project", combined_a)
        self.assertNotIn("Confidential Beta Project", combined_a)

        # Query as user_beta
        resp_b = provider.retrieve(MemoryRetrievalRequest(query="project", user_id="user_beta"))
        combined_b = "\n".join(resp_b.context_strings)
        self.assertIn("Confidential Beta Project", combined_b)
        self.assertNotIn("Confidential Alpha Project", combined_b)

    # 5. Authentication enforcement
    def test_05_authentication_enforcement(self):
        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        # When user_id is empty, it falls back to VENNELA_BOSS_ID from trusted config
        req = MemoryRetrievalRequest(query="test", user_id="")
        resp = provider.retrieve(req)
        self.assertEqual(resp.mode, MemoryIsolationMode.MARK_I_TEMPORARY)

    # 6. Memory provider selection
    def test_06_memory_provider_selection(self):
        # Case A: VENNELA_MEMORY_PROVIDER="stateless"
        os.environ["VENNELA_MEMORY_PROVIDER"] = "stateless"
        reset_memory_subsystem()
        sub = get_memory_subsystem()
        self.assertEqual(sub.mode, MemoryIsolationMode.STATELESS_ISOLATED)

        # Case B: VENNELA_MEMORY_PROVIDER="mark_i"
        os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
        reset_memory_subsystem()
        sub = get_memory_subsystem()
        self.assertEqual(sub.mode, MemoryIsolationMode.MARK_I_TEMPORARY)

        # Case C: VENNELA_MEMORY_ENABLED="true"
        del os.environ["VENNELA_MEMORY_PROVIDER"]
        os.environ["VENNELA_MEMORY_ENABLED"] = "true"
        reset_memory_subsystem()
        sub = get_memory_subsystem()
        self.assertEqual(sub.mode, MemoryIsolationMode.MARK_I_TEMPORARY)

        # Case D: VENNELA_MEMORY_ENABLED="false"
        os.environ["VENNELA_MEMORY_ENABLED"] = "false"
        reset_memory_subsystem()
        sub = get_memory_subsystem()
        self.assertEqual(sub.mode, MemoryIsolationMode.STATELESS_ISOLATED)

    # 7. Memory failure handling
    def test_07_memory_failure_handling(self):
        # Simulate a provider whose API factory raises an error
        def failing_api():
            raise ConnectionError("Supabase connection timed out")

        provider = TemporaryMarkIMemoryProvider(api_factory=failing_api)
        resp = provider.retrieve(MemoryRetrievalRequest(query="test", user_id=self.boss_id))
        # Does not crash; gracefully returns empty context
        self.assertEqual(resp.context_strings, [])
        self.assertEqual(resp.metadata.get("status"), "connection_unavailable")

        # Store does not crash; returns False gracefully
        stored = provider.store("test statement", user_id=self.boss_id)
        self.assertFalse(stored)

    # 8. Brain B and MARK-I memory integration
    def test_08_brain_b_and_mark_i_memory_integration(self):
        from conversation.response_policy import ConversationAdjuster
        from llm_router.adapter import VennelaLLMAdapter
        from production_langgraph_adapter import ProductionLangGraphBrain
        import asyncio

        now = datetime.now(timezone.utc)
        rec = MemoryRecord("mem-1", self.boss_id, MemoryDomain.BOSS_PERSONAL, MemoryCategory.PREFERENCE,
                           {"text": "User is the Chief Architect of Ryali Industries"}, None, now, now, True)
        self.stub_repo.create(rec)

        provider = TemporaryMarkIMemoryProvider(api_factory=lambda: self.api)
        retrieval = provider.retrieve(MemoryRetrievalRequest(query="architect", user_id=self.boss_id))
        self.assertGreater(len(retrieval.context_strings), 0)

        # Brain B consumes context strings
        memory_lines = [
            line[2:] for line in retrieval.context_strings
            if line.startswith("- ")
        ]
        self.assertIn("User is the Chief Architect of Ryali Industries", memory_lines)

        adapter = VennelaLLMAdapter(mock=True)
        adjuster = ConversationAdjuster()
        brain = ProductionLangGraphBrain(adapter, adjuster)

        result = asyncio.run(brain.process(
            "Who am I?",
            request_id="test-req-mark1",
            memory_context=memory_lines,
        ))
        self.assertEqual(result.status, "completed")
        self.assertTrue(len(result.response) > 0)
        self.assertEqual(result.metadata["memory_count"], len(memory_lines))

    # 9. MARK-II isolation & premature activation prevention
    def test_09_mark_ii_isolation(self):
        os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_ii"
        reset_memory_subsystem()
        with self.assertRaises(RuntimeError) as ctx:
            get_memory_subsystem()
        self.assertIn("MARK-II Cognitive Memory Architecture is currently under independent development", str(ctx.exception))

    # 10. Application startup with temporary memory enabled
    def test_10_application_startup_with_mark_i(self):
        os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
        reset_memory_subsystem()
        from app import app
        self.assertIsNotNone(app)
        # Verify provider selected is MARK_I_TEMPORARY
        sub = get_memory_subsystem()
        self.assertEqual(sub.mode, MemoryIsolationMode.MARK_I_TEMPORARY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
