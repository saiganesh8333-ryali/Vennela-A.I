import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vennela_realtime.api import create_realtime_api


class FakeLiveSession:
    def __init__(self):
        self.audio = []
        self.text = []
        self.tool_results = []
        self.closed = False

    async def send_audio(self, data, mime_type):
        self.audio.append((data, mime_type))

    async def send_text(self, text):
        self.text.append(text)

    async def send_tool_result(self, call_id, name, result):
        self.tool_results.append((call_id, name, result))

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
