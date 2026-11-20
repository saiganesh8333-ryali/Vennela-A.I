"""HTTP adapter from Telegram messages to Vennela's existing /chat endpoint."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from .config import TelegramConfig

logger = logging.getLogger(__name__)


class VennelaAdapterError(RuntimeError):
    """Raised when the Vennela API cannot provide a safe response."""


def session_id_for_chat(chat_id: int | str) -> str:
    """Return the stable Vennela session namespace for a Telegram chat."""
    return f"telegram:{chat_id}"


def build_chat_payload(message: str, chat_id: int | str) -> dict[str, str]:
    """Transform a Telegram message into the existing Vennela request shape."""
    return {
        "message": message,
        "user_id": f"telegram:{chat_id}",
        "session_id": session_id_for_chat(chat_id),
    }


class VennelaAdapter:
    def __init__(
        self,
        config: TelegramConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    async def respond(
        self,
        message: str,
        chat_id: int | str,
        request_id: str | None = None,
    ) -> str:
        request_id = request_id or uuid4().hex
        if not self.config.vennela_chat_enabled:
            error = VennelaAdapterError("Vennela /chat forwarding is disabled")
            logger.error(
                "[TELEGRAM] error stage=vennela_request request_id=%s error_class=%s",
                request_id,
                type(error).__name__,
            )
            raise error

        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.config.request_timeout_seconds)
        started = perf_counter()
        status_code: int | None = None
        logger.info("[TELEGRAM] vennela_request_started request_id=%s", request_id)
        try:
            response = await client.post(
                self.config.chat_url,
                json=build_chat_payload(message, chat_id),
                headers={"X-Request-ID": request_id},
            )
            status_code = response.status_code
            response.raise_for_status()
            data: Any = response.json()
            text = data.get("response") if isinstance(data, dict) else None
            if not isinstance(text, str) or not text.strip():
                raise VennelaAdapterError("Vennela returned an invalid response")
            duration_ms = round((perf_counter() - started) * 1000, 3)
            logger.info(
                "[TELEGRAM] vennela_request_completed request_id=%s status_code=%s duration_ms=%.3f",
                request_id,
                response.status_code,
                duration_ms,
            )
            logger.info(
                "[TELEGRAM] response_generated request_id=%s response_nonempty=true",
                request_id,
            )
            return text
        except httpx.HTTPStatusError as exc:
            logger.error(
                "[TELEGRAM] error stage=vennela_request request_id=%s error_class=%s "
                "status_code=%s duration_ms=%.3f",
                request_id,
                type(exc).__name__,
                exc.response.status_code,
                (perf_counter() - started) * 1000,
            )
            raise VennelaAdapterError("Vennela is temporarily unavailable") from exc
        except VennelaAdapterError as exc:
            logger.error(
                "[TELEGRAM] error stage=vennela_response request_id=%s error_class=%s "
                "status_code=%s duration_ms=%.3f",
                request_id,
                type(exc).__name__,
                status_code,
                (perf_counter() - started) * 1000,
            )
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.error(
                "[TELEGRAM] error stage=vennela_response request_id=%s error_class=%s "
                "status_code=%s duration_ms=%.3f",
                request_id,
                type(exc).__name__,
                status_code,
                (perf_counter() - started) * 1000,
            )
            raise VennelaAdapterError("Vennela is temporarily unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()
