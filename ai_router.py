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
GROQ_MODEL = "llama3-70b-8192"
OPENROUTER_MODEL = "openai/gpt-4o-mini"
TEMPERATURE = 0.7
TIMEOUT = 30


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
        
        logger.debug("Sending request to Groq...")
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=2048
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Groq response received in {elapsed:.2f}s")
        
        return {
            "provider": "Groq",
            "response": response.choices[0].message.content,
            "latency_ms": int(elapsed * 1000)
        }
        
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