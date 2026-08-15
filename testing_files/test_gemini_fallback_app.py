import os
import sys
import types
import json
import pytest
from fastapi.testclient import TestClient

# Import the app (loads app.py)
from app import app

client = TestClient(app)


class FakeGenaiModule(types.ModuleType):
    def __init__(self, behavior_map):
        super().__init__("google.generativeai")
        self._behavior = behavior_map
        self.configured_key = None

    def configure(self, api_key=None):
        self.configured_key = api_key

    class GenerativeModel:
        def __init__(self, model_id, system_instruction=None):
            self.model_id = model_id
            # behavior map will be attached at module level
        def generate_content(self, prompt):
            mod = sys.modules.get('google.generativeai')
            behavior = mod._behavior.get(self.model_id)
            if behavior is None:
                # default: success
                class R: pass
                r = R(); r.text = f"response from {self.model_id}"
                return r
            if behavior[0] == 'success':
                class R: pass
                r = R(); r.text = behavior[1]
                return r
            elif behavior[0] == 'error':
                # raise a generic exception mimicking SDK
                ex = Exception(behavior[1])
                # optionally attach status_code
                if len(behavior) > 2:
                    setattr(ex, 'status_code', behavior[2])
                raise ex
            else:
                raise Exception('unknown behavior')


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    # Ensure GEMINI_MODEL_CHAIN is unset unless test sets it
    monkeypatch.delenv('GEMINI_MODEL_CHAIN', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_MAX_RETRIES', raising=False)
    monkeypatch.delenv('GEMINI_BACKOFF_BASE', raising=False)
    yield


def setup_fake_genai(monkeypatch, behavior_map, api_key='test-key'):
    fake = FakeGenaiModule(behavior_map)
    monkeypatch.setitem(sys.modules, 'google.generativeai', fake)
    # also set GEMINI_API_KEY in env so app proceeds
    os.environ['GEMINI_API_KEY'] = api_key
    return fake


def test_primary_model_succeeds(monkeypatch):
    # Primary only (default), succeed
    behavior = {'gemini-3.5-flash': ('success', 'primary ok')}
    setup_fake_genai(monkeypatch, behavior)

    resp = client.post('/chat', json={'message': 'hello'})
    assert resp.status_code == 200
    assert resp.json()['response'] == 'primary ok'


def test_primary_429_then_fallback_success(monkeypatch):
    # Set GEMINI_MODEL_CHAIN to two models
    os.environ['GEMINI_MODEL_CHAIN'] = 'primary-model,fallback-model'
    behavior = {
        'primary-model': ('error', 'rate limit exceeded', 429),
        'fallback-model': ('success', 'fallback ok')
    }
    setup_fake_genai(monkeypatch, behavior)

    resp = client.post('/chat', json={'message': 'hello'})
    assert resp.status_code == 200
    assert resp.json()['response'] == 'fallback ok'


def test_quota_exceeded_fallback(monkeypatch):
    os.environ['GEMINI_MODEL_CHAIN'] = 'm1,m2'
    behavior = {
        'm1': ('error', 'quota exceeded'),
        'm2': ('success', 'm2 ok')
    }
    setup_fake_genai(monkeypatch, behavior)

    resp = client.post('/chat', json={'message': 'hello'})
    assert resp.status_code == 200
    assert resp.json()['response'] == 'm2 ok'


def test_temporary_5xx_fallback(monkeypatch):
    os.environ['GEMINI_MODEL_CHAIN'] = 'a,b'
    behavior = {
        'a': ('error', 'server error', 503),
        'b': ('success', 'b ok')
    }
    setup_fake_genai(monkeypatch, behavior)

    resp = client.post('/chat', json={'message': 'hello'})
    assert resp.status_code == 200
    assert resp.json()['response'] == 'b ok'


def test_invalid_api_key_no_endless_fallback(monkeypatch):
    os.environ['GEMINI_MODEL_CHAIN'] = 'x,y'
    behavior = {
        'x': ('error', 'invalid api key'),
        'y': ('success', 'y ok')
    }
    setup_fake_genai(monkeypatch, behavior)

    resp = client.post('/chat', json={'message': 'hello'})
    # Should surface as 401 or 400 (implementation returns 401 for status==401 else 400)
    assert resp.status_code in (400, 401)


def test_all_models_fail(monkeypatch):
    os.environ['GEMINI_MODEL_CHAIN'] = 'p,q'
    behavior = {
        'p': ('error', 'quota exceeded'),
        'q': ('error', 'temporarily unavailable')
    }
    setup_fake_genai(monkeypatch, behavior)

    resp = client.post('/chat', json={'message': 'hello'})
    assert resp.status_code == 503


def test_retry_count(monkeypatch):
    # Ensure GEMINI_MAX_RETRIES respected; primary fails then after retries fallback
    os.environ['GEMINI_MODEL_CHAIN'] = 'mprimary,mfallback'
    os.environ['GEMINI_MAX_RETRIES'] = '1'
    call_counts = {'mprimary': 0}

    class CountingFake(FakeGenaiModule):
        class GenerativeModel(FakeGenaiModule.GenerativeModel):
            def generate_content(self, prompt):
                mod = sys.modules.get('google.generativeai')
                behavior = mod._behavior.get(self.model_id)
                if self.model_id == 'mprimary':
                    call_counts['mprimary'] += 1
                if behavior[0] == 'error':
                    ex = Exception(behavior[1]); setattr(ex, 'status_code', behavior[2] if len(behavior)>2 else None); raise ex
                class R: pass
                r = R(); r.text = behavior[1]; return r

    fake = CountingFake({'mprimary': ('error', 'rate limit', 429), 'mfallback': ('success', 'ok')})
    monkeypatch.setitem(sys.modules, 'google.generativeai', fake)
    os.environ['GEMINI_API_KEY'] = 'k'

    resp = client.post('/chat', json={'message': 'hi'})
    assert resp.status_code == 200
    assert resp.json()['response'] == 'ok'
    # With 1 retry, generate_content should have been called 2 times for mprimary
    assert call_counts['mprimary'] == 2
