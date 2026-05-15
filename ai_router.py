"""AI routing with Groq and OpenRouter with enhanced error handling and logging."""
import logging
import os
import time
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI, APIError, RateLimitError, APIConnectionError

logger = logging.getLogger(__name__)

load_dotenv()

# =========================
# CONFIGURATION
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))
TIMEOUT = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))


# =========================
# CLIENT INITIALIZATION
# =========================
def _get_groq_client() -> Optional[OpenAI]:
    """Initialize Groq client with error handling."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set in environment")
        return None
    
    try:
        return OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=TIMEOUT
        )
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return None


def _get_openrouter_client() -> Optional[OpenAI]:
    """Initialize OpenRouter client with error handling."""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set in environment")
        return None
    
    try:
        return OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            timeout=TIMEOUT
        )
    except Exception as e:
        logger.error(f"Failed to initialize OpenRouter client: {e}")
        return None


def _groq_models() -> list:
    """Return Groq models to try in order without duplicates."""
    models = [GROQ_MODEL, GROQ_FALLBACK_MODEL]
    return [model for index, model in enumerate(models) if model and model not in models[:index]]


# =========================
# AI RESPONSE GENERATION
# =========================
def get_ai_response(messages: list) -> Dict[str, str]:
    """
    Get AI response with provider fallback and error handling.
    
    Tries Groq first, falls back to OpenRouter, then returns error message.
    
    Args:
        messages: List of message dicts with "role" and "content"
        
    Returns:
        Dict with "provider" and "response" keys
    """
    if not messages:
        logger.error("No messages provided to get_ai_response")
        return {
            "provider": "error",
            "response": "No messages provided"
        }
    
    # Try Groq first
    response = _try_groq(messages)
    if response:
        return response
    
    # Fallback to OpenRouter
    response = _try_openrouter(messages)
    if response:
        return response
    
    # Final fail-safe
    logger.error("Both Groq and OpenRouter failed")
    return {
        "provider": "none",
        "response": "Both AI providers unavailable. Please try again later."
    }


def _try_groq(messages: list) -> Optional[Dict[str, str]]:
    """
    Try to get response from Groq.
    
    Args:
        messages: List of message dicts
        
    Returns:
        Dict with response or None if failed
    """
    try:
        client = _get_groq_client()
        if not client:
            logger.debug("Groq client not initialized")
            return None
        
        for model in _groq_models():
            try:
                logger.debug(f"Sending request to Groq model {model}...")
                start_time = time.time()

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_tokens=2048
                )

                elapsed = time.time() - start_time
                logger.info(f"Groq response received from {model} in {elapsed:.2f}s")

                return {
                    "provider": "Groq",
                    "model": model,
                    "response": response.choices[0].message.content,
                    "latency_ms": int(elapsed * 1000)
                }
            except APIError as e:
                logger.warning(f"Groq API error for model {model}: {e}")
                continue

        return None
        
    except RateLimitError as e:
        logger.warning(f"Groq rate limit hit: {e}")
        return None
    except APIConnectionError as e:
        logger.warning(f"Groq connection error: {e}")
        return None
    except APIError as e:
        logger.warning(f"Groq API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error from Groq: {e}")
        return None


def _try_openrouter(messages: list) -> Optional[Dict[str, str]]:
    """
    Try to get response from OpenRouter (fallback).
    
    Args:
        messages: List of message dicts
        
    Returns:
        Dict with response or None if failed
    """
    try:
        client = _get_openrouter_client()
        if not client:
            logger.debug("OpenRouter client not initialized")
            return None
        
        logger.debug("Sending request to OpenRouter (fallback)...")
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=2048
        )
        
        elapsed = time.time() - start_time
        logger.info(f"OpenRouter response received in {elapsed:.2f}s")
        
        return {
            "provider": "OpenRouter",
            "model": OPENROUTER_MODEL,
            "response": response.choices[0].message.content,
            "latency_ms": int(elapsed * 1000)
        }
        
    except RateLimitError as e:
        logger.warning(f"OpenRouter rate limit hit: {e}")
        return None
    except APIConnectionError as e:
        logger.warning(f"OpenRouter connection error: {e}")
        return None
    except APIError as e:
        logger.warning(f"OpenRouter API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error from OpenRouter: {e}")
        return None
