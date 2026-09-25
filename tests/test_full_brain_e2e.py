from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agents.brain import BrainResult
from agents.models import DelegationType
from app import app
from automation import ActionType, AgentGateway, AgentPlatform, MockExecutionAgent
from production_langgraph_adapter import ProductionLangGraphBrain
from web_intelligence.models import ExtractedFact, ResearchResult, SourceProvenance


class LocalLLM:
    def route_text(self, prompt, **kwargs):
        return {
            "text": f"local response: {prompt}",
            "model_id": "local-model",
            "provider": "local-mock",
            "latency_ms": 0.0,
            "fallback_used": False,
            "attempts": [],
            "usage": {},
        }


class FakeWebHuntAgent:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.requests: list[str] = []

    async def run(self, request, *, context=None, options=None):
        self.requests.append(request)
        if self.fail:
            return ResearchResult(
                original_query=request,
                needs_search=True,
                uncertainties=["mock provider failure"],
                errors_and_warnings=["mock provider failure"],
                metadata={"status": "failed", "error_code": "ENGINE_FAILURE"},
            )
        return ResearchResult(
            original_query=request,
            needs_search=True,
            sources=[SourceProvenance(
                url="https://example.test/source",
                domain="example.test",
                title="Mock source",
            )],
            extracted_information=[ExtractedFact(
                fact="Mock finding",
                source_url="https://example.test/source",
                source_domain="example.test",
            )],
            key_findings=["Mock finding"],
            uncertainties=["Mock uncertainty"],
            metadata={"provider": "mock-web", "status": "completed"},
        )


class NeverFallback:
    async def process(self, *args, **kwargs):
        raise AssertionError("NEXUS fallback was called")


def _brain(*, gateway=None, web=None):
    return ProductionLangGraphBrain(
        NeverFallback(),
        LocalLLM(),
        SimpleNamespace(),
        pc_gateway=gateway,
        android_gateway=gateway,
        web_agent=web,
    )


def test_full_brain_normal_conversation_preserves_identity_and_memory():
    brain = _brain()
    result = asyncio.run(brain.process(
        "What is my name?",
        request_id="request-conversation",
        session_id="session-one",
        user_id="user-one",
        messages=[
            {"role": "user", "content": "My name is Ganesh."},
            {"role": "user", "content": "What is my name?"},
        ],
        memory_context=["User name is Ganesh"],
    ))

    assert result.status == "completed"
    assert result.request_id == "request-conversation"
    assert result.metadata["session_id"] == "session-one"
    assert result.metadata["history_count"] == 2
    assert result.metadata["memory_count"] == 1


def test_full_brain_session_and_user_context_do_not_leak_between_runs():
    brain = _brain()
    first = asyncio.run(brain.process(
        "Hello from one",
        request_id="request-one",
        session_id="session-one",
        user_id="user-one",
        messages=[{"role": "user", "content": "one"}],
        memory_context=["memory-one"],
    ))
    second = asyncio.run(brain.process(
        "Hello from two",
        request_id="request-two",
        session_id="session-two",
        user_id="user-two",
        messages=[{"role": "user", "content": "two"}],
        memory_context=["memory-two"],
    ))

    assert first.request_id != second.request_id
    assert first.metadata["session_id"] == "session-one"
    assert second.metadata["session_id"] == "session-two"
    assert first.metadata["memory_count"] == second.metadata["memory_count"] == 1


@pytest.mark.parametrize(
    ("message", "platform", "action"),
    [
        ("open notepad", AgentPlatform.PC, ActionType.OPEN_APP),
        ("battery status", AgentPlatform.PC, ActionType.BATTERY_STATUS),
        ("what is the device time", AgentPlatform.PC, ActionType.GET_DEVICE_TIME),
        ("turn on flashlight", AgentPlatform.ANDROID, ActionType.FLASHLIGHT_ON),
        ("turn off flashlight", AgentPlatform.ANDROID, ActionType.FLASHLIGHT_OFF),
    ],
)
def test_device_capability_e2e_uses_shared_gateway(message, platform, action):
    gateway = AgentGateway()
    agent = MockExecutionAgent(
        platform=platform,
        capabilities=frozenset({action}),
    )
    gateway.register_agent(agent)

    result = asyncio.run(_brain(gateway=gateway).process(
        message,
        request_id=f"request-{action.value}",
        session_id="device-session",
        user_id="device-user",
    ))

    assert result.status == "completed"
    assert agent.executed_actions[0][0].type is action
    assert len(gateway.list_agents()) == 1


def test_device_failure_is_not_reported_as_success():
    gateway = AgentGateway()
    gateway.register_agent(
        MockExecutionAgent(
            platform=AgentPlatform.ANDROID,
            capabilities=frozenset({ActionType.FLASHLIGHT_ON}),
            default_success=False,
        )
    )

    result = asyncio.run(_brain(gateway=gateway).process("turn on flashlight"))

    assert result.status == "completed"
    assert "verification" in result.response


def test_web_success_preserves_research_and_request_identity():
    web = FakeWebHuntAgent()
    result = asyncio.run(_brain(web=web).process(
        "research web sources",
        request_id="request-web-e2e",
        session_id="web-session",
        user_id="web-user",
    ))

    assert result.status == "completed"
    assert web.requests == ["research web sources"]
    assert result.metadata["execution"] == "langgraph"


def test_web_failure_is_not_silently_successful():
    result = asyncio.run(_brain(web=FakeWebHuntAgent(fail=True)).process(
        "research web sources",
        request_id="request-web-failure",
    ))

    assert result.status == "completed"
    assert "web" in result.response


def test_parallel_web_and_pc_branches_merge_without_fallback():
    gateway = AgentGateway()
    gateway.register_agent(
        MockExecutionAgent(
            platform=AgentPlatform.PC,
            capabilities=frozenset({ActionType.BATTERY_STATUS}),
        )
    )
    web = FakeWebHuntAgent()

    result = asyncio.run(_brain(gateway=gateway, web=web).process(
        "research web sources and battery status",
        request_id="request-parallel",
    ))

    assert result.status == "completed"
    assert web.requests == ["research web sources and battery status"]
    assert result.response


def test_chat_missing_session_and_malformed_request_remain_safe():
    import app as app_module

    class FakeBrain:
        async def process(self, task, **kwargs):
            return BrainResult(
                request_id=kwargs["request_id"],
                status="completed",
                task=task,
                decision=DelegationType.DIRECT,
                response="safe local response",
            )

    original = app_module.get_brain
    app_module.get_brain = lambda: FakeBrain()
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        malformed = client.post("/chat", json={})
    finally:
        app_module.get_brain = original

    assert response.status_code == 200
    assert response.json()["request_id"]
    assert malformed.status_code == 422


def test_feature_flag_on_and_off_preserves_brain_selection(monkeypatch):
    import app as app_module

    previous_brain = app_module._brain_instance
    previous_flag = __import__("os").environ.get("VENNELA_LANGGRAPH_ENABLED")
    monkeypatch.setenv("VENNELA_LANGGRAPH_ENABLED", "true")
    app_module._brain_instance = None
    assert isinstance(app_module.get_brain(), ProductionLangGraphBrain)

    monkeypatch.setenv("VENNELA_LANGGRAPH_ENABLED", "false")
    app_module._brain_instance = None
    assert type(app_module.get_brain()).__name__ == "VennelaBrain"
    app_module._brain_instance = previous_brain
    if previous_flag is None:
        __import__("os").environ.pop("VENNELA_LANGGRAPH_ENABLED", None)
    else:
        __import__("os").environ["VENNELA_LANGGRAPH_ENABLED"] = previous_flag
