# core/memory_core.py

import logging
from typing import Dict

from core.memory_classifier import classify_memory
from core.memory_compressor import compress_memory

from memory.smart_memory import importance_score

logger = logging.getLogger(__name__)


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