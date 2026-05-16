"""AI routing with Groq and OpenRouter."""

import logging
import os
import time
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# =========================
# CONFIGURATION
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

GROQ_FALLBACK_MODEL = os.getenv(
    "GROQ_FALLBACK_MODEL",
    "llama-3.1-8b-instant"
)

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-4o-mini"
)

TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))

TIMEOUT = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))

MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "500"))

# =========================
# BAD RESPONSE FILTER
# =========================

BAD_PATTERNS = [
    "system online",
    "listening",
    "how can i assist",
    "i'm ready to help",
    "i am ready to assist",
    "what's on your mind",
    "ready to engage",
    "provide information",
]


def is_bad_response(text: str) -> bool:

    if not text:
        return True

    lower = text.lower().strip()

    return any(pattern in lower for pattern in BAD_PATTERNS)


# =========================
# CLIENTS
# =========================

def get_groq_client() -> Optional[OpenAI]:

    if not GROQ_API_KEY:
        logger.warning("❌ GROQ_API_KEY missing")
        return None

    try:
        return OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=TIMEOUT
        )

    except Exception as e:
        logger.error(f"Groq client init failed: {e}")
        return None


def get_openrouter_client() -> Optional[OpenAI]:

    if not OPENROUTER_API_KEY:
        logger.warning("❌ OPENROUTER_API_KEY missing")
        return None

    try:
        return OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            timeout=TIMEOUT
        )

    except Exception as e:
        logger.error(f"OpenRouter client init failed: {e}")
        return None


# =========================
# MAIN AI FUNCTION
# =========================

def get_ai_response(messages: list) -> Dict[str, str]:

    if not messages:
        return {
            "provider": "error",
            "response": "No messages provided.",
            "error": "empty_messages"
        }

    # Ensure system message exists
    has_system = any(
        msg.get("role") == "system"
        for msg in messages
    )

    if not has_system:

        messages.insert(0, {
            "role": "system",
            "content": (
                "You are VENNELA AI. "
                "Reply naturally and directly. "
                "Do not repeat greetings. "
                "Do not say system online."
            )
        })

    # DEBUG LOGGING
    print("\n===== FINAL MESSAGES SENT TO AI =====\n")

    for msg in messages:
        print(msg)

    print("\n=====================================\n")

    # Try Groq first
    groq_response = try_groq(messages)

    if groq_response:
        return groq_response

    # Fallback OpenRouter
    openrouter_response = try_openrouter(messages)

    if openrouter_response:
        return openrouter_response

    # Final fail-safe
    return {
        "provider": "error",
        "response": (
            "AI temporarily unavailable. "
            "Please try again."
        ),
        "error": "all_providers_failed"
    }


# =========================
# GROQ
# =========================

def try_groq(messages: list) -> Optional[Dict[str, str]]:

    client = get_groq_client()

    if not client:
        return None

    models = [
        GROQ_MODEL,
        GROQ_FALLBACK_MODEL
    ]

    tried = set()

    for model in models:

        if not model or model in tried:
            continue

        tried.add(model)

        try:

            logger.info(f"🚀 Using Groq model: {model}")

            start = time.time()

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS
            )

            elapsed = int((time.time() - start) * 1000)

            ai_reply = (
                response.choices[0]
                .message
                .content
                .strip()
            )

            logger.info(f"✅ Groq success ({elapsed}ms)")
            logger.info(f"RAW: {ai_reply[:120]}")

            if is_bad_response(ai_reply):

                logger.warning(
                    "⚠️ Bad response filtered from Groq"
                )

                continue

            return {
                "provider": "Groq",
                "model": model,
                "response": ai_reply,
                "latency_ms": elapsed
            }

        except Exception as e:

            logger.warning(
                f"❌ Groq model failed ({model}): {e}"
            )

            continue

    return None


# =========================
# OPENROUTER FALLBACK
# =========================

def try_openrouter(messages: list) -> Optional[Dict[str, str]]:

    client = get_openrouter_client()

    if not client:
        return None

    try:

        logger.info("⚡ Switching to OpenRouter fallback")

        start = time.time()

        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS
        )

        elapsed = int((time.time() - start) * 1000)

        ai_reply = (
            response.choices[0]
            .message
            .content
            .strip()
        )

        logger.info(f"✅ OpenRouter success ({elapsed}ms)")
        logger.info(f"RAW: {ai_reply[:120]}")

        if is_bad_response(ai_reply):

            logger.warning(
                "⚠️ Bad response filtered from OpenRouter"
            )

            return None

        return {
            "provider": "OpenRouter",
            "model": OPENROUTER_MODEL,
            "response": ai_reply,
            "latency_ms": elapsed
        }

    except Exception as e:

        logger.warning(f"❌ OpenRouter failed: {e}")

        return None