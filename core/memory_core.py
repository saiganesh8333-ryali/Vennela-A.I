# core/memory_core.py

import logging
from typing import Dict

from core.memory_classifier import classify_memory
from core.memory_compressor import compress_memory

logger = logging.getLogger(__name__)


def importance_score(text: str) -> int:
    """
    Calculate importance score for a given text.
    """
    if not text or not isinstance(text, str):
        return 0

    text = text.lower()
    score = 0

    keyword_weights = {
        "my name": 10,
        "call me": 10,
        "i want": 4,
        "i need": 4,
        "project": 4,
        "goal": 4,
        "learn": 3,
        "i like": 3,
        "i love": 3,
        "remember": 5,
        "error": 5,
        "problem": 5,
        "failed": 5
    }

    for keyword, weight in keyword_weights.items():
        if keyword in text:
            score += weight

    if len(text) > 50:
        score += 1

    return min(score, 10)


def process_memory(user_message: str) -> Dict:
    """
    Main memory processing pipeline.
    """

    if not user_message:
        return {}

    try:

        # STEP 1: CLASSIFY
        memory_type = classify_memory(user_message)

        # STEP 2: COMPRESS
        compressed_memory = compress_memory(user_message)

        # STEP 3: IMPORTANCE
        score = importance_score(user_message)

        # STEP 4: DECISION
        should_store = score >= 4

        memory_data = {
            "type": memory_type,
            "compressed": compressed_memory,
            "importance": score,
            "should_store": should_store
        }

        logger.info(f"🧠 Memory processed: {memory_data}")

        return memory_data

    except Exception as e:

        logger.error(f"Memory processing failed: {e}")

        return {}