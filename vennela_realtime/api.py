"""Authenticated WebSocket proxy for Gemini Live sessions."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import os
import re
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

logger = logging.getLogger(__name__)

MAX_FRAME_BYTES = 512 * 1024
MAX_SESSION_ID_LENGTH = 128
MAX_USER_ID_LENGTH = 256
_HEX_SIGNATURE = re.compile(r"^[0-9a-fA-F]+$")
_BASE64_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]*={0,2}$")


def _field(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            candidate = getattr(value, name)
            if candidate is not None:
                return candidate
    return None


def _bearer_token(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _configured_token() -> str:
    return os.getenv("VENNELA_REALTIME_TOKEN", "").strip() or os.getenv(
        "VENNELA_AGENT_TOKEN", ""
    ).strip()


def _origin_allowed(websocket: WebSocket) -> bool:
    configured = os.getenv("VENNELA_REALTIME_ALLOWED_ORIGINS", "").strip()
    if not configured:
        return True
    origin = websocket.headers.get("origin", "")
    return origin in {item.strip() for item in configured.split(",") if item.strip()}


def _tool_declarations() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_battery_status",
            "description": "Get the current Android device battery status.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "play_latest_news",
            "description": "Ask the Android device to play the latest news.",
            "parameters": {"type": "object", "properties": {}},
        },
    ]


def _thought_signature_bytes(value: Any) -> bytes:
    """Convert persisted thought-signature data to the SDK's required bytes."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized and len(normalized) % 2 == 0 and _HEX_SIGNATURE.fullmatch(normalized):
            return bytes.fromhex(normalized)
        try:
            if not _BASE64_SIGNATURE.fullmatch(normalized):
                raise ValueError("invalid encoded bytes")
            unpadded = normalized.rstrip("=")
            if len(unpadded) % 4 == 1:
                raise ValueError("invalid encoded bytes length")
            padded = unpadded + "=" * (-len(unpadded) % 4)
            decoded = base64.b64decode(
                padded.replace("-", "+").replace("_", "/"),
                validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise ValueError("thought_signature must be SDK bytes or valid encoded bytes") from exc
        if not decoded:
            raise ValueError("thought_signature must not be empty")
        return decoded
    raise TypeError("thought_signature must be SDK bytes or an encoded string")


def _content_for_gemini(value: Any, types: Any) -> Any:
    """Rehydrate history with SDK-native Parts while keeping signatures transient."""
    if isinstance(value, types.Content):
        parts = [
            types.Part(
                **{
                    **part.model_dump(exclude_none=True),
                    **(
                        {
                            "thought_signature": _thought_signature_bytes(
                                part.thought_signature
                            )
                        }
                        if part.thought_signature is not None
                        else {}
                    ),
                }
            )
            for part in (value.parts or [])
        ]
        return types.Content(role=value.role, parts=parts)
    if not isinstance(value, dict):
        raise TypeError("Gemini history content must be an SDK Content or mapping")

    parts = []
    for raw_part in value.get("parts") or []:
        if not isinstance(raw_part, dict):
            raise TypeError("Gemini history parts must be mappings")
        part = dict(raw_part)
        signature_key = (
            "thought_signature"
            if "thought_signature" in part
            else "thoughtSignature"
            if "thoughtSignature" in part
            else None
        )
        if signature_key is not None:
            part["thought_signature"] = _thought_signature_bytes(part.pop(signature_key))
        parts.append(types.Part(**part))
    return types.Content(role=value.get("role"), parts=parts)


class RealtimeConfigurationError(RuntimeError):
    """Raised when the server cannot create a secure upstream session."""


class GeminiLiveSession:
    """Small adapter around the optional Google GenAI Live SDK."""

    def __init__(self, session: Any, types: Any) -> None:
        self._session = session
        self._types = types

    @classmethod
    async def connect(
        cls,
        *,
        api_key: str,
        model: str,
        system_instruction: str | None = None,
    ) -> "GeminiLiveSession":
        if not api_key:
            raise RealtimeConfigurationError("Gemini Live is not configured on the server")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RealtimeConfigurationError(
                "Gemini Live support is not installed on the server"
            ) from exc

        client = genai.Client(api_key=api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=system_instruction or None,
            tools=[types.Tool(function_declarations=_tool_declarations())],
        )
        session = await client.aio.live.connect(model=model, config=config)
        return cls(session, types)

    async def send_audio(self, data: bytes, mime_type: str) -> None:
        await self._session.send_realtime_input(
            audio=self._types.Blob(data=data, mime_type=mime_type)
        )

    async def send_text(self, text: str) -> None:
        await self._session.send_client_content(
            turns=self._content_for_gemini(
                {"role": "user", "parts": [{"text": text}]}, self._types
            ),
            turn_complete=True,
        )

    async def send_history(self, turns: Any) -> None:
        """Send rehydrated history without treating transient metadata as text."""
        if isinstance(turns, list):
            normalized = [
                self._content_for_gemini(turn, self._types) for turn in turns
            ]
        else:
            normalized = self._content_for_gemini(turns, self._types)
        await self._session.send_client_content(
            turns=normalized,
            turn_complete=True,
        )

    @staticmethod
    def _content_for_gemini(value: Any, types: Any) -> Any:
        return _content_for_gemini(value, types)

    async def send_tool_result(
        self, call_id: str, name: str, result: dict[str, Any]
    ) -> None:
        await self._session.send_tool_response(
            function_responses=[
                self._types.FunctionResponse(
                    id=call_id,
                    name=name,
                    response=result,
                )
            ]
        )

    async def receive(self):
        async for response in self._session.receive():
            yield response

    async def close(self) -> None:
        close = getattr(self._session, "close", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result


def _decode_audio(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ValueError("audio.data must be a base64 string")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("audio.data is not valid base64") from exc


async def _send_json(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_text(json.dumps(payload, separators=(",", ":")))


def create_realtime_api(
    session_factory: Callable[..., Any] | None = None,
) -> APIRouter:
    """Create the authenticated Gemini Live proxy router."""
    router = APIRouter(tags=["realtime"])
    factory = session_factory or GeminiLiveSession.connect

    @router.websocket("/ws/gemini/live")
    async def gemini_live_endpoint(websocket: WebSocket) -> None:
        expected_token = _configured_token()
        supplied_token = _bearer_token(websocket)
        if not expected_token or supplied_token != expected_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if not _origin_allowed(websocket):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        upstream: GeminiLiveSession | Any | None = None
        receiver_task: asyncio.Task[Any] | None = None
        realtime_session_id = str(uuid4())
        try:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
                raise ValueError("Handshake frame is too large")
            handshake = json.loads(raw)
            if not isinstance(handshake, dict) or handshake.get("type") != "session.start":
                raise ValueError("First frame must have type='session.start'")

            user_id = str(handshake.get("user_id", "")).strip()
            session_id = str(handshake.get("session_id", "")).strip()
            if not user_id or len(user_id) > MAX_USER_ID_LENGTH:
                raise ValueError("user_id is required")
            if not session_id or len(session_id) > MAX_SESSION_ID_LENGTH:
                raise ValueError("session_id is required")

            configured_user = os.getenv("VENNELA_REALTIME_USER_ID", "").strip()
            if configured_user and user_id != configured_user:
                raise PermissionError("user_id is not authorized for this session")

            model = str(
                handshake.get("model")
                or os.getenv("GEMINI_LIVE_MODEL", "gemini-2.0-flash-live-001")
            ).strip()
            upstream = await factory(
                api_key=os.getenv("GEMINI_API_KEY", "").strip(),
                model=model,
                system_instruction=os.getenv("VENNELA_PROMPT", "").strip() or None,
            )
            await _send_json(
                websocket,
                {
                    "type": "session.ready",
                    "session_id": session_id,
                    "realtime_session_id": realtime_session_id,
                    "user_id": user_id,
                    "model": model,
                },
            )

            async def forward_upstream() -> None:
                async for response in upstream.receive():
                    audio = _field(response, "data", "audio")
                    if isinstance(audio, bytes):
                        await _send_json(
                            websocket,
                            {
                                "type": "audio",
                                "data": base64.b64encode(audio).decode("ascii"),
                                "mime_type": "audio/pcm",
                            },
                        )
                    text = _field(response, "text")
                    if isinstance(text, str) and text:
                        await _send_json(websocket, {"type": "text", "text": text})
                    tool_call = _field(response, "tool_call", "toolCall")
                    if tool_call is not None:
                        calls = _field(tool_call, "function_calls", "functionCalls") or []
                        await _send_json(
                            websocket,
                            {
                                "type": "tool_call",
                                "calls": [
                                    {
                                        "id": _field(call, "id") or str(uuid4()),
                                        "name": _field(call, "name") or "",
                                        "args": _field(call, "args") or {},
                                    }
                                    for call in calls
                                ],
                            },
                        )
                    if _field(response, "server_content", "serverContent") is not None:
                        interrupted = _field(
                            _field(response, "server_content", "serverContent"),
                            "interrupted",
                        )
                        if interrupted:
                            await _send_json(websocket, {"type": "interrupted"})

            receiver_task = asyncio.create_task(forward_upstream())
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    if len(message["bytes"]) > MAX_FRAME_BYTES:
                        raise ValueError("Audio frame is too large")
                    await upstream.send_audio(message["bytes"], "audio/pcm;rate=16000")
                    continue
                raw_message = message.get("text")
                if raw_message is None or len(raw_message.encode("utf-8")) > MAX_FRAME_BYTES:
                    raise ValueError("Message frame is missing or too large")
                payload = json.loads(raw_message)
                if not isinstance(payload, dict):
                    raise ValueError("Message frame must be a JSON object")
                message_type = payload.get("type")
                if message_type == "audio":
                    audio = _decode_audio(_field(payload, "data"))
                    await upstream.send_audio(
                        audio, str(payload.get("mime_type") or "audio/pcm;rate=16000")
                    )
                elif message_type == "text":
                    await upstream.send_text(str(payload.get("text") or ""))
                elif message_type == "tool_result":
                    await upstream.send_tool_result(
                        str(payload.get("call_id") or ""),
                        str(payload.get("name") or ""),
                        payload.get("result") if isinstance(payload.get("result"), dict) else {},
                    )
                elif message_type == "ping":
                    await _send_json(websocket, {"type": "pong"})
                else:
                    await _send_json(websocket, {"type": "error", "error": "Unsupported message type"})
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except (ValueError, PermissionError, RealtimeConfigurationError) as exc:
            await _send_json(websocket, {"type": "error", "error": str(exc)})
        except Exception:
            logger.exception("Gemini Live proxy failed for session %s", realtime_session_id)
            await _send_json(
                websocket,
                {"type": "error", "error": "Realtime service temporarily unavailable"},
            )
        finally:
            if receiver_task is not None:
                receiver_task.cancel()
                await asyncio.gather(receiver_task, return_exceptions=True)
            if upstream is not None:
                await upstream.close()

    return router
