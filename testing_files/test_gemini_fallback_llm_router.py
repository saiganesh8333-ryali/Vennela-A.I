import os
import sys
import types
import pytest
from llm_router_gemini import get_multi_llm_router
from llm_provider_manager import ProviderType

class FakeGenai(types.ModuleType):
    def __init__(self, behavior):
        super().__init__('google.generativeai')
        self._behavior = behavior
    def configure(self, api_key=None):
        self._api_key = api_key
    class GenerativeModel:
        def __init__(self, model_id, system_instruction=None):
            self.model_id = model_id
        def generate_content(self, prompt):
            mod = sys.modules.get('google.generativeai')
            behavior = mod._behavior.get(self.model_id)
            if behavior is None:
                class R: pass
                r = R(); r.text = f'response from {self.model_id}'; return r
            if behavior[0] == 'success':
                class R: pass
                r = R(); r.text = behavior[1]; return r
            elif behavior[0] == 'error':
                ex = Exception(behavior[1])
                if len(behavior) > 2:
                    setattr(ex, 'status_code', behavior[2])
                raise ex

@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv('GEMINI_MODEL_CHAIN', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    yield


def test_llm_router_uses_centralized_chain(monkeypatch):
    # Provide GEMINI_MODEL_CHAIN
    monkeypatch.setenv('GEMINI_MODEL_CHAIN', 'alpha,beta')
    behavior = {
        'alpha': ('error', 'quota exceeded'),
        'beta': ('success', 'beta ok')
    }
    fake = FakeGenai(behavior)
    monkeypatch.setitem(sys.modules, 'google.generativeai', fake)
    # Initialize router and inject gemini client
    router = get_multi_llm_router()
    router._gemini_client = fake

    # Call _call_gemini with preferred model that will fail first
    res = router._call_gemini(ProviderType.GEMINI_FLASH, 'hello', [], 'alpha')
    assert res['success']
    assert 'beta ok' in res['response']


def test_llm_router_fallback_order_respected(monkeypatch):
    monkeypatch.setenv('GEMINI_MODEL_CHAIN', 'm1,m2,m3')
    behavior = {
        'm1': ('error', 'rate limit', 429),
        'm2': ('error', 'temporarily unavailable', 503),
        'm3': ('success', 'm3 ok')
    }
    fake = FakeGenai(behavior)
    monkeypatch.setitem(sys.modules, 'google.generativeai', fake)
    router = get_multi_llm_router()
    router._gemini_client = fake

    res = router._call_gemini(ProviderType.GEMINI_FLASH, 'hello', [], 'm1')
    assert res['success']
    assert 'm3 ok' in res['response']
