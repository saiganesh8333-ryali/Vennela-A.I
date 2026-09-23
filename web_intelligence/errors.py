"""Typed error definitions and failure classifications for Web Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailureKind(str, Enum):
    NO_API_KEY = "NO_API_KEY"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    NETWORK = "NETWORK"
    SERVER = "SERVER"
    AUTH = "AUTH"
    INVALID_REQUEST = "INVALID_REQUEST"
    PAGE_FETCH_ERROR = "PAGE_FETCH_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    message: str
    retryable: bool = False
    provider: str | None = None
    status_code: int | None = None
    details: dict[str, Any] | None = None


class WebHuntError(Exception):
    """Base exception for all web hunt / internet intelligence operations."""

    def __init__(self, failure: Failure) -> None:
        self.failure = failure
        super().__init__(failure.message)

    @classmethod
    def missing_key(cls, provider: str) -> "WebHuntError":
        return cls(
            Failure(
                kind=FailureKind.NO_API_KEY,
                message=f"{provider} API key is not configured or is empty",
                retryable=False,
                provider=provider,
            )
        )

    @classmethod
    def timeout(cls, provider: str, message: str = "Search request timed out") -> "WebHuntError":
        return cls(
            Failure(
                kind=FailureKind.TIMEOUT,
                message=message,
                retryable=True,
                provider=provider,
            )
        )

    @classmethod
    def rate_limit(cls, provider: str, message: str = "Rate limit exceeded") -> "WebHuntError":
        return cls(
            Failure(
                kind=FailureKind.RATE_LIMIT,
                message=message,
                retryable=True,
                provider=provider,
                status_code=429,
            )
        )

    @classmethod
    def server_error(cls, provider: str, message: str, status_code: int | None = None) -> "WebHuntError":
        return cls(
            Failure(
                kind=FailureKind.SERVER,
                message=message,
                retryable=True,
                provider=provider,
                status_code=status_code,
            )
        )

    @classmethod
    def invalid_response(cls, provider: str, message: str) -> "WebHuntError":
        return cls(
            Failure(
                kind=FailureKind.INVALID_RESPONSE,
                message=message,
                retryable=False,
                provider=provider,
            )
        )
