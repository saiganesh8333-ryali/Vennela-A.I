import json

import httpx
import pytest

from telegram_interface.adapter import (
    VennelaAdapter,
    VennelaAdapterError,
    build_chat_payload,
    session_id_for_chat,
)
from telegram_interface.config import TelegramConfig


def enabled_config():
    return TelegramConfig(
        bot_token="token",
        allowed_chat_ids=frozenset({42}),
        vennela_api_base_url="https://vennela.example",
        vennela_chat_enabled=True,
    )


def test_session_mapping_and_payload():
    assert session_id_for_chat(42) == "telegram:42"
    assert build_chat_payload("hello", 42) == {
        "message": "hello",
        "user_id": "telegram:42",
        "session_id": "telegram:42",
    }


@pytest.mark.asyncio
async def test_adapter_handles_response():
    seen = {}
    request_id = "telegram-request-test"

    async def handler(request):
        seen.update(json.loads(request.content))
        seen["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200, json={"response": "Hello from Vennela"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await VennelaAdapter(enabled_config(), client).respond(
            "hello", 42, request_id=request_id
        )
    finally:
        await client.aclose()
    assert result == "Hello from Vennela"
    assert seen["session_id"] == "telegram:42"
    assert seen["request_id"] == request_id


@pytest.mark.asyncio
async def test_adapter_returns_marked_test_response_when_disabled():
    config = TelegramConfig("token", frozenset({42}))
    with pytest.raises(VennelaAdapterError, match="forwarding is disabled"):
        await VennelaAdapter(config).respond("hello", 42)


@pytest.mark.asyncio
async def test_adapter_handles_backend_failure():
    async def handler(request):
        return httpx.Response(504)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(VennelaAdapterError, match="temporarily unavailable"):
            await VennelaAdapter(enabled_config(), client).respond("hello", 42)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_adapter_handles_timeout():
    async def handler(request):
        raise httpx.ReadTimeout("backend timed out", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(VennelaAdapterError, match="temporarily unavailable"):
            await VennelaAdapter(enabled_config(), client).respond("hello", 42)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_adapter_handles_malformed_response():
    async def handler(request):
        return httpx.Response(200, json={"message": "missing response field"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(VennelaAdapterError, match="invalid response"):
            await VennelaAdapter(enabled_config(), client).respond("hello", 42)
    finally:
        await client.aclose()
