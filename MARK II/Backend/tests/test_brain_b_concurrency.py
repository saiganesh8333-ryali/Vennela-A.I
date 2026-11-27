"""Phase 1 (P0-04): Brain B Concurrency Isolation & Event-Loop Protection tests."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import os
import socket
import sys
import threading
import time
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import uvicorn

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ.setdefault("VENNELA_BOSS_ID", "boss_concurrency_test")
os.environ.setdefault("VENNELA_AGENT_TOKEN", "token-concurrency-test-secret-12345")
os.environ.setdefault("LIGHTWEIGHT_MODE", "true")
os.environ.setdefault("LLM_ROUTER_MOCK", "true")

import app as app_module
from automation import ActionType, AgentGateway, AgentPlatform, MockExecutionAgent
from core.intelligence_contracts import DelegationType
from conversation.response_policy import ConversationAdjuster
from production_langgraph_adapter import ProductionLangGraphBrain
from web_intelligence.models import ExtractedFact, ResearchResult, SourceProvenance


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _running_single_worker_uvicorn(fast_app):
    """Run app in a real single-worker uvicorn.Server on an ephemeral localhost port."""
    port = _free_tcp_port()
    config = uvicorn.Config(
        fast_app,
        host="127.0.0.1",
        port=port,
        workers=1,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="uvicorn-test-server", daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.perf_counter() + 10.0
    while not server.started:
        if time.perf_counter() > deadline:
            server.should_exit = True
            raise RuntimeError("Uvicorn test server failed to start within 10s")
        time.sleep(0.02)

    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10.0)


@pytest.mark.asyncio
async def test_01_event_loop_responsiveness_under_concurrent_5s_brain_b_load():
    """GET /health stays < 100ms on single-worker Uvicorn during concurrent 5s Brain B calls."""

    class SlowBlockingLLMAdapter:
        def __init__(self) -> None:
            self.delay_seconds = 0.0

        def route_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
            if self.delay_seconds > 0:
                # Simulate a 5-second synchronous blocking LLM network call
                time.sleep(self.delay_seconds)
            sys_inst = kwargs.get("system_instruction", "")
            return {
                "text": f"reply:{prompt}|has_sys={bool(sys_inst)}",
                "model_id": "slow-mock-model",
                "provider": "slow-mock",
                "latency_ms": self.delay_seconds * 1000.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    llm_adapter = SlowBlockingLLMAdapter()
    brain = ProductionLangGraphBrain(
        llm_adapter,
        ConversationAdjuster(),
    )
    token = os.environ["VENNELA_AGENT_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch.object(app_module, "_brain_instance", brain),
        patch.object(app_module, "get_brain", return_value=brain),
    ):
        with _running_single_worker_uvicorn(app_module.app) as base_url:
            async with (
                httpx.AsyncClient(base_url=base_url, timeout=15.0) as chat_client,
                httpx.AsyncClient(base_url=base_url, timeout=5.0) as health_client,
            ):
                # Warm up one fast request + keep-alive connections so one-time module imports
                # do not distort the steady-state 5-second concurrency measurement.
                warmup_health = await health_client.get("/health")
                assert warmup_health.status_code == 200
                warmup_chat = await chat_client.post(
                    "/chat",
                    headers=headers,
                    json={"message": "Warmup request", "session_id": "warmup-session"},
                )
                assert warmup_chat.status_code == 200

                llm_adapter.delay_seconds = 5.0

                async def invoke_slow_chat(idx: int) -> httpx.Response:
                    return await chat_client.post(
                        "/chat",
                        headers=headers,
                        json={
                            "message": f"Explain isolation scenario {idx}",
                            "session_id": f"load-session-{idx}",
                            "request_id": f"00000000-0000-4000-8000-00000000010{idx}",
                        },
                    )

                workload_started = time.perf_counter()
                chat_tasks = [asyncio.create_task(invoke_slow_chat(i)) for i in range(5)]

                # Give chat tasks a moment to enter the 5-second Brain B execution
                await asyncio.sleep(0.2)

                health_latencies_ms: list[float] = []
                while not all(task.done() for task in chat_tasks):
                    t0 = time.perf_counter()
                    health_resp = await health_client.get("/health")
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    assert health_resp.status_code == 200
                    assert health_resp.json()["status"] == "healthy"
                    health_latencies_ms.append(elapsed_ms)
                    await asyncio.sleep(0.15)

                chat_responses = await asyncio.gather(*chat_tasks)
                total_wall_s = time.perf_counter() - workload_started

    # 5 concurrent 5s requests must execute concurrently (~5s), not sequentially (25s)
    print(
        f"\n[P0-04 LOAD] 5x5s concurrent Brain B requests completed in {total_wall_s:.3f}s | "
        f"health checks={len(health_latencies_ms)} | "
        f"min={min(health_latencies_ms):.2f}ms "
        f"mean={sum(health_latencies_ms)/len(health_latencies_ms):.2f}ms "
        f"max={max(health_latencies_ms):.2f}ms"
    )
    assert 4.8 <= total_wall_s < 10.0, (
        f"Expected ~5s concurrent execution, got {total_wall_s:.2f}s"
    )
    assert len(health_latencies_ms) >= 15
    max_health_ms = max(health_latencies_ms)
    assert max_health_ms < 100.0, (
        f"Event loop blocked: max /health latency was {max_health_ms:.2f}ms "
        f"(all={health_latencies_ms})"
    )

    for idx, resp in enumerate(chat_responses):
        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == f"00000000-0000-4000-8000-00000000010{idx}"
        assert f"reply:Explain isolation scenario {idx}" in body["response"]


@pytest.mark.asyncio
async def test_02_concurrent_request_isolation_across_contexts_and_agents():
    """Concurrent requests never mix user_id, request_id, history, memory, or web state."""

    class CapturingOverlapLLM:
        def route_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
            # Stagger sleep so concurrent requests overlap inside graph execution
            idx = int(prompt.rsplit("-", 1)[-1])
            time.sleep(0.05 + (idx % 3) * 0.03)
            sys_inst = kwargs.get("system_instruction") or ""
            msgs = kwargs.get("messages") or []
            timing_cb = kwargs.get("timing_callback")
            if timing_cb is not None:
                timing_cb({"provider": "iso-mock", "model": f"model-{idx}", "success": True})
            msg_contents = "|".join(m["content"] for m in msgs)
            return {
                "text": (
                    f"TASK={prompt}||SYS={sys_inst}||MSGS={msg_contents}"
                ),
                "model_id": f"model-{idx}",
                "provider": "iso-mock",
                "latency_ms": 50.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class IsolatedFakeWebAgent:
        async def run(self, request: str, *, context: dict[str, Any] | None = None):
            await asyncio.sleep(0.04)
            req_id = (context or {}).get("request_id", "missing")
            return ResearchResult(
                original_query=request,
                needs_search=True,
                sources=[
                    SourceProvenance(
                        url=f"https://example.test/{req_id}",
                        domain="example.test",
                        title=f"Source-{req_id}",
                    )
                ],
                extracted_information=[
                    ExtractedFact(
                        fact=f"web-fact-for-{req_id}",
                        source_url=f"https://example.test/{req_id}",
                        source_domain="example.test",
                    )
                ],
                key_findings=[f"web-fact-for-{req_id}"],
                metadata={"status": "completed", "provider": "fake-web"},
            )

    gateway = AgentGateway()
    gateway.register_agent(
        MockExecutionAgent(
            platform=AgentPlatform.PC,
            capabilities=frozenset({ActionType.BATTERY_STATUS}),
        )
    )

    brain = ProductionLangGraphBrain(
        CapturingOverlapLLM(),
        ConversationAdjuster(),
        pc_gateway=gateway,
        web_agent=IsolatedFakeWebAgent(),
    )

    timings = [{"llm_events": []} for _ in range(12)]

    async def run_one(idx: int):
        # Mix ordinary, memory-node-triggering, and web-research prompts concurrently
        if idx % 3 == 0:
            task = f"Remember secret-memory-{idx} for user-{idx}"
        elif idx % 3 == 1:
            task = f"Search web news for topic-{idx}"
        else:
            task = f"Explain concept-{idx}"

        return await brain.process(
            task,
            request_id=f"[req-{idx}]",
            user_id=f"user-{idx}",
            session_id=f"sess-{idx}",
            messages=[{"role": "user", "content": f"[history-msg-{idx}]"}],
            memory_context=[f"[mem-token-{idx}]"],
            context={"_system_instruction": f"[sys-token-{idx}]"},
            timing=timings[idx],
        )

    results = await asyncio.gather(*(run_one(i) for i in range(12)))

    for idx, res in enumerate(results):
        assert res.status == "completed"
        assert res.request_id == f"[req-{idx}]"
        assert res.metadata["session_id"] == f"sess-{idx}"
        assert res.metadata["memory_count"] == 1
        assert f"[sys-token-{idx}]" in res.response
        assert f"[mem-token-{idx}]" in res.response
        assert f"[history-msg-{idx}]" in res.response
        if idx % 3 == 1:
            assert f"web-fact-for-[req-{idx}]" in res.response

        # Ensure zero leaks from any other request index
        for other in range(12):
            if other == idx:
                continue
            assert f"[sys-token-{other}]" not in res.response
            assert f"[mem-token-{other}]" not in res.response
            assert f"[history-msg-{other}]" not in res.response
            assert f"web-fact-for-[req-{other}]" not in res.response

        # Timing events must stay isolated to this request's dict
        assert len(timings[idx]["llm_events"]) == 1
        assert timings[idx]["llm_events"][0]["model"] == f"model-{idx}"


@pytest.mark.asyncio
async def test_03_shared_graph_integrity_no_mutation_across_concurrent_requests():
    """Concurrent requests reuse compiled graph without mutating shared nodes or adapters."""

    class EchoLLM:
        def route_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
            time.sleep(0.05)
            return {
                "text": f"echo:{prompt}",
                "model_id": "echo-model",
                "provider": "echo",
                "latency_ms": 1.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    brain = ProductionLangGraphBrain(EchoLLM(), ConversationAdjuster())

    # Race graph construction itself across concurrent tasks first
    async def run_req(idx: int):
        return await brain.process(
            f"prompt-{idx}",
            request_id=f"graph-req-{idx}",
            session_id=f"graph-sess-{idx}",
            user_id=f"graph-user-{idx}",
            memory_context=[f"graph-mem-{idx}"],
            messages=[{"role": "user", "content": f"graph-msg-{idx}"}],
            context={"_system_instruction": f"graph-sys-{idx}"},
            timing={"llm_events": []},
        )

    first_batch = await asyncio.gather(*(run_req(i) for i in range(6)))
    assert all(r.status == "completed" for r in first_batch)

    graph = brain._get_graph([], None, [])
    graph_id = id(graph)
    compiled_id = id(graph.compiled_graph)
    memory_agent = graph.nodes["memory"].agent
    reasoning_adapter = graph.nodes["reasoning"].reasoning_adapter
    memory_agent_id = id(memory_agent)
    reasoning_adapter_id = id(reasoning_adapter)

    second_batch = await asyncio.gather(*(run_req(i) for i in range(6, 16)))
    assert all(r.status == "completed" for r in second_batch)

    assert id(brain._get_graph([], None, [])) == graph_id
    assert id(graph.compiled_graph) == compiled_id
    assert id(graph.nodes["memory"].agent) == memory_agent_id
    assert id(graph.nodes["reasoning"].reasoning_adapter) == reasoning_adapter_id

    # Shared adapters must remain unmutated
    assert memory_agent.context == []
    assert reasoning_adapter.system_instruction is None
    assert reasoning_adapter.messages == []
    assert reasoning_adapter.timing is None
    assert graph.telemetry.events == []


@pytest.mark.asyncio
async def test_04_existing_reasoning_regression_contract_preserved():
    """Verify Brain B produces the expected BrainResult contract and handles failures."""

    class ContractLLM:
        def route_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
            return {
                "text": "Structured Brain B answer",
                "model_id": "contract-model",
                "provider": "contract-provider",
                "latency_ms": 1.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    brain = ProductionLangGraphBrain(ContractLLM(), ConversationAdjuster())
    result = await brain.process(
        "Explain concurrency safety",
        request_id="req-contract-1",
        session_id="sess-contract-1",
        user_id="user-contract-1",
        memory_context=["User is a backend engineer"],
        messages=[{"role": "user", "content": "Explain concurrency safety"}],
        context={"_system_instruction": "Be concise"},
    )

    assert result.request_id == "req-contract-1"
    assert result.status == "completed"
    assert result.decision == DelegationType.DIRECT
    assert result.response == "Structured Brain B answer"
    assert result.metadata["execution"] == "langgraph"
    assert result.metadata["backend"] == "langgraph-production"
    assert result.metadata["session_id"] == "sess-contract-1"
    assert result.metadata["memory_count"] == 1
    assert result.metadata["history_count"] == 1
    assert "graph_execution" in result.metadata["timings_ms"]

    # Unsupported capability still fails structurally without Brain A fallback
    unsupported = await brain.process("open notepad", request_id="req-unsupported")
    assert unsupported.status == "failed"
    assert unsupported.error["code"] == "UNSUPPORTED_REQUEST"


@pytest.mark.asyncio
async def test_05_synchronous_graph_execution_runs_off_event_loop_thread():
    """Verify graph execution and nested web agent run outside the asyncio event loop thread."""
    event_loop_thread_id = threading.get_ident()
    observed_llm_threads: list[int] = []
    observed_web_threads: list[int] = []

    class ThreadRecordingLLM:
        def route_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
            observed_llm_threads.append(threading.get_ident())
            return {
                "text": "thread-checked response",
                "model_id": "thread-model",
                "provider": "thread-mock",
                "latency_ms": 1.0,
                "fallback_used": False,
                "attempts": [],
                "usage": {},
            }

    class ThreadRecordingWebAgent:
        async def run(self, request: str, *, context: dict[str, Any] | None = None):
            observed_web_threads.append(threading.get_ident())
            await asyncio.sleep(0.02)
            return ResearchResult(
                original_query=request,
                needs_search=True,
                sources=[
                    SourceProvenance(
                        url="https://example.test/thread",
                        domain="example.test",
                        title="Thread Test",
                    )
                ],
                extracted_information=[
                    ExtractedFact(
                        fact="Executed off event loop",
                        source_url="https://example.test/thread",
                        source_domain="example.test",
                    )
                ],
                key_findings=["Executed off event loop"],
                metadata={"status": "completed", "provider": "thread-web"},
            )

    brain = ProductionLangGraphBrain(
        ThreadRecordingLLM(),
        ConversationAdjuster(),
        web_agent=ThreadRecordingWebAgent(),
    )

    results = await asyncio.gather(
        brain.process("Search the web for Python concurrency", request_id="req-thread-1"),
        brain.process("Search the web for asyncio to_thread", request_id="req-thread-2"),
    )

    assert all(r.status == "completed" for r in results)
    assert len(observed_llm_threads) == 2
    assert len(observed_web_threads) == 2
    assert all(tid != event_loop_thread_id for tid in observed_llm_threads)
    assert all(tid != event_loop_thread_id for tid in observed_web_threads)
