from fastapi.testclient import TestClient
import os
import json
import types

import app

client = TestClient(app.app)


class DummyResponse:
    def __init__(self, text):
        self.text = text


def test_chat_normal(monkeypatch):
    # Ensure GEMINI_API_KEY present to pass early check
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    def fake_call(genai, message, **kwargs):
        return DummyResponse("Hello user")

    import gemini_fallback
    monkeypatch.setattr(gemini_fallback, 'call_gemini_with_fallback', fake_call)

    r = client.post("/chat", json={"message": "Say hi"})
    assert r.status_code == 200
    j = r.json()
    assert "response" in j
    assert j["response"] == "Hello user"
    assert j.get("automation") is None


def test_chat_automation_executes_tool(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    action_json = json.dumps({"tool": "get_time", "arguments": {}})

    def fake_call(genai, message, **kwargs):
        return DummyResponse(action_json)

    import gemini_fallback
    monkeypatch.setattr(gemini_fallback, 'call_gemini_with_fallback', fake_call)

    r = client.post("/chat", json={"message": "What time is it?"})
    assert r.status_code == 200
    j = r.json()
    assert j["response"] == action_json
    assert j.get("automation") is not None
    assert j["automation"]["success"] is True
    assert j["automation"]["tool"] == "get_time"


def test_chat_automation_unknown_tool(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    action_json = json.dumps({"tool": "no_such_tool", "arguments": {}})

    def fake_call(genai, message, **kwargs):
        return DummyResponse(action_json)

    import gemini_fallback
    monkeypatch.setattr(gemini_fallback, 'call_gemini_with_fallback', fake_call)

    r = client.post("/chat", json={"message": "Do a thing"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("automation") is not None
    assert j["automation"]["success"] is False
    assert j["automation"]["error"]["type"] == "ToolNotFound"


def test_chat_automation_tool_permission_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    action_json = json.dumps({"tool": "open_app", "arguments": {"app_name": "not_allowed_app"}})

    def fake_call(genai, message, **kwargs):
        return DummyResponse(action_json)

    import gemini_fallback
    monkeypatch.setattr(gemini_fallback, 'call_gemini_with_fallback', fake_call)

    r = client.post("/chat", json={"message": "Open the app"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("automation") is not None
    assert j["automation"]["success"] is False
    # PermissionError from executor is surfaced as error.type == 'PermissionError'
    assert j["automation"]["error"]["type"] in ("PermissionError", "PermissionError")
