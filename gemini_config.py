"""
Centralized Gemini model chain configuration.
Provides a single source of truth for GEMINI_MODEL_CHAIN used across the project.
"""
import os
import logging

logger = logging.getLogger(__name__)

def get_gemini_model_chain():
    """Return a list of Gemini model IDs from environment or default minimal chain.

    IMPORTANT: Do NOT hardcode guessed model IDs here. The default chain uses only the
    current primary model referenced in the project. For full multi-model chains, set
    the GEMINI_MODEL_CHAIN environment variable (comma-separated) to a verified list.
    """
    chain_env = os.getenv("GEMINI_MODEL_CHAIN", "").strip()
    if chain_env:
        chain = [m.strip() for m in chain_env.split(",") if m.strip()]
        logger.info(f"[GeminiConfig] Using GEMINI_MODEL_CHAIN from env: {chain}")
        return chain

    # Conservative default: only the currently used primary model.
    default = ["gemini-3.5-flash"]
    logger.warning("[GeminiConfig] GEMINI_MODEL_CHAIN not set. Using conservative default: %s", default)
    return default
