"""Configuration and environment management for LLM Router with secret masking."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _bool(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _float(val: str | None, default: float) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _int(val: str | None, default: int) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 3
    recovery_seconds: float = 30.0
    half_open_probes: int = 1


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    api_key: str | None = None
    timeout_seconds: float = 30.0
    base_url: str | None = None
    default_model: str | None = None
    enabled: bool = True

    def __repr__(self) -> str:
        key_status = "present" if self.api_key else "missing"
        return f"ProviderConfig(provider={self.provider!r}, api_key=<{key_status}>, timeout={self.timeout_seconds}, enabled={self.enabled})"


@dataclass(frozen=True)
class RouterConfig:
    default_model_id: str = "google/gemini-2.5-flash-lite"
    emergency_model_id: str = "meta-llama/llama-3.1-8b-instruct"
    timeout_seconds: float = 30.0
    max_retries: int = 2
    retry_delay_seconds: float = 0.5
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    gemini_api_key: str | None = None
    telemetry_enabled: bool = True

    def __repr__(self) -> str:
        return (
            f"RouterConfig(default_model_id={self.default_model_id!r}, "
            f"emergency_model_id={self.emergency_model_id!r}, "
            f"timeout={self.timeout_seconds}, max_retries={self.max_retries}, "
            f"groq_key={'***' if self.groq_api_key else None}, "
            f"openrouter_key={'***' if self.openrouter_api_key else None})"
        )

    @classmethod
    def from_env(cls, env_path: Path | str | None = None) -> "RouterConfig":
        target_path = Path(env_path) if env_path else PROJECT_ENV_FILE
        if target_path.exists():
            load_dotenv(target_path, override=False)

        cb_config = CircuitBreakerConfig(
            failure_threshold=max(1, _int(os.getenv("HEALTH_FAILURE_THRESHOLD"), 3)),
            recovery_seconds=max(0.1, _float(os.getenv("HEALTH_RECOVERY_SECONDS"), 30.0)),
        )

        return cls(
            default_model_id=os.getenv("DEFAULT_MODEL_ID", "google/gemini-2.5-flash-lite"),
            emergency_model_id=os.getenv("EMERGENCY_MODEL_ID", "meta-llama/llama-3.1-8b-instruct"),
            timeout_seconds=max(0.1, _float(os.getenv("ROUTER_TIMEOUT_SECONDS"), 30.0)),
            max_retries=max(0, _int(os.getenv("MAX_RETRIES"), 2)),
            retry_delay_seconds=max(0.0, _float(os.getenv("ROUTER_RETRY_DELAY_SECONDS"), 0.5)),
            circuit_breaker=cb_config,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            telemetry_enabled=_bool(os.getenv("TELEMETRY_ENABLED"), True),
        )
