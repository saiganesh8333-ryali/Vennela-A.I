import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class LLMConfig:
    mode: str = "DETERMINISTIC"
    provider: str = "openai_compatible"
    model: str = ""
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 20.0
    max_retries: int = 1

    @classmethod
    def from_environment(cls) -> "LLMConfig":
        return cls(
            mode=os.getenv("LLM_MODE", "DETERMINISTIC").upper(),
            provider=os.getenv("LLM_PROVIDER", "openai_compatible"),
            model=os.getenv("LLM_MODEL", ""),
            api_key=os.getenv("LLM_API_KEY") or None,
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
        )

    def validate_real_mode(self) -> None:
        if self.mode == "REAL" and (not self.api_key or not self.model):
            raise ValueError("REAL mode requires LLM_API_KEY and LLM_MODEL")
        if self.timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if self.max_retries < 0:
            raise ValueError("LLM_MAX_RETRIES cannot be negative")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("LLM_BASE_URL must be an absolute HTTP(S) URL")
