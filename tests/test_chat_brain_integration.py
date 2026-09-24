from types import SimpleNamespace

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
    request = provider.recorded_requests[-1][0]
    assert request.normalized_messages() == [
        {"role": "user", "content": "My name is Ganesh."},
        {"role": "assistant", "content": "Nice to meet you, Boss."},
        {"role": "user", "content": "What is my name?"},
    ]


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
