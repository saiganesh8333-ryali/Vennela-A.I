import pytest
from fastapi.testclient import TestClient

from app import app, get_llm_adapter, get_conversation_adjuster
from llm_router.adapter import VennelaLLMAdapter
from llm_router.gateway import Gateway
from llm_router.providers.mock import MockProvider, MockMode
from llm_router.registry import ModelProfile, ModelRegistry, ModelTier
from llm_router.contracts import LLMRequest, TaskType
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


def test_09_router_preserves_ordered_history_and_single_system_message():
    groq_p = MockProvider("groq", "history response")
    or_p = MockProvider("openrouter", "history response")
    gateway = Gateway.create(custom_providers={"groq": groq_p, "openrouter": or_p})
    adapter = VennelaLLMAdapter(router=gateway.router)

    adapter.route_text(
        "what is my father name",
        system_instruction="Vennela personality and memory context",
        messages=[
            {"role": "system", "content": "old system"},
            {"role": "user", "content": "my father name is Nageswara Rao"},
            {"role": "assistant", "content": "I noted that."},
            {"role": "user", "content": "what is my father name"},
        ],
    )

    recorded = (or_p.recorded_requests + groq_p.recorded_requests)[0][0]
    assert recorded.normalized_messages() == [
        {"role": "system", "content": "Vennela personality and memory context"},
        {"role": "user", "content": "my father name is Nageswara Rao"},
        {"role": "assistant", "content": "I noted that."},
        {"role": "user", "content": "what is my father name"},
    ]


def test_10_fallback_receives_identical_context():
    groq_p = MockProvider("groq", "fallback response", failures=[MockMode.SERVER_ERROR_500])
    or_p = MockProvider("openrouter", "fallback response")
    registry = ModelRegistry([
        ModelProfile(
            "primary", "groq", tier=ModelTier.GENERAL, quality_score=1.0,
            conversation_strength=1.0, latency_ms=100,
        ),
        ModelProfile(
            "fallback", "openrouter", tier=ModelTier.GENERAL, quality_score=0.8,
            conversation_strength=0.8, latency_ms=200,
        ),
    ])
    gateway = Gateway.create(
        custom_providers={"groq": groq_p, "openrouter": or_p},
        registry=registry,
    )
    adapter = VennelaLLMAdapter(router=gateway.router)
    history = [
        {"role": "system", "content": "memory: father is Nageswara Rao"},
        {"role": "user", "content": "my father name is Nageswara Rao"},
        {"role": "assistant", "content": "Understood, Boss."},
        {"role": "user", "content": "what is my father name"},
    ]

    adapter.route_text(history[-1]["content"], messages=history)

    recorded = or_p.recorded_requests + groq_p.recorded_requests
    assert len(recorded) >= 2
    assert recorded[0][0].normalized_messages() == recorded[1][0].normalized_messages()


def test_11_normal_conversation_preserves_personality_without_restrictions():
    adjuster = ConversationAdjuster()

    policy = adjuster.adjust(
        "Hello Vennela",
        user_system_instruction="Authoritative Vennela personality",
    )

    assert policy.system_instruction == "Authoritative Vennela personality"
    assert policy.max_tokens is None
    assert "1-3" not in policy.system_instruction


def test_12_explicit_concise_request_retains_concise_policy():
    adjuster = ConversationAdjuster()

    policy = adjuster.adjust(
        "Give me a brief answer",
        user_system_instruction="Authoritative Vennela personality",
    )

    assert policy.detail_level == DetailLevel.CONCISE
    assert policy.max_tokens == 150
    assert "Answer in 1-3 short sentences" in policy.system_instruction


def test_13_conversation_adjuster_does_not_classify_tasks():
    adjuster = ConversationAdjuster()

    for prompt in (
        "Hello Vennela",
        "Explain Python tuples",
        "Write a Python implementation of binary search",
        "Give me a brief answer about Python tuples",
    ):
        assert adjuster.adjust(prompt).task_hint is None


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Hello Vennela", TaskType.CONVERSATION),
        ("Explain Python tuples", TaskType.GENERAL_REASONING),
        ("Write a Python implementation of binary search", TaskType.CODING),
        ("Explain how binary search works", TaskType.GENERAL_REASONING),
        ("Write a website-search script", TaskType.CODING),
    ],
)
def test_14_router_owns_task_classification(prompt, expected):
    router = Gateway.create(
        custom_providers={
            "groq": MockProvider("groq", "classification response"),
            "openrouter": MockProvider("openrouter", "classification response"),
        }
    ).router

    assert router.infer_task_type(LLMRequest(prompt=prompt)) is expected
