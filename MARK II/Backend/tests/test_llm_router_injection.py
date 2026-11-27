import os
import sys
import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
for p in (BACKEND_ROOT, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from app import app, get_llm_adapter, get_conversation_adjuster
from llm_router.adapter import VennelaLLMAdapter
from llm_router.gateway import Gateway
from llm_router.providers.mock import MockProvider, MockMode
from llm_router.registry import ModelProfile, ModelRegistry, ModelTier
from llm_router.contracts import LLMRequest, TaskType
from llm_router.config import RouterConfig
from conversation.response_policy import ConversationAdjuster, DetailLevel
try:
    from ai.ai_router import get_ai_response
except ImportError:
    get_ai_response = None


@pytest.fixture
def client_with_mock_router(monkeypatch):
    groq_p = MockProvider('groq', 'Mock Groq response', stream_chunks=['Streaming ', 'from ', 'Vennela'])
    or_p = MockProvider('openrouter', 'Mock OpenRouter response', stream_chunks=['Streaming ', 'from ', 'OpenRouter'])
    gateway = Gateway.create(custom_providers={'groq': groq_p, 'openrouter': or_p})
    mock_adapter = VennelaLLMAdapter(router=gateway.router)
    
    import app as app_module
    monkeypatch.setattr(app_module, '_llm_adapter_instance', mock_adapter)
    token = os.environ.get("VENNELA_AGENT_TOKEN", "token_test")
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


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
    assert data['response'] in {'Mock OpenRouter response', 'Mock Groq response'}


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


def test_fallback_attempts_emergency_candidate_after_provider_failures():
    primary = MockProvider("openrouter", "emergency", failures=[MockMode.SERVER_ERROR_500])
    alternate = MockProvider("groq", "alternate", failures=[MockMode.SERVER_ERROR_500])
    registry = ModelRegistry(
        [
            ModelProfile(
                "primary", "openrouter", tier=ModelTier.GENERAL, quality_score=1.0,
                conversation_strength=1.0, latency_ms=100,
            ),
            ModelProfile(
                "alternate", "groq", tier=ModelTier.GENERAL, quality_score=0.9,
                conversation_strength=0.9, latency_ms=150,
            ),
            ModelProfile(
                "meta-llama/llama-3.1-8b-instruct", "openrouter",
                tier=ModelTier.EMERGENCY, quality_score=0.5,
                conversation_strength=0.5, latency_ms=250,
            ),
        ]
    )
    gateway = Gateway.create(
        custom_providers={"openrouter": primary, "groq": alternate},
        registry=registry,
    )

    response, attempts = gateway.router.fallback.execute_completion(
        LLMRequest(prompt="Hello Vennela"),
        [
            ("primary", "openrouter"),
            ("alternate", "groq"),
            ("meta-llama/llama-3.1-8b-instruct", "openrouter"),
        ],
    )

    assert response.text == "emergency"
    assert response.provider == "openrouter"
    assert response.fallback_used is True
    assert primary.call_count == 2
    assert alternate.call_count == 1
    assert len(attempts) == 3


def test_router_passes_configured_emergency_model_to_fallback():
    config = RouterConfig(emergency_model_id="custom/emergency-model")
    gateway = Gateway.create(
        config=config,
        custom_providers={
            "openrouter": MockProvider("openrouter", "response"),
            "groq": MockProvider("groq", "response"),
        },
    )

    assert gateway.router.fallback.emergency_model_id == "custom/emergency-model"


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


def test_15_env_model_overrides_and_router_health_reporting(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("GROQ_MODEL", "qwen/qwen3-32b")

    cfg = RouterConfig.from_env()
    assert cfg.openrouter_model == "openai/gpt-4o-mini"
    assert cfg.groq_model == "qwen/qwen3-32b"
    assert cfg.default_model_id == "openai/gpt-4o-mini"

    groq_p = MockProvider("groq", "Mock Groq override")
    or_p = MockProvider("openrouter", "Mock OpenRouter override")
    adapter = VennelaLLMAdapter(
        router=Gateway.create(
            config=cfg,
            custom_providers={"openrouter": or_p, "groq": groq_p},
        ).router
    )

    health = adapter.health_summary()
    assert health["openrouter"]["model_id"] == "openai/gpt-4o-mini"
    assert health["groq"]["model_id"] == "qwen/qwen3-32b"

    result = adapter.route_text("Hello Vennela")
    assert result["provider"] == "openrouter"
    assert result["model_id"] == "openai/gpt-4o-mini"

    import app as app_module
    monkeypatch.setattr(app_module, "_llm_adapter_instance", adapter)
    token = os.environ.get("VENNELA_AGENT_TOKEN", "token_test")
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/router/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["openrouter"]["model_id"] == "openai/gpt-4o-mini"
    assert payload["groq"]["model_id"] == "qwen/qwen3-32b"


def test_16_default_router_health_populates_active_models(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    adapter = VennelaLLMAdapter(mock=True)
    health = adapter.health_summary()
    assert health["openrouter"]["model_id"] == "google/gemini-2.5-flash-lite"
    assert health["groq"]["model_id"] == "llama-3.3-70b-versatile"


def test_17_configured_provider_priority_when_other_key_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_configured_key")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    cfg = RouterConfig.from_env()
    gw = Gateway.create(config=cfg)
    chain = gw.router.build_candidate_chain(LLMRequest(prompt="Hello"), TaskType.CONVERSATION)
    assert chain[0] == ("llama-3.3-70b-versatile", "groq")


def test_18_provider_error_diagnostics_preserve_status_and_redact_secrets(monkeypatch):
    from io import BytesIO
    from urllib.error import HTTPError
    from llm_router.contracts import FailureKind, RoutingError
    from llm_router.providers.groq import GroqProvider
    from llm_router.providers.openrouter import OpenRouterProvider

    assert GroqProvider.base_url == "https://api.groq.com/openai/v1/chat/completions"
    assert OpenRouterProvider.base_url == "https://openrouter.ai/api/v1/chat/completions"

    # 1. Groq 404 preserves status_code=404 and upstream message without exposing key
    def fake_urlopen_404(req, timeout=30.0):
        raise HTTPError(
            req.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=BytesIO(b'{"error":{"message":"The model foo does not exist (Bearer gsk_secret_123456789)","code":"model_not_found"}}'),
        )

    monkeypatch.setattr("llm_router.providers.base.urlopen", fake_urlopen_404)
    groq = GroqProvider(api_key="gsk_secret_123456789")
    with pytest.raises(RoutingError) as exc_info:
        groq.complete(LLMRequest(prompt="hi"), "foo")
    assert exc_info.value.failure.kind == FailureKind.MODEL_UNAVAILABLE
    assert exc_info.value.failure.status_code == 404
    assert "model_not_found" in exc_info.value.failure.message
    assert "gsk_secret_123456789" not in exc_info.value.failure.message

    # 2. OpenRouter HTTP-200 JSON error payload is classified with error code & message
    class _FakeResp:
        status = 200
        def __init__(self, data: bytes) -> None:
            self._data = data
        def read(self) -> bytes:
            return self._data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "llm_router.providers.base.urlopen",
        lambda req, timeout=30.0: _FakeResp(b'{"error":{"message":"Insufficient credits","code":402}}'),
    )
    openrouter = OpenRouterProvider(api_key="sk-or-v1-secret-test")
    with pytest.raises(RoutingError) as or_exc:
        openrouter.complete(LLMRequest(prompt="hi"), "meta-llama/llama-3.1-8b-instruct")
    assert or_exc.value.failure.kind == FailureKind.RATE_LIMIT
    assert or_exc.value.failure.status_code == 402
    assert "Insufficient credits" in or_exc.value.failure.message

    # 3. Streaming SSE error event raises classified RoutingError with status & message
    class _FakeSSEResp:
        status = 200
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines
        def __iter__(self):
            return iter(self._lines)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "llm_router.providers.base.urlopen",
        lambda req, timeout=30.0: _FakeSSEResp([b'data: {"error":{"message":"Model not found","code":404}}\n']),
    )
    with pytest.raises(RoutingError) as stream_exc:
        list(openrouter.stream(LLMRequest(prompt="hi"), "bad/model"))
    assert stream_exc.value.failure.kind == FailureKind.MODEL_UNAVAILABLE
    assert stream_exc.value.failure.status_code == 404
    assert "Model not found" in stream_exc.value.failure.message
