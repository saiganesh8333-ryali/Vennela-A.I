from types import SimpleNamespace
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from agents.brain import BrainResult
from agents.models import DelegationType
from app import app
from llm_router.adapter import VennelaLLMAdapter
from llm_router.gateway import Gateway
from llm_router.providers.mock import MockProvider
from llm_router.providers.mock import MockMode
from llm_router.registry import ModelProfile, ModelRegistry, ModelTier
from memory.models import MemoryCategory
from production_langgraph_adapter import ProductionLangGraphBrain


def test_production_langgraph_brain_isolates_overlapping_requests():
    class FakeLLM:
        def route_text(self, prompt, **kwargs):
            return {
                "text": prompt.split("USER:")[-1].splitlines()[0].strip(),
                "model_id": "mock",
                "provider": "mock",
                "latency_ms": 0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class NoFallback:
        async def process(self, *args, **kwargs):
            raise AssertionError("LangGraph unexpectedly used NEXUS fallback")

    brain = ProductionLangGraphBrain(
        NoFallback(),
        FakeLLM(),
        SimpleNamespace(),
    )

    def run(index):
        return asyncio.run(
            brain.process(
                f"hello-{index}",
                request_id=f"request-{index}",
                user_id=f"user-{index}",
                session_id=f"session-{index}",
                memory_context=[f"memory-{index}"],
            )
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(run, range(8)))

    assert all(result.status == "completed" for result in results)
    assert [
        result.metadata["session_id"] for result in results
    ] == [f"session-{index}" for index in range(8)]


@pytest.fixture
def chat_client(monkeypatch):
    provider = MockProvider("openrouter", "direct response")
    adapter = VennelaLLMAdapter(
        router=Gateway.create(
            custom_providers={"openrouter": provider},
        ).router
    )
    import app as app_module

    monkeypatch.setattr(app_module, "_llm_adapter_instance", adapter)
    monkeypatch.setattr(app_module, "_brain_instance", None)
    monkeypatch.setattr(
        app_module,
        "_basic_memory_api",
        lambda: (_ for _ in ()).throw(RuntimeError("memory unavailable in test")),
    )
    return TestClient(app), provider


def test_chat_direct_flow_uses_brain_router_and_history(chat_client):
    client, provider = chat_client
    response = client.post(
        "/chat",
        json={
            "message": "What is my name?",
            "session_id": "session-1",
            "messages": [
                {"role": "user", "content": "My name is Ganesh."},
                {"role": "assistant", "content": "Nice to meet you, Boss."},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["response"] == "direct response"
    assert len(provider.recorded_requests) == 1
    request = provider.recorded_requests[-1][0]
    messages = request.normalized_messages()
    # The temporal context system instruction is injected by the production
    # path and appears as the first system message.  Validate user/assistant
    # history is forwarded intact after it.
    user_assistant = [m for m in messages if m["role"] != "system"]
    assert user_assistant == [
        {"role": "user", "content": "My name is Ganesh."},
        {"role": "assistant", "content": "Nice to meet you, Boss."},
        {"role": "user", "content": "What is my name?"},
    ]


def test_chat_emits_correlated_safe_timing_log(chat_client, monkeypatch, caplog):
    import app as app_module

    class FakeBrain:
        async def process(self, task, *, request_id, messages, context):
            context["_timing"]["llm_events"].append(
                {
                    "duration_ms": 2.5,
                    "provider": "mock",
                    "model": "mock-model",
                    "success": True,
                    "fallback_used": False,
                    "attempt_count": 1,
                }
            )
            return BrainResult(
                request_id=request_id,
                status="completed",
                task=task,
                decision=DelegationType.DIRECT,
                response="timed response",
                metadata={"timings_ms": {"graph_execution": 3.5}},
            )

    monkeypatch.setattr(app_module, "get_brain", lambda: FakeBrain())
    request_id = "00000000-0000-4000-8000-000000000601"
    with caplog.at_level("INFO"):
        response = chat_client[0].post(
            "/chat",
            headers={"X-Request-ID": request_id},
            json={"message": "timing probe"},
        )

    assert response.status_code == 200
    timing_records = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("chat_timing ")
    ]
    assert len(timing_records) == 1
    timing = timing_records[0]
    assert f"request_id={request_id}" in timing
    assert "memory_stable_ms=" in timing
    assert "memory_relevant_ms=" in timing
    assert "langgraph_ms=3.5" in timing
    assert "llm_ms=2.5" in timing
    assert "timing probe" not in timing


def test_llm_adapter_timing_callback_preserves_router_result():
    events = []
    provider = MockProvider("openrouter", "timed response")
    adapter = VennelaLLMAdapter(
        router=Gateway.create(custom_providers={"openrouter": provider}).router
    )

    result = adapter.route_text(
        "timing request",
        timing_callback=events.append,
        request_id="00000000-0000-4000-8000-000000000602",
    )

    assert result["text"] == "timed response"
    assert len(events) == 1
    assert events[0]["success"] is True
    assert events[0]["provider"] == result["provider"]
    assert events[0]["model"] == result["model_id"]
    assert events[0]["duration_ms"] >= 0


def test_chat_delegated_flow_returns_brain_response(monkeypatch):
    import app as app_module

    class FakeBrain:
        async def process(self, task, *, request_id, messages, context):
            assert task == "What are the latest AI agent developments?"
            assert messages[-1] == {
                "role": "user",
                "content": task,
            }
            return BrainResult(
                request_id=request_id,
                status="completed",
                task=task,
                decision=DelegationType.DELEGATE,
                capability="web_research",
                agent_id="web_hunt",
                response="Research synthesis",
                model_id="conversation-model",
                provider="openrouter",
            )

    monkeypatch.setattr(app_module, "get_brain", lambda: FakeBrain())
    monkeypatch.setattr(
        app_module,
        "_basic_memory_api",
        lambda: (_ for _ in ()).throw(RuntimeError("memory unavailable in test")),
    )
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"message": "What are the latest AI agent developments?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "response": "Research synthesis",
        "request_id": response.json()["request_id"],
        "actions": [],
        "action_results": [],
    }


def test_chat_memory_context_and_session_scope_reach_brain(monkeypatch):
    import app as app_module

    captured = {}
    record = SimpleNamespace(
        memory_id="memory-1",
        content={"text": "User name is Ganesh"},
        active=True,
        category=MemoryCategory.PROFILE,
        updated_at=SimpleNamespace(timestamp=lambda: 1),
    )

    class FakeMemoryAPI:
        pass

    class FakeBrain:
        async def process(self, task, *, request_id, messages, context):
            captured.update(
                task=task,
                messages=messages,
                context=context,
            )
            return BrainResult(
                request_id=request_id,
                status="direct",
                task=task,
                decision=DelegationType.DIRECT,
                response="memory-aware response",
                model_id="conversation-model",
                provider="openrouter",
            )

    monkeypatch.setattr(app_module, "get_brain", lambda: FakeBrain())
    monkeypatch.setattr(app_module, "_basic_memory_context", lambda session_id: session_id)
    monkeypatch.setattr(app_module, "_basic_memory_api", lambda: FakeMemoryAPI())
    monkeypatch.setattr(app_module, "_retrieve_stable_chat_memories", lambda *args: [record])
    monkeypatch.setattr(app_module, "_retrieve_chat_memories", lambda *args: [])
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"message": "What is my name?", "session_id": "session-ganesh"},
    )

    assert response.status_code == 200
    assert captured["context"]["_system_instruction"].endswith(
        "Stable user context:\n- User name is Ganesh"
    )
    assert captured["messages"][-1] == {
        "role": "user",
        "content": "What is my name?",
    }


