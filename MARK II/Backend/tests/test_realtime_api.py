import base64
import asyncio

import pytest
from fastapi import FastAPI
from google.genai import types
from fastapi.testclient import TestClient

from vennela_realtime.api import (
    GeminiLiveSession,
    _content_for_gemini,
    create_realtime_api,
)


class FakeLiveSession:
    def __init__(self):
        self.audio = []
        self.text = []
        self.tool_results = []
        self.closed = False
        self.content = []

    async def send_audio(self, data, mime_type):
        self.audio.append((data, mime_type))

    async def send_text(self, text):
        self.text.append(text)

    async def send_tool_result(self, call_id, name, result):
        self.tool_results.append((call_id, name, result))

    async def send_client_content(self, *, turns, turn_complete):
        self.content.append((turns, turn_complete))

    async def receive(self):
        if False:
            yield None

    async def close(self):
        self.closed = True


@pytest.fixture
def realtime_app(monkeypatch):
    monkeypatch.setenv("VENNELA_REALTIME_TOKEN", "test-token")
    session = FakeLiveSession()

    async def factory(**kwargs):
        return session

    app = FastAPI()
    app.include_router(create_realtime_api(factory))
    return app, session


def test_realtime_requires_bearer_auth(realtime_app):
    app, _ = realtime_app
    with pytest.raises(Exception):
        with TestClient(app).websocket_connect("/ws/gemini/live"):
            pass


def test_realtime_forwards_audio_text_and_tool_result(realtime_app):
    app, session = realtime_app
    with TestClient(app).websocket_connect(
        "/ws/gemini/live", headers={"Authorization": "Bearer test-token"}
    ) as websocket:
        websocket.send_json(
            {
                "type": "session.start",
                "user_id": "boss",
                "session_id": "session-1",
            }
        )
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["session_id"] == "session-1"

        payload = base64.b64encode(b"\x01\x02").decode("ascii")
        websocket.send_json({"type": "audio", "data": payload})
        websocket.send_json({"type": "text", "text": "hello"})
        websocket.send_json(
            {
                "type": "tool_result",
                "call_id": "call-1",
                "name": "get_battery_status",
                "result": {"percent": 80},
            }
        )
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

    assert session.audio == [(b"\x01\x02", "audio/pcm;rate=16000")]
    assert session.text == ["hello"]
    assert session.tool_results == [
        ("call-1", "get_battery_status", {"percent": 80})
    ]
    assert session.closed


def test_thought_signature_history_uses_sdk_bytes():
    hex_signature = "018f3d6b5fcc9629d008d5634f22fefe"
    content = _content_for_gemini(
        {
            "role": "model",
            "parts": [{"text": "answer", "thought_signature": hex_signature}],
        },
        types,
    )

    assert content.parts[0].thought_signature == bytes.fromhex(hex_signature)
    serialized = content.model_dump(mode="json", exclude_none=True)
    assert serialized["parts"][0]["thought_signature"] != hex_signature
    assert isinstance(serialized["parts"][0]["thought_signature"], str)


def test_thought_signature_response_json_round_trip_uses_sdk_bytes():
    signature = bytes.fromhex("018f3d6b5fcc9629d008d5634f22fefe")
    response_part = types.Part(text="answer", thought_signature=signature)
    persisted_history = {
        "role": "model",
        "parts": [response_part.model_dump(mode="json", exclude_none=True)],
    }

    content = _content_for_gemini(persisted_history, types)

    assert content.parts[0].thought_signature == signature


def test_thought_signature_history_is_rehydrated_before_next_request():
    asyncio.run(_assert_thought_signature_history_is_rehydrated())


async def _assert_thought_signature_history_is_rehydrated():
    session = FakeLiveSession()
    live = GeminiLiveSession(session, types)
    await live.send_history(
        [
            {
                "role": "user",
                "parts": [{"text": "question"}],
            },
            {
                "role": "model",
                "parts": [
                    {
                        "text": "answer",
                        "thought_signature": "018f3d6b5fcc9629d008d5634f22fefe",
                    }
                ],
            },
        ]
    )

    turns, turn_complete = session.content[0]
    assert turn_complete is True
    assert turns[1].parts[0].thought_signature == bytes.fromhex(
        "018f3d6b5fcc9629d008d5634f22fefe"
    )
