"""
Centralized Gemini fallback caller.
Provides call_gemini_with_fallback(genai, prompt_or_messages, system_instruction, model_chain, max_retries, backoff_base)

This encapsulates the retry/backoff and transient/permanent error detection logic so all callers use the same behavior.
"""
import time
import logging
from typing import List, Any, Optional

logger = logging.getLogger(__name__)


def _is_permanent_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(token in msg for token in ("invalid api key", "invalidapikey", "unauthorized", "invalid api", "authentication")):
        return True
    if any(token in msg for token in ("malformed request", "invalid request", "invalid argument", "bad request")):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None) or getattr(exc, "http_status", None)
    if status in (401, 403):
        return True
    return False


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(token in msg for token in ("rate limit", "rate-limited", "quota", "quota exceeded", "temporarily unavailable", "unavailable", "overloaded", "try again later")):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None) or getattr(exc, "http_status", None)
    if status in (429, 500, 502, 503, 504):
        return True
    return False


class GeminiFallbackError(Exception):
    """Raised when all models fail or a permanent error is detected."""
    pass


def call_gemini_with_fallback(
    genai_module: Any,
    prompt_or_messages: Any,
    system_instruction: str = "",
    model_chain: Optional[List[str]] = None,
    preferred_first: Optional[str] = None,
    max_retries: int = 2,
    backoff_base: float = 0.5,
):
    """
    Call the Gemini models in model_chain (or preferred_first + model_chain) with retries and backoff.
    Returns the successful model response object (the object returned by model.generate_content), or raises GeminiFallbackError/Exception.
    """
    if model_chain is None:
        model_chain = []

    # Build ordered unique chain, with preferred_first first if provided
    ordered = []
    if preferred_first:
        ordered.append(preferred_first)
    for m in model_chain:
        if m not in ordered:
            ordered.append(m)

    if not ordered:
        raise GeminiFallbackError("No Gemini models configured")

    last_exc = None
    for idx, model_id in enumerate(ordered):
        logger.info(f"[GeminiFallback] Trying model: {model_id}")
        attempt = 0
        while attempt <= max_retries:
            try:
                # Create model instance; SDK may accept system_instruction at init
                try:
                    model = genai_module.GenerativeModel(model_id, system_instruction=system_instruction)
                except TypeError:
                    # Older SDKs may not accept system_instruction in constructor
                    model = genai_module.GenerativeModel(model_id)
                    # Some SDKs accept system instruction in generate_content call; we'll pass prompt/messages as-is

                response = model.generate_content(prompt_or_messages)
                logger.info(f"[GeminiFallback] Model succeeded: {model_id}")
                logger.debug(f"[GeminiFallback] Handled by model: {model_id}")
                return response

            except Exception as e:
                last_exc = e
                if _is_permanent_error(e):
                    logger.error(f"[GeminiFallback] Permanent error for model {model_id}: {e}")
                    # Surface permanent error immediately
                    raise

                if _is_transient_error(e):
                    logger.warning(f"[GeminiFallback] Transient error for model {model_id}: {e}")
                    attempt += 1
                    if attempt <= max_retries:
                        sleep_for = backoff_base * (2 ** (attempt - 1))
                        logger.info(f"[GeminiFallback] Retrying model {model_id} in {sleep_for:.2f}s (attempt {attempt}/{max_retries})")
                        time.sleep(sleep_for)
                        continue
                    else:
                        next_model = ordered[idx + 1] if idx + 1 < len(ordered) else None
                        logger.info(f"[GeminiFallback] Falling back to: {next_model if next_model else 'none'}")
                        break

                # Non-transient unknown error: don't retry this model; try next
                logger.error(f"[GeminiFallback] Non-retriable error for model {model_id}: {e}")
                break

    logger.error("[GeminiFallback] All configured models failed")
    # Raise final exception for caller to turn into HTTP 503
    raise GeminiFallbackError(last_exc)
