"""FastAPI WebSocket router and endpoints for the real-time Agent Gateway."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, FastAPI, Query, WebSocket, WebSocketDisconnect, status

from .gateway import AgentGateway
from .transport import (
    AuthenticationError,
    AgentTransportManager,
    RegistrationError,
)

logger = logging.getLogger(__name__)


def create_agent_transport_api(
    gateway: AgentGateway,
    transport_manager: AgentTransportManager | None = None,
) -> tuple[APIRouter, AgentTransportManager]:
    """Create a FastAPI APIRouter exposing the authenticated /ws/agents/{agent_id} endpoint."""
    manager = transport_manager or AgentTransportManager(gateway=gateway)
    router = APIRouter(tags=["automation_agents"])

    @router.websocket("/ws/agents/{agent_id}")
    async def agent_websocket_endpoint(
        websocket: WebSocket,
        agent_id: str,
        token: Optional[str] = Query(None),
    ) -> None:
        # Check token from query param or Authorization header
        header_auth = websocket.headers.get("authorization")
        if header_auth and header_auth.lower().startswith("bearer "):
            token = header_auth[7:].strip()

        await websocket.accept()

        registered_agent_id: str | None = None
        loop = asyncio.get_event_loop()

        try:
            # 1. Await registration handshake frame
            try:
                raw_init = await websocket.receive_text()
                handshake = json.loads(raw_init)
            except Exception as e:
                await websocket.send_json({"type": "error", "error": f"Malformed handshake JSON: {e}"})
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            if not isinstance(handshake, dict) or handshake.get("type") != "register":
                await websocket.send_json({
                    "type": "error",
                    "error": "First message must be a registration frame with type='register'",
                })
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Combine token from handshake if not in query/header
            handshake_token = token or handshake.get("token")
            handshake["token"] = handshake_token

            # Verify agent_id in payload matches URL param
            payload_agent_id = handshake.get("agent_id")
            if payload_agent_id and str(payload_agent_id).strip() != agent_id.strip():
                await websocket.send_json({
                    "type": "error",
                    "error": f"URL agent_id '{agent_id}' does not match handshake agent_id '{payload_agent_id}'",
                })
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            handshake["agent_id"] = agent_id.strip()

            # 2. Register connection with transport manager
            try:
                connection, agent = manager.register_connection(websocket, handshake, loop)
                registered_agent_id = agent_id.strip()
            except (AuthenticationError, RegistrationError) as exc:
                await websocket.send_json({"type": "error", "error": str(exc)})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # 3. Send successful registration response
            await websocket.send_json({
                "type": "registered",
                "version": "1.0",
                "agent_id": registered_agent_id,
                "status": "online",
            })

            # 4. Message processing loop
            while True:
                msg_text = await websocket.receive_text()
                try:
                    data = json.loads(msg_text)
                except Exception as exc:
                    await websocket.send_json({"type": "error", "error": f"Invalid JSON message: {exc}"})
                    continue

                if not isinstance(data, dict):
                    await websocket.send_json({"type": "error", "error": "Message frame must be a JSON object"})
                    continue

                msg_type = data.get("type")

                if msg_type in ("ping", "heartbeat"):
                    connection.update_last_seen()
                    resp_type = "pong" if msg_type == "ping" else "heartbeat_ack"
                    await websocket.send_json({"type": resp_type, "timestamp": time.time()})

                elif msg_type == "result":
                    connection.handle_result(data)

                elif msg_type == "pong":
                    connection.update_last_seen()

                else:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Unsupported message type: '{msg_type}'",
                    })

        except WebSocketDisconnect:
            logger.info(f"Agent '{agent_id}' disconnected")
        except Exception as exc:
            logger.warning(f"Unexpected error in agent WebSocket '{agent_id}': {exc}")
        finally:
            if registered_agent_id:
                manager.unregister_connection(registered_agent_id, reason="Connection terminated")

    return router, manager


def create_agent_app(gateway: AgentGateway | None = None) -> tuple[FastAPI, AgentGateway, AgentTransportManager]:
    """App factory creating a FastAPI app with agent transport API mounted for testing or standalone execution."""
    gw = gateway or AgentGateway()
    router, tm = create_agent_transport_api(gw)

    app = FastAPI(title="Vennela Agent Gateway", version="1.0.0")
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"status": "ok", "active_agents": len(tm._connections)}

    return app, gw, tm
