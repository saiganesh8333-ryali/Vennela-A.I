"""Phase 2 (P0-03): Streaming Authorization, Error Sanitization & Disconnect Safety tests."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ.setdefault("VENNELA_BOSS_ID", "boss_stream_test")
os.environ.setdefault("VENNELA_AGENT_TOKEN", "token-stream-test-secret-12345")
os.environ.setdefault("LIGHTWEIGHT_MODE", "true")
os.environ.setdefault("LLM_ROUTER_MOCK", "true")

import app as app_module
from llm_router.adapter import VennelaLLMAdapter
from llm_router.contracts import Failure, FailureKind, RoutingError
from llm_router.gateway import Gateway
from llm_router.providers.mock import MockProvider
from llm_router.providers.openrouter import OpenRouterProvider
from llm_router.registry import ModelProfile, ModelRegistry, ModelTier


def _auth_headers() -> dict[str, str]:
    token = os.environ["VENNELA_AGENT_TOKEN"]
    return {"Authorization": f"Bearer {token}"}


class SpyMemorySubsystem:
    """In-memory spy verifying exact retrieve and store invocations."""

    def __init__(self) -> None:
        self.mode = SimpleNamespace(value="MARK_I_TEMPORARY")
        self.retrieve_calls: list[Any] = []
        self.store_calls: list[dict[str, Any]] = []

    def retrieve(self, request):
        self.retrieve_calls.append(request)
        return SimpleNamespace(
            context_strings=[],
            memory_count=0,
            mode=self.mode,
            duration_ms=0.0,
            metadata={"stable_count": 0, "relevant_count": 0},
        )

    def store(self, text: str, *, user_id: str, session_id=None, metadata=None) -> bool:
        self.store_calls.append(
            {
                "text": text,
                "user_id": user_id,
                "session_id": session_id,
                "metadata": dict(metadata or {}),
            }
        )
        return True


def _mock_adapter(chunks=("Hello ", "Boss", "!")) -> VennelaLLMAdapter:
    provider = MockProvider("openrouter", "Mock response", stream_chunks=list(chunks))
    gateway = Gateway.create(custom_providers={"openrouter": provider, "groq": provider})
    return VennelaLLMAdapter(router=gateway.router)


def test_01_authorization_parity_between_chat_and_chat_stream():
    """Cross-owner requests return HTTP 403 on both /chat and /chat/stream; missing auth returns 401."""
    client = TestClient(app_module.app)
    headers = _auth_headers()

    with patch.object(app_module, "_llm_adapter_instance", _mock_adapter()):
        chat_unauth = client.post("/chat", json={"message": "Hello"})
        stream_unauth = client.post("/chat/stream", json={"message": "Hello"})
        assert chat_unauth.status_code == 401
        assert stream_unauth.status_code == 401

        cross_owner_payload = {
            "message": "Read private data",
            "user_id": "other_victim_user_999",
            "session_id": "sess-bola",
        }
        chat_bola = client.post("/chat", json=cross_owner_payload, headers=headers)
        stream_bola = client.post("/chat/stream", json=cross_owner_payload, headers=headers)

    assert chat_bola.status_code == 403
    assert stream_bola.status_code == 403
    assert chat_bola.json()["detail"] == stream_bola.json()["detail"]


def test_02_internal_error_sanitization_setup_and_midstream():
    """Internal exceptions return sanitized HTTP 500 or sanitized message with zero secret leakage."""
    secret_marker = "SECRET_DB_MARKER_PG_998877_DO_NOT_LEAK"
    client = TestClient(app_module.app, raise_server_exceptions=False)
    headers = _auth_headers()

    def failing_memory():
        raise RuntimeError(
            f"psycopg connection failed postgresql://admin:{secret_marker}@db.internal/prod"
        )

    with patch.object(app_module, "get_memory_subsystem", side_effect=failing_memory):
        resp = client.post(
            "/chat/stream",
            json={"message": "Explain status", "session_id": "sess-sec"},
            headers=headers,
        )

    assert resp.status_code == 500
    body = resp.text
    assert secret_marker not in body
    assert "psycopg" not in body
    assert "Traceback" not in body
    assert "File " not in body
    assert resp.json() == {"detail": "Internal AI error"}

    # Mid-stream exception containing secret marker must also be sanitized
    class SecretCrashingAdapter:
        def stream_text(self, *args, **kwargs):
            yield "partial chunk "
            raise RuntimeError(f"upstream explosion token={secret_marker}")

    spy_mem = SpyMemorySubsystem()
    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_mem),
        patch.object(app_module, "get_llm_adapter", return_value=SecretCrashingAdapter()),
    ):
        resp_mid = client.post(
            "/chat/stream",
            json={"message": "Tell me something", "session_id": "sess-sec-mid"},
            headers=headers,
        )

    assert resp_mid.status_code == 200
    assert secret_marker not in resp_mid.text
    assert "Traceback" not in resp_mid.text
    assert "[AI service temporarily unavailable]" in resp_mid.text
    assert spy_mem.store_calls == []


@pytest.mark.asyncio
async def test_03_disconnect_stops_generation_closes_upstream_and_blocks_persistence():
    """Client disconnection stops upstream pulls, closes iterator, cleans resources, and prevents store()."""
    pulled_indices: list[int] = []
    upstream_closed = threading.Event()
    disconnect_after_second = False

    class DisconnectCountingAdapter:
        def stream_text(self, *args, **kwargs):
            def _gen():
                try:
                    for idx in range(20):
                        pulled_indices.append(idx)
                        if idx >= 2:
                            time.sleep(0.15)
                        yield f"chunk-{idx} "
                finally:
                    upstream_closed.set()

            return _gen()

    class SimulatedDisconnectRequest:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            self.state = SimpleNamespace(request_id="00000000-0000-4000-8000-000000000701")

        async def is_disconnected(self) -> bool:
            return disconnect_after_second

    spy_mem = SpyMemorySubsystem()
    req_model = app_module.ChatRequest(message="Long response", session_id="sess-disc")
    fake_http = SimulatedDisconnectRequest()
    user = app_module.AuthenticatedUser(user_id=os.environ["VENNELA_BOSS_ID"])

    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_mem),
        patch.object(app_module, "get_llm_adapter", return_value=DisconnectCountingAdapter()),
    ):
        response = await app_module.chat_stream(req_model, fake_http, user)
        received: list[str] = []
        async for chunk in response.body_iterator:
            received.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))
            if len(received) == 2:
                disconnect_after_second = True

    # Wait briefly if a single in-flight next() was concluding before .close() fired
    closed = await asyncio.to_thread(upstream_closed.wait, 2.0)
    assert closed, "Upstream iterator was never closed after disconnect"
    assert received == ["chunk-0 ", "chunk-1 "]
    assert len(pulled_indices) <= 3, f"Upstream continued pulling too many chunks: {pulled_indices}"
    assert spy_mem.store_calls == []


@pytest.mark.asyncio
async def test_03b_real_uvicorn_client_disconnect_prevents_persistence():
    """Real socket close against single-worker Uvicorn cancels stream and skips memory store()."""
    first_chunk_sent = threading.Event()
    upstream_closed = threading.Event()
    pulled: list[int] = []

    class SlowChunkAdapter:
        def stream_text(self, *args, **kwargs):
            def _gen():
                try:
                    for idx in range(30):
                        pulled.append(idx)
                        if idx == 0:
                            first_chunk_sent.set()
                        else:
                            time.sleep(0.1)
                        yield f"tok-{idx} "
                finally:
                    upstream_closed.set()

            return _gen()

    spy_mem = SpyMemorySubsystem()

    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_mem),
        patch.object(app_module, "get_llm_adapter", return_value=SlowChunkAdapter()),
    ):
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = int(s.getsockname()[1])

        config = uvicorn.Config(
            app_module.app,
            host="127.0.0.1",
            port=port,
            workers=1,
            log_level="error",
            access_log=False,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.perf_counter() + 10.0
        while not server.started:
            if time.perf_counter() > deadline:
                server.should_exit = True
                raise RuntimeError("Uvicorn failed to start")
            time.sleep(0.02)

        try:
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10.0) as client:
                async with client.stream(
                    "POST",
                    "/chat/stream",
                    headers=_auth_headers(),
                    json={"message": "Stream slowly", "session_id": "sess-real-disc"},
                ) as resp:
                    assert resp.status_code == 200
                    it = resp.aiter_text()
                    first = await anext(it)
                    assert "tok-0" in first
                    # Closing context aborts TCP connection immediately
            closed = await asyncio.to_thread(upstream_closed.wait, 3.0)
            assert closed, "Upstream iterator did not close on client socket close"
        finally:
            server.should_exit = True
            thread.join(timeout=10.0)

    assert len(pulled) < 30
    assert spy_mem.store_calls == []


def test_04_partial_generation_failure_never_persists_memory():
    """An exception after yielding multiple chunks must never persist partial conversation turns."""
    upstream_closed = threading.Event()

    class PartialFailureAdapter:
        def stream_text(self, *args, **kwargs):
            def _gen():
                try:
                    yield "chunk one "
                    yield "chunk two "
                    raise RoutingError(
                        Failure(
                            FailureKind.SERVER,
                            "Simulated mid-stream 500 INTERNAL_TOKEN_XYZ",
                            retryable=True,
                            provider="openrouter",
                        )
                    )
                finally:
                    upstream_closed.set()

            return _gen()

    spy_mem = SpyMemorySubsystem()
    client = TestClient(app_module.app)

    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_mem),
        patch.object(app_module, "get_llm_adapter", return_value=PartialFailureAdapter()),
    ):
        resp = client.post(
            "/chat/stream",
            json={"message": "Remember my favorite color is cobalt", "session_id": "sess-partial"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    assert "chunk one " in resp.text
    assert "chunk two " in resp.text
    assert "[AI service temporarily unavailable]" in resp.text
    assert "INTERNAL_TOKEN_XYZ" not in resp.text
    assert upstream_closed.is_set()
    assert spy_mem.store_calls == []


def test_05_clean_eof_persists_memory_exactly_once():
    """Successful stream completion persists conversation turn once with owner and session."""
    spy_mem = SpyMemorySubsystem()
    adapter = _mock_adapter(chunks=["Answer ", "complete."])
    client = TestClient(app_module.app)

    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_mem),
        patch.object(app_module, "get_llm_adapter", return_value=adapter),
    ):
        resp = client.post(
            "/chat/stream",
            json={"message": "My favorite language is Python", "session_id": "sess-clean"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    assert resp.text == "Answer complete."
    assert len(spy_mem.store_calls) == 1
    stored = spy_mem.store_calls[0]
    assert stored["text"] == "My favorite language is Python"
    assert stored["user_id"] == os.environ["VENNELA_BOSS_ID"]
    assert stored["session_id"] == "sess-clean"
    assert stored["metadata"]["store_session"] is True

    # Whitespace-only response must not persist an empty turn
    spy_empty = SpyMemorySubsystem()
    empty_adapter = _mock_adapter(chunks=["   ", "\n"])
    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_empty),
        patch.object(app_module, "get_llm_adapter", return_value=empty_adapter),
    ):
        resp_empty = client.post(
            "/chat/stream",
            json={"message": "Hello there", "session_id": "sess-empty"},
            headers=_auth_headers(),
        )
    assert resp_empty.status_code == 200
    assert spy_empty.store_calls == []


@pytest.mark.asyncio
async def test_06_asyncio_cancelled_error_propagates_and_cleans_up():
    """asyncio.CancelledError is never swallowed at setup or during streaming, and skips persistence."""
    spy_mem = SpyMemorySubsystem()
    upstream_closed = threading.Event()
    first_chunk_pulled = threading.Event()
    user = app_module.AuthenticatedUser(user_id=os.environ["VENNELA_BOSS_ID"])

    # Case A: Cancellation during endpoint setup
    class CancelledSetupMemory:
        def retrieve(self, request):
            raise asyncio.CancelledError()

    with patch.object(app_module, "get_memory_subsystem", return_value=CancelledSetupMemory()):
        req = app_module.ChatRequest(message="Cancel setup", session_id="sess-cancel-setup")
        fake_http = SimpleNamespace(
            headers={},
            state=SimpleNamespace(request_id="00000000-0000-4000-8000-000000000702"),
            is_disconnected=lambda: asyncio.sleep(0, result=False),
        )
        with pytest.raises(asyncio.CancelledError):
            await app_module.chat_stream(req, fake_http, user)

    # Case B: Cancellation mid-stream while pulling next chunk
    class BlockingSecondChunkAdapter:
        def stream_text(self, *args, **kwargs):
            def _gen():
                try:
                    yield "first "
                    first_chunk_pulled.set()
                    time.sleep(0.4)
                    yield "second "
                finally:
                    upstream_closed.set()

            return _gen()

    async def fake_is_disconnected():
        return False

    fake_http = SimpleNamespace(
        headers={},
        state=SimpleNamespace(request_id="00000000-0000-4000-8000-000000000703"),
        is_disconnected=fake_is_disconnected,
    )

    with (
        patch.object(app_module, "get_memory_subsystem", return_value=spy_mem),
        patch.object(app_module, "get_llm_adapter", return_value=BlockingSecondChunkAdapter()),
    ):
        response = await app_module.chat_stream(
            app_module.ChatRequest(message="Cancel midstream", session_id="sess-cancel-mid"),
            fake_http,
            user,
        )
        gen = response.body_iterator
        first_chunk = await anext(gen)
        assert first_chunk == "first "

        # Next pull is blocked inside thread; cancel the task awaiting anext(gen)
        next_task = asyncio.create_task(anext(gen))
        await asyncio.sleep(0.08)
        next_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await next_task

    closed = await asyncio.to_thread(upstream_closed.wait, 2.0)
    assert closed, "Upstream iterator not closed after CancelledError"
    assert spy_mem.store_calls == []


def test_07_router_provider_stream_close_cascades_to_sse_layer():
    """Closing VennelaLLMAdapter.stream_text closes FallbackEngine and provider _stream_sse cleanly."""
    sse_closed = threading.Event()

    class InspectableOpenRouterProvider(OpenRouterProvider):
        def _stream_sse(self, url, payload, headers, model_id):
            try:
                yield '{"choices":[{"delta":{"content":"one "}}]}'
                yield '{"choices":[{"delta":{"content":"two "}}]}'
                yield '{"choices":[{"delta":{"content":"three"}}]}'
            finally:
                sse_closed.set()

    provider = InspectableOpenRouterProvider(api_key="test-key")
    registry = ModelRegistry(
        [
            ModelProfile(
                "test-or-model",
                "openrouter",
                tier=ModelTier.GENERAL,
                quality_score=1.0,
                conversation_strength=1.0,
                latency_ms=50,
            )
        ]
    )
    gateway = Gateway.create(custom_providers={"openrouter": provider}, registry=registry)
    adapter = VennelaLLMAdapter(router=gateway.router)

    stream_iter = adapter.stream_text("Hello cascade")
    first = next(stream_iter)
    assert first == "one "
    assert not sse_closed.is_set()
    stream_iter.close()
    assert sse_closed.is_set()