def test_chat_missing_session_id_preserves_existing_contract(chat_client):
    client, _ = chat_client

    response = client.post("/chat", json={"message": "Hello Vennela"})

    assert response.status_code == 200
    assert response.json()["response"] == "direct response"


def test_chat_uses_langgraph_when_enabled(chat_client, monkeypatch):
    import app as app_module

    monkeypatch.setenv("VENNELA_LANGGRAPH_ENABLED", "true")
    app_module._brain_instance = None
    response = chat_client[0].post(
        "/chat",
        json={
            "message": "Hello Vennela",
            "session_id": "graph-session",
            "messages": [{"role": "user", "content": "Earlier message"}],
        },
    )

    assert response.status_code == 200
    assert isinstance(app_module.get_brain(), ProductionLangGraphBrain)
    assert chat_client[1].recorded_requests


def test_production_chat_passes_history_session_and_memory_to_langgraph(
    chat_client, monkeypatch
):
    import app as app_module

    captured = {}

    class FakeGraph:
        def run(self, request, **kwargs):
            captured.update(request=request, **kwargs)
            return SimpleNamespace(
                request_id=kwargs["request_id"],
                status="completed",
                response="graph response",
                errors=[],
                session_id=kwargs["session_id"],
                memory_context=kwargs["memory_context"],
                messages=kwargs["messages"],
            )

    monkeypatch.setenv("VENNELA_LANGGRAPH_ENABLED", "true")
    monkeypatch.setattr(
        ProductionLangGraphBrain,
        "_get_graph",
        lambda self, memory_context, system_instruction, messages: FakeGraph(),
    )
    record = SimpleNamespace(
        memory_id="memory-graph",
        content={"text": "User prefers concise answers"},
        active=True,
        category=MemoryCategory.PREFERENCE,
        updated_at=SimpleNamespace(timestamp=lambda: 1),
    )
    monkeypatch.setattr(app_module, "_basic_memory_context", lambda session_id: session_id)
    monkeypatch.setattr(app_module, "_basic_memory_api", lambda: object())
    monkeypatch.setattr(app_module, "_retrieve_stable_chat_memories", lambda *args: [record])
    monkeypatch.setattr(app_module, "_retrieve_chat_memories", lambda *args: [])
    app_module._brain_instance = None

    response = chat_client[0].post(
        "/chat",
        json={
            "message": "What should I do?",
            "user_id": "user-1",
            "session_id": "session-1",
            "messages": [{"role": "user", "content": "Earlier context"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["response"] == "graph response"
    assert captured["session_id"] == "session-1"
    assert captured["user_id"] == "user-1"
    assert captured["memory_context"] == ["User prefers concise answers"]
    assert captured["messages"][-1] == {
        "role": "user",
        "content": "What should I do?",
    }


def test_langgraph_adapter_translates_production_inputs(monkeypatch):
    captured = {}

    class FakeGraph:
        def run(self, request, **kwargs):
            captured.update(request=request, **kwargs)
            return SimpleNamespace(
                request_id=kwargs["request_id"],
                status="completed",
                response="graph response",
                errors=[],
                session_id=kwargs["session_id"],
                memory_context=kwargs["memory_context"],
                messages=kwargs["messages"],
            )

    class LegacyBrain:
        async def process(self, *args, **kwargs):
            raise AssertionError("legacy fallback was not expected")

    adapter = ProductionLangGraphBrain(
        LegacyBrain(),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    monkeypatch.setattr(adapter, "_supports_graph_request", lambda request: True)
    monkeypatch.setattr(
        adapter,
        "_get_graph",
        lambda memory_context, system_instruction, messages: FakeGraph(),
    )

    result = asyncio.run(adapter.process(
        "What is my name?",
        request_id="request-1",
        messages=[
            {"role": "user", "content": "My name is Ganesh."},
            {"role": "user", "content": "What is my name?"},
        ],
        context={
            "_system_instruction": "system",
            "_session_id": "session-1",
            "_user_id": "user-1",
            "_memory_context": ["User name is Ganesh"],
        },
    ))

    assert result.response == "graph response"
    assert captured["request"] == "What is my name?"
    assert captured["request_id"] == "request-1"
    assert captured["session_id"] == "session-1"
    assert captured["user_id"] == "user-1"
    assert captured["memory_context"] == ["User name is Ganesh"]
    assert captured["messages"][0]["content"] == "My name is Ganesh."


def test_unmocked_production_graph_run_keeps_lab_contracts_available():
    class LocalLLMAdapter:
        def route_text(self, prompt, **kwargs):
            return {
                "text": "local graph response",
                "model_id": "local-model",
                "provider": "local-mock",
                "latency_ms": 0.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class LegacyBrain:
        async def process(self, *args, **kwargs):
            raise AssertionError("NEXUS fallback was called")

    adapter = ProductionLangGraphBrain(
        LegacyBrain(),
        LocalLLMAdapter(),
        SimpleNamespace(),
    )
    result = asyncio.run(adapter.process(
        "Hello locally",
        request_id="request-graph",
        context={"_system_instruction": "local"},
        messages=[{"role": "user", "content": "Hello locally"}],
        session_id="session-graph",
        user_id="user-graph",
        memory_context=["local memory"],
    ))

    assert result.response == "local graph response"
    assert result.metadata["execution"] == "langgraph"
    assert result.metadata["session_id"] == "session-graph"
    assert result.metadata["memory_count"] == 1


def test_production_pc_adapter_uses_gateway_and_preserves_verification():
    from production_capability_adapters import ProductionPCAgent
    from automation import AgentPlatform, ActionType, AgentGateway, MockExecutionAgent

    gateway = AgentGateway()
    agent = MockExecutionAgent(
        platform=AgentPlatform.PC,
        capabilities=frozenset({ActionType.OPEN_APP}),
    )
    gateway.register_agent(agent)

    result = ProductionPCAgent(gateway).execute("OPEN_APP:notepad")

    assert result["executed"] is True
    assert result["verified"] is True
    assert result["verification_status"] == "verified"
    assert result["result"]["output"]["target"] == "notepad"
    assert agent.executed_actions[0][0].type is ActionType.OPEN_APP


def test_production_graph_executes_pc_branch_without_nexus_fallback():
    from production_capability_adapters import ProductionPCAgent
    from automation import AgentPlatform, ActionType, AgentGateway, MockExecutionAgent

    gateway = AgentGateway()
    gateway.register_agent(
        MockExecutionAgent(
            platform=AgentPlatform.PC,
            capabilities=frozenset({ActionType.OPEN_APP}),
        )
    )

    class LocalLLMAdapter:
        def route_text(self, prompt, **kwargs):
            return {
                "text": "local PC response",
                "model_id": "local-model",
                "provider": "local-mock",
                "latency_ms": 0.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class LegacyBrain:
        async def process(self, *args, **kwargs):
            raise AssertionError("NEXUS fallback was called")

    adapter = ProductionLangGraphBrain(
        LegacyBrain(),
        LocalLLMAdapter(),
        SimpleNamespace(),
        pc_gateway=gateway,
    )
    result = asyncio.run(adapter.process(
        "open notepad",
        request_id="request-pc",
        messages=[{"role": "user", "content": "open notepad"}],
        session_id="session-pc",
        user_id="user-pc",
    ))

    assert result.response == "local PC response"
    assert result.metadata["execution"] == "langgraph"


def test_production_android_adapter_uses_shared_gateway_and_preserves_results():
    from production_capability_adapters import ProductionAndroidAgent
    from automation import AgentPlatform, ActionType, AgentGateway, MockExecutionAgent

    gateway = AgentGateway()
    agent = MockExecutionAgent(
        platform=AgentPlatform.ANDROID,
        capabilities=frozenset({ActionType.FLASHLIGHT_ON}),
    )
    gateway.register_agent(agent)

    result = ProductionAndroidAgent(gateway).execute_with_context(
        "FLASHLIGHT",
        "turn on flashlight",
    )

    assert result["executed"] is True
    assert result["verified"] is True
    assert result["status"] == "verified"
    assert result["metadata"]["execution"]["success"] is True
    assert result["metadata"]["verification"]["details"]["action"] == "FLASHLIGHT_ON"
    assert agent.executed_actions[0][0].type is ActionType.FLASHLIGHT_ON


def test_production_android_adapter_preserves_failure_result():
    from production_capability_adapters import ProductionAndroidAgent
    from automation import AgentPlatform, ActionType, AgentGateway, MockExecutionAgent

    gateway = AgentGateway()
    gateway.register_agent(
        MockExecutionAgent(
            platform=AgentPlatform.ANDROID,
            capabilities=frozenset({ActionType.FLASHLIGHT_OFF}),
            default_success=False,
        )
    )

    result = ProductionAndroidAgent(gateway).execute("FLASHLIGHT_OFF")

    assert result["executed"] is False
    assert result["verified"] is False
    assert result["status"] == "failed"
    assert result["error"] == "Mock execution simulated failure"


def test_production_graph_executes_android_branch_without_nexus_fallback():
    from production_capability_adapters import ProductionAndroidAgent
    from automation import AgentPlatform, ActionType, AgentGateway, MockExecutionAgent

    gateway = AgentGateway()
    gateway.register_agent(
        MockExecutionAgent(
            platform=AgentPlatform.ANDROID,
            capabilities=frozenset({ActionType.FLASHLIGHT_ON}),
        )
    )

    class LocalLLMAdapter:
        def route_text(self, prompt, **kwargs):
            return {
                "text": "local Android response",
                "model_id": "local-model",
                "provider": "local-mock",
                "latency_ms": 0.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class LegacyBrain:
        async def process(self, *args, **kwargs):
            raise AssertionError("NEXUS fallback was called")

    adapter = ProductionLangGraphBrain(
        LegacyBrain(),
        LocalLLMAdapter(),
        SimpleNamespace(),
        android_gateway=gateway,
    )
    result = asyncio.run(adapter.process(
        "turn on flashlight",
        request_id="request-android",
        messages=[{"role": "user", "content": "turn on flashlight"}],
        session_id="session-android",
        user_id="user-android",
    ))

    assert result.response == "local Android response"
    assert result.metadata["execution"] == "langgraph"


def test_production_web_adapter_preserves_research_result():
    from production_capability_adapters import ProductionWebAgent
    from web_intelligence.models import ResearchResult, SourceProvenance, ExtractedFact

    captured = {}

    class FakeWebHuntAgent:
        async def run(self, request):
            captured["request"] = request
            return ResearchResult(
                original_query=request,
                needs_search=True,
                sources=[SourceProvenance(
                    url="https://example.test/source",
                    domain="example.test",
                    title="Example source",
                    snippet="A useful source",
                )],
                extracted_information=[ExtractedFact(
                    fact="A preserved finding",
                    source_url="https://example.test/source",
                    source_domain="example.test",
                )],
                key_findings=["A preserved finding"],
                uncertainties=["Needs confirmation"],
                errors_and_warnings=[],
                metadata={"provider": "mock-web", "status": "completed"},
            )

    result = ProductionWebAgent(FakeWebHuntAgent()).search("research this")

    assert captured["request"] == "research this"
    assert result["executed"] is True
    assert result["verified"] is True
    assert result["status"] == "completed"
    assert result["sources"][0]["url"] == "https://example.test/source"
    assert result["findings"] == ["A preserved finding"]
    assert result["uncertainties"] == ["Needs confirmation"]
    assert result["metadata"]["provider"] == "mock-web"


def test_production_web_adapter_preserves_failure():
    from production_capability_adapters import ProductionWebAgent
    from web_intelligence.models import ResearchResult

    class FakeWebHuntAgent:
        async def run(self, request):
            return ResearchResult(
                original_query=request,
                needs_search=True,
                uncertainties=["provider unavailable"],
                errors_and_warnings=["provider unavailable"],
                metadata={"status": "failed", "error_code": "ENGINE_FAILURE"},
            )

    result = ProductionWebAgent(FakeWebHuntAgent()).search("research failure")

    assert result["executed"] is False
    assert result["verified"] is False
    assert result["status"] == "failed"
    assert result["error"] == "provider unavailable"


def test_production_graph_executes_web_branch_without_nexus_fallback():
    from production_capability_adapters import ProductionWebAgent
    from web_intelligence.models import ResearchResult, SourceProvenance, ExtractedFact

    class FakeWebHuntAgent:
        async def run(self, request):
            return ResearchResult(
                original_query=request,
                needs_search=True,
                sources=[SourceProvenance(
                    url="https://example.test/source",
                    domain="example.test",
                    title="Mock source",
                )],
                extracted_information=[ExtractedFact(
                    fact="Mock web result",
                    source_url="https://example.test/source",
                    source_domain="example.test",
                )],
                key_findings=["Mock web result"],
                metadata={"provider": "mock-web", "status": "completed"},
            )

    class LocalLLMAdapter:
        def route_text(self, prompt, **kwargs):
            return {
                "text": "local Web response",
                "model_id": "local-model",
                "provider": "local-mock",
                "latency_ms": 0.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class LegacyBrain:
        async def process(self, *args, **kwargs):
            raise AssertionError("NEXUS fallback was called")

    adapter = ProductionLangGraphBrain(
        LegacyBrain(),
        LocalLLMAdapter(),
        SimpleNamespace(),
        web_agent=FakeWebHuntAgent(),
    )
    result = asyncio.run(adapter.process(
        "research web sources",
        request_id="request-web",
        messages=[{"role": "user", "content": "research web sources"}],
        session_id="session-web",
        user_id="user-web",
    ))

    assert result.response == "local Web response"
    assert result.metadata["execution"] == "langgraph"


def test_langgraph_disabled_keeps_nexus_path(chat_client, monkeypatch):
    import app as app_module

    monkeypatch.setenv("VENNELA_LANGGRAPH_ENABLED", "false")
    app_module._brain_instance = None
    response = chat_client[0].post("/chat", json={"message": "Hello Vennela"})

    assert response.status_code == 200
    assert type(app_module.get_brain()).__name__ == "VennelaBrain"
    assert response.json()["response"] == "direct response"


def test_langgraph_failure_falls_back_to_nexus():
    class LegacyBrain:
        async def process(self, task, **kwargs):
            return BrainResult(
                request_id=kwargs["request_id"],
                status="direct",
                task=task,
                decision=DelegationType.DIRECT,
                response="safe fallback",
            )

    adapter = ProductionLangGraphBrain(
        LegacyBrain(),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    adapter._supports_graph_request = lambda request: True
    adapter._get_graph = lambda *args: (_ for _ in ()).throw(RuntimeError("graph unavailable"))

    result = asyncio.run(adapter.process(
        "Hello",
        request_id="request-2",
        context={},
        messages=[],
    ))

    assert result.response == "safe fallback"
    assert "graph unavailable" not in result.response


def test_chat_provider_503_uses_fallback_and_preserves_request_id(monkeypatch):
    import app as app_module

    primary = MockProvider("groq", "primary", failures=[MockMode.SERVER_ERROR_500])
    fallback = MockProvider("openrouter", "fallback")
    registry = ModelRegistry(
        [
            ModelProfile(
                "primary", "groq", tier=ModelTier.GENERAL, quality_score=1.0,
                conversation_strength=1.0, latency_ms=100,
            ),
            ModelProfile(
                "fallback", "openrouter", tier=ModelTier.GENERAL, quality_score=0.8,
                conversation_strength=0.8, latency_ms=200,
            ),
        ]
    )
    adapter = VennelaLLMAdapter(
        router=Gateway.create(
            custom_providers={"groq": primary, "openrouter": fallback},
            registry=registry,
        ).router
    )
    monkeypatch.setattr(app_module, "_llm_adapter_instance", adapter)
    monkeypatch.setattr(app_module, "_brain_instance", None)
    monkeypatch.setattr(
        app_module,
        "_basic_memory_api",
        lambda: (_ for _ in ()).throw(RuntimeError("memory unavailable in test")),
    )

    response = TestClient(app).post(
        "/chat",
        headers={"X-Request-ID": "header-request-id"},
        json={"message": "Hello Vennela"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "header-request-id"
    assert response.json()["response"] == "fallback"


def test_chat_unrecoverable_provider_failure_has_deliberate_503(monkeypatch):
    import app as app_module

    primary = MockProvider(
        "openrouter",
        "primary",
        failures=[MockMode.SERVER_ERROR_500] * 3,
    )
    groq = MockProvider("groq", "groq", failures=[MockMode.SERVER_ERROR_500] * 3)
    monkeypatch.setattr(
        app_module,
        "_llm_adapter_instance",
        VennelaLLMAdapter(
            router=Gateway.create(
                custom_providers={"openrouter": primary, "groq": groq}
            ).router
        ),
    )
    monkeypatch.setattr(app_module, "_brain_instance", None)
    monkeypatch.setattr(
        app_module,
        "_basic_memory_api",
        lambda: (_ for _ in ()).throw(RuntimeError("memory unavailable in test")),
    )

    response = TestClient(app).post("/chat", json={"message": "Hello Vennela"})

    assert response.status_code == 503
    assert response.json()["detail"] == "AI services temporarily unavailable. Please try again later."
