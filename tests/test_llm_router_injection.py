import pytest
from fastapi.testclient import TestClient

from app import app, get_llm_adapter, get_conversation_adjuster
from llm_router.adapter import VennelaLLMAdapter
from llm_router.gateway import Gateway
from llm_router.providers.mock import MockProvider, MockMode
from conversation.response_policy import ConversationAdjuster, DetailLevel
from ai.ai_router import get_ai_response


@pytest.fixture
def client_with_mock_router(monkeypatch):
    groq_p = MockProvider('groq', 'Mock Groq response', stream_chunks=['Streaming ', 'from ', 'Vennela'])
    or_p = MockProvider('openrouter', 'Mock OpenRouter response', stream_chunks=['Streaming ', 'from ', 'OpenRouter'])
    gateway = Gateway.create(custom_providers={'groq': groq_p, 'openrouter': or_p})
    mock_adapter = VennelaLLMAdapter(router=gateway.router)

    import app as app_module
    monkeypatch.setattr(app_module, '_llm_adapter_instance', mock_adapter)
    return TestClient(app)


def test_01_app_chat_conversational_endpoint(client_with_mock_router):
    resp = client_with_mock_router.post('/chat', json={'message': 'Hello Vennela'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'response' in data
    assert data['response'] == 'Mock OpenRouter response'


def test_02_app_chat_coding_request(client_with_mock_router):
    resp = client_with_mock_router.post('/chat', json={'message': 'Write a python function to reverse a string'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['response'] == 'Mock OpenRouter response'


def test_03_app_chat_reasoning_request(client_with_mock_router):
    resp = client_with_mock_router.post('/chat', json={'message': 'Explain in detail why HTTPS is more secure than HTTP'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['response'] == 'Mock OpenRouter response'


def test_04_app_chat_streaming_endpoint(client_with_mock_router):
    resp = client_with_mock_router.post('/chat/stream', json={'message': 'Tell me five facts about computers'})
    assert resp.status_code == 200
    text = resp.text
    assert len(text) > 0
    assert 'Streaming ' in text


def test_05_router_health_endpoint(client_with_mock_router):
    resp = client_with_mock_router.get('/router/health')
    assert resp.status_code == 200
    data = resp.json()
    assert 'openrouter' in data or 'groq' in data


def test_06_router_models_endpoint(client_with_mock_router):
    resp = client_with_mock_router.get('/router/models')
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 4


def test_07_status_endpoint_shows_router_active(client_with_mock_router):
    resp = client_with_mock_router.get('/status')
    assert resp.status_code == 200
    data = resp.json()
    assert 'router' in data
    assert data['router']['status'] == 'active'


def test_08_ai_router_get_ai_response_integration(monkeypatch):
    groq_p = MockProvider('groq', 'AI router mock response')
    or_p = MockProvider('openrouter', 'AI router mock response')
    gateway = Gateway.create(custom_providers={'groq': groq_p, 'openrouter': or_p})
    mock_adapter = VennelaLLMAdapter(router=gateway.router)

    import ai.ai_router as ai_module
    monkeypatch.setattr(ai_module, '_adapter', mock_adapter)

    res = get_ai_response([{'role': 'user', 'content': 'Test message'}])
    assert res['provider'] in {'openrouter', 'groq', 'LLMRouter'}
    assert res['response'] == 'AI router mock response'
