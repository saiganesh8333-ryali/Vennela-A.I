"""
Vennela AI MARK-II — Brain B Production Activation Verification Suite
=====================================================================
Validates all 14 mandatory acceptance test requirements for Brain B
production activation under stateless memory isolation.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

# Ensure Backend root is in sys.path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Set test environment
os.environ["VENNELA_BOSS_ID"] = "boss_prod_test"
os.environ["VENNELA_AGENT_TOKEN"] = "token-prod-test-secret-987654321"
os.environ["LIGHTWEIGHT_MODE"] = "true"
os.environ["VENNELA_MEMORY_ENABLED"] = "false"
os.environ["LLM_ROUTER_MOCK"] = "true"

from fastapi.testclient import TestClient
import app as app_module
from app import app, validate_startup_security_config
from core.intelligence_contracts import BrainResult, DelegationType
from core.memory_contracts import (
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    get_memory_subsystem,
    reset_memory_subsystem,
)
from conversation.response_policy import ConversationAdjuster
from llm_router.adapter import VennelaLLMAdapter
from llm_router.contracts import FailureKind, RoutingError, Failure
from llm_router.gateway import Gateway
from llm_router.providers.base import classify_http_error
from llm_router.providers.openrouter import OpenRouterProvider
from llm_router.registry import ModelTier, default_model_registry
from production_langgraph_adapter import ProductionLangGraphBrain
from vennela_langgraph.core.intent import resolve_intent


class TestBrainBProductionActivation(unittest.TestCase):
    """Full 14-point test suite for Brain B production readiness."""

    @classmethod
    def setUpClass(cls):
        cls.token = os.environ["VENNELA_AGENT_TOKEN"]
        cls.boss_id = os.environ["VENNELA_BOSS_ID"]
        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}
        app_module._brain_instance = None
        app_module._llm_adapter_instance = VennelaLLMAdapter(mock=True)
        cls.client = TestClient(app)

    def setUp(self):
        # Reset instances to use mock adapter for tests
        reset_memory_subsystem()
        app_module._brain_instance = None
        app_module._llm_adapter_instance = VennelaLLMAdapter(mock=True)

    # -------------------------------------------------------------------------
    # TEST 1: Brain B Initialization Test
    # -------------------------------------------------------------------------
    def test_01_brain_b_initialization(self):
        """Verify ProductionLangGraphBrain initializes cleanly with decoupled contracts."""
        llm_adapter = VennelaLLMAdapter(mock=True)
        adjuster = ConversationAdjuster()
        brain = ProductionLangGraphBrain(llm_adapter, adjuster)
        self.assertEqual(brain.backend, "langgraph-production")
        self.assertIsNone(brain.pc_gateway)
        self.assertIsNone(brain.android_gateway)
        self.assertIsNone(brain.web_agent)

    # -------------------------------------------------------------------------
    # TEST 2: LangGraph Compilation Test
    # -------------------------------------------------------------------------
    def test_02_langgraph_compilation(self):
        """Verify LangGraph StateGraph builds and compiles all core execution nodes."""
        llm_adapter = VennelaLLMAdapter(mock=True)
        adjuster = ConversationAdjuster()
        brain = ProductionLangGraphBrain(llm_adapter, adjuster)
        graph = brain._get_graph([], None, [])
        self.assertIsNotNone(graph)
        self.assertIsNotNone(graph.compiled_graph)

        expected_nodes = {
            "intent", "planner", "memory", "web",
            "pc", "android", "verification", "reasoning",
            "fusion", "response",
        }
        for node in expected_nodes:
            self.assertIn(node, graph.nodes)

    # -------------------------------------------------------------------------
    # TEST 3: Intent Recognition Test
    # -------------------------------------------------------------------------
    def test_03_intent_recognition(self):
        """Verify intent resolver maps requests to canonical intents correctly."""
        conv_intent = resolve_intent("What is the capital of France?")
        self.assertFalse(conv_intent.requires_web)
        self.assertFalse(conv_intent.requires_pc)
        self.assertFalse(conv_intent.requires_android)

        web_intent = resolve_intent("Search the web for latest Mars rover news")
        self.assertTrue(web_intent.requires_web)

        pc_intent = resolve_intent("open notepad")
        self.assertTrue(pc_intent.requires_pc)

        android_intent = resolve_intent("turn on flashlight")
        self.assertTrue(android_intent.requires_android)

    # -------------------------------------------------------------------------
    # TEST 4: Planner Test
    # -------------------------------------------------------------------------
    def test_04_planner(self):
        """Verify PlannerNode produces valid structured PlanDetails."""
        from vennela_langgraph.nodes.planner_node import PlannerNode
        from vennela_langgraph.core.state import VennelaState
        from vennela_langgraph.observability.telemetry import InMemoryTelemetry

        telemetry = InMemoryTelemetry()
        planner_node = PlannerNode(telemetry)
        state = VennelaState(
            original_request="search the web for python 3.14 features",
            canonical_intent=resolve_intent("search the web for python 3.14 features"),
        )
        update = planner_node.execute(state)
        self.assertIn("plan_details", update.values)
        plan = update.values["plan_details"]
        self.assertGreater(len(plan.steps), 0)

    # -------------------------------------------------------------------------
    # TEST 5: Capability Dispatch Test
    # -------------------------------------------------------------------------
    def test_05_capability_dispatch(self):
        """Verify capability routing logic branches correctly based on requirements."""
        llm_adapter = VennelaLLMAdapter(mock=True)
        adjuster = ConversationAdjuster()
        brain = ProductionLangGraphBrain(llm_adapter, adjuster)

        # Standalone conversational request does not require device capabilities
        self.assertTrue(brain._supports_graph_request("Explain quantum entanglement"))

        # Device action without gateway is recognized as unsupported
        self.assertFalse(brain._supports_graph_request("open notepad"))

    # -------------------------------------------------------------------------
    # TEST 6: Stateless Chat Test
    # -------------------------------------------------------------------------
    def test_06_stateless_chat(self):
        """Verify chat executes through Brain B with memory strictly isolated."""
        with patch.dict(os.environ, {"VENNELA_MEMORY_PROVIDER": "stateless", "VENNELA_MEMORY_ENABLED": "false"}):
            reset_memory_subsystem()
            mem_subsystem = get_memory_subsystem()
            self.assertEqual(mem_subsystem.mode, MemoryIsolationMode.STATELESS_ISOLATED)

            resp = mem_subsystem.retrieve(
                MemoryRetrievalRequest(query="test", user_id=self.boss_id)
            )
            self.assertEqual(resp.context_strings, [])
            self.assertEqual(resp.memory_count, 0)

            # Chat through endpoint with Bearer auth
            payload = {"message": "Hello Vennela, how are you today?"}
            res = self.client.post("/chat", json=payload, headers=self.auth_headers)
            self.assertEqual(res.status_code, 200, f"Chat failed: {res.text}")
            data = res.json()
            self.assertIn("response", data)
            self.assertIn("request_id", data)
            self.assertTrue(len(data["response"]) > 0)

    # -------------------------------------------------------------------------
    # TEST 7: LLM Router Integration Test
    # -------------------------------------------------------------------------
    def test_07_llm_router_integration(self):
        """Verify LLM Router adapter correctly generates and returns structured result."""
        adapter = VennelaLLMAdapter(mock=True)
        result = adapter.route_text("Hello test")
        self.assertIn("text", result)
        self.assertIn("model_id", result)
        self.assertIn("provider", result)
        self.assertEqual(result["model_id"], "google/gemini-2.5-flash-lite")
        self.assertTrue(len(result["text"]) > 0)

    # -------------------------------------------------------------------------
    # TEST 8: OpenRouter Provider Contract Test
    # -------------------------------------------------------------------------
    def test_08_openrouter_provider_contract(self):
        """Verify OpenRouter provider adapter is registered with correct profile."""
        registry = default_model_registry()
        profile = registry.get("google/gemini-2.5-flash-lite")
        self.assertEqual(profile.provider, "openrouter")
        self.assertEqual(profile.tier, ModelTier.FAST)

        provider = OpenRouterProvider(api_key="sk-or-test-mock-key")
        self.assertEqual(provider.provider_name, "openrouter")
        self.assertEqual(provider.base_url, "https://openrouter.ai/api/v1/chat/completions")

    # -------------------------------------------------------------------------
    # TEST 9: Groq Fallback Test
    # -------------------------------------------------------------------------
    def test_09_groq_fallback_contract(self):
        """Verify provider error normalization and fallback capability."""
        # 1. Error normalization
        self.assertEqual(classify_http_error(429), FailureKind.RATE_LIMIT)
        self.assertEqual(classify_http_error(401), FailureKind.AUTHENTICATION)
        self.assertEqual(classify_http_error(408), FailureKind.TIMEOUT)
        self.assertEqual(classify_http_error(504), FailureKind.TIMEOUT)

        # 2. Fallback Engine verification via Gateway
        gateway = Gateway.create(mock=True)
        fallback_engine = gateway.router.fallback
        self.assertIsNotNone(fallback_engine)
        self.assertEqual(fallback_engine.emergency_model_id, "meta-llama/llama-3.1-8b-instruct")

    # -------------------------------------------------------------------------
    # TEST 10: Authentication Test
    # -------------------------------------------------------------------------
    def test_10_authentication_enforcement(self):
        """Verify authenticated request with valid Bearer token succeeds."""
        res = self.client.post(
            "/chat",
            json={"message": "System integrity check"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------------------
    # TEST 11: Unauthorized Request Rejection Test
    # -------------------------------------------------------------------------
    def test_11_unauthorized_request_rejection(self):
        """Verify missing, invalid, or empty Bearer token is rejected with 401."""
        # Missing auth header
        res1 = self.client.post("/chat", json={"message": "hello"})
        self.assertEqual(res1.status_code, 401)

        # Invalid token
        res2 = self.client.post(
            "/chat",
            json={"message": "hello"},
            headers={"Authorization": "Bearer invalid-wrong-token"},
        )
        self.assertEqual(res2.status_code, 401)

        # Malformed scheme
        res3 = self.client.post(
            "/chat",
            json={"message": "hello"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        self.assertEqual(res3.status_code, 401)

    # -------------------------------------------------------------------------
    # TEST 12: Error Recovery Test
    # -------------------------------------------------------------------------
    def test_12_error_recovery(self):
        """Verify Brain B returns structured BrainResult failure instead of crashing."""
        class CrashingLLM:
            def route_text(self, *args, **kwargs):
                raise RoutingError(
                    Failure(FailureKind.TIMEOUT, "Simulated timeout", True, "test")
                )

        brain = ProductionLangGraphBrain(CrashingLLM(), ConversationAdjuster())
        result = asyncio.run(brain.process("test message", request_id="req-fail-test"))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.decision, DelegationType.DIRECT)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error["code"], "PROVIDER_ERROR")

    # -------------------------------------------------------------------------
    # TEST 13: API Contract Regression Tests
    # -------------------------------------------------------------------------
    def test_13_api_contract_regression(self):
        """Verify chat request validation rejects empty or oversized payloads."""
        # Empty payload
        res_empty = self.client.post("/chat", json={}, headers=self.auth_headers)
        self.assertEqual(res_empty.status_code, 422)

        # Empty string
        res_blank = self.client.post("/chat", json={"message": ""}, headers=self.auth_headers)
        self.assertEqual(res_blank.status_code, 422)

        # Oversized message (> 8192 chars)
        oversized = "a" * 8193
        res_oversized = self.client.post("/chat", json={"message": oversized}, headers=self.auth_headers)
        self.assertEqual(res_oversized.status_code, 422)

        # Health endpoint
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "healthy")

    # -------------------------------------------------------------------------
    # TEST 14: Production Startup Test
    # -------------------------------------------------------------------------
    def test_14_production_startup(self):
        """Verify startup security gate enforces presence of required environment secrets."""
        # With env vars set: should not raise
        validate_startup_security_config()

        # With env vars missing: must raise RuntimeError
        with patch.dict(os.environ, {"VENNELA_AGENT_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                validate_startup_security_config()


if __name__ == "__main__":
    unittest.main()
