"""Advanced Smart Memory Engine"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from memory.embedding_engine import get_embedding
from firebase.firebase_db import get_db
from ai.nlp_engine import detect_emotion, detect_sentiment
from core.memory_core import process_memory, importance_score

logger = logging.getLogger(__name__)

# =========================
# LIMITS
# =========================

MAX_SHORT_TERM = 30
MAX_LONG_TERM = 100
MAX_EPISODIC = 50
MAX_IMPORTANCE = 100
MAX_EMBEDDINGS = 200
MAX_MESSAGE_LENGTH = 5000

# =========================
# DEFAULT MEMORY
# =========================

def _default_memory() -> Dict:

    return {
        "profile": {},
        "short_term": [],
        "long_term": [],
        "episodic": [],
        "emotions": {},
        "sentiments": {},
        "importance": [],
        "summary": "",
        "embeddings": []
    }

# =========================
# NORMALIZE MEMORY
# =========================

def _normalize_memory(data: Optional[Dict]) -> Dict:

    if not data or not isinstance(data, dict):
        return _default_memory()

    memory = _default_memory()

    memory["profile"] = data.get("profile", {})
    memory["short_term"] = data.get("short_term", [])
    memory["long_term"] = data.get("long_term", [])
    memory["episodic"] = data.get("episodic", [])
    memory["emotions"] = data.get("emotions", {})
    memory["sentiments"] = data.get("sentiments", {})
    memory["importance"] = data.get("importance", [])
    memory["summary"] = data.get("summary", "")
    memory["embeddings"] = data.get("embeddings", [])

    return memory

# =========================
# DATABASE
# =========================

def get_memory(user_id: str) -> Dict:

    try:

        db = get_db()

        if not db:
            return _default_memory()

        doc = (
            db.collection("memory")
            .document(user_id)
            .get()
        )

        if doc.exists:
            return _normalize_memory(doc.to_dict())

        return _default_memory()

    except Exception as e:

        logger.error(f"Memory load error: {e}")

        return _default_memory()


def save_memory(user_id: str, data: Dict) -> bool:

    try:

        db = get_db()

        if not db:
            return False

        (
            db.collection("memory")
            .document(user_id)
            .set(data, merge=True)
        )

        return True

    except Exception as e:

        logger.error(f"Memory save error: {e}")

        return False

# =========================
# IMPORTANCE SCORE
# =========================

def importance_score(text: str) -> int:

    text = text.lower()

    score = 0

    keywords = {
        "my name": 10,
        "call me": 10,
        "goal": 6,
        "dream": 6,
        "project": 5,
        "remember": 5,
        "i love": 4,
        "i like": 3,
        "problem": 5,
        "error": 5,
        "failed": 5
    }

    for keyword, weight in keywords.items():

        if keyword in text:
            score += weight

    if len(text) > 50:
        score += 1

    return min(score, 10)

# =========================
# PROFILE UPDATE
# =========================

def _extract_phrase_after(text: str, marker: str):

    try:

        pattern = rf"{re.escape(marker)}\s+([a-zA-Z ]+)"

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if not match:
            return ""

        return match.group(1).strip()

    except:
        return ""


def _update_profile(user_message: str, memory: Dict):

    profile = memory.setdefault("profile", {})

    lower = user_message.lower()

    if "my name is" in lower:

        name = _extract_phrase_after(
            user_message,
            "my name is"
        )

        if name:
            profile["name"] = name.title()

    if "call me" in lower:

        preferred = _extract_phrase_after(
            user_message,
            "call me"
        )

        if preferred:
            profile["preferred_name"] = preferred.title()

# =========================
# MEMORY SUMMARY
# =========================

def summarize_memory(memory: Dict):

    try:

        parts = []

        profile = memory.get("profile", {})

        if profile.get("name"):

            parts.append(
                f"User name is {profile['name']}"
            )

        if profile.get("preferred_name"):

            parts.append(
                f"Preferred name is {profile['preferred_name']}"
            )

        episodic = memory.get("episodic", [])

        for event in episodic[-5:]:

            parts.append(
                f"Event: {event.get('event')}"
            )

        long_term = memory.get("long_term", [])

        parts.extend(long_term[-10:])

        memory["summary"] = " | ".join(parts[:20])

        return memory

    except Exception as e:

        logger.error(f"Summary error: {e}")

        return memory

# =========================
# UPDATE MEMORY
# =========================

def update_memory(
    user_id: str,
    user_msg: str,
    ai_reply: str,
    memory: Dict
):

    try:

        memory = _normalize_memory(memory)

        user_msg = user_msg[:MAX_MESSAGE_LENGTH]

        # =====================
        # EMOTION + SENTIMENT
        # =====================

        emotion = detect_emotion(user_msg)

        sentiment = detect_sentiment(user_msg)

        memory["emotions"][emotion] = (
            memory["emotions"].get(emotion, 0) + 1
        )

        memory["sentiments"][sentiment] = (
            memory["sentiments"].get(sentiment, 0) + 1
        )

        # =====================
        # PROCESS MEMORY
        # =====================

        result = process_memory(user_msg)

        score = result.get(
            "importance",
            importance_score(user_msg)
        )

        memory_type = result.get("type")

        compressed = result.get(
            "compressed",
            user_msg
        )

        should_store = result.get(
            "should_store",
            False
        )

        # =====================
        # EPISODIC MEMORY
        # =====================

        if (
            should_store
            and memory_type == "event"
        ):

            memory["episodic"].append({

                "event": compressed,

                "timestamp": datetime.utcnow().isoformat(),

                "importance": score
            })

        # =====================
        # LONG TERM
        # =====================

        elif should_store:

            if compressed not in memory["long_term"]:

                memory["long_term"].append(
                    compressed
                )

        # =====================
        # SHORT TERM
        # =====================

        else:

            memory["short_term"].append({

                "role": "user",

                "content": user_msg
            })

        # =====================
        # IMPORTANCE TRACKING
        # =====================

        memory["importance"].append({

            "text": user_msg,

            "score": score,

            "emotion": emotion,

            "sentiment": sentiment
        })

        # =====================
        # EMBEDDINGS
        # =====================

        embedding = get_embedding(user_msg)

        memory["embeddings"].append({

            "text": user_msg,

            "vector": embedding,

            "importance": score
        })

        # =====================
        # PROFILE UPDATE
        # =====================

        _update_profile(
            user_msg,
            memory
        )

        # =====================
        # LIMITS
        # =====================

        memory["short_term"] = (
            memory["short_term"][-MAX_SHORT_TERM:]
        )

        memory["long_term"] = (
            memory["long_term"][-MAX_LONG_TERM:]
        )

        memory["episodic"] = (
            memory["episodic"][-MAX_EPISODIC:]
        )

        memory["importance"] = (
            memory["importance"][-MAX_IMPORTANCE:]
        )

        memory["embeddings"] = (
            memory["embeddings"][-MAX_EMBEDDINGS:]
        )

        # =====================
        # SUMMARY
        # =====================

        memory = summarize_memory(memory)

        return memory

    except Exception as e:

        logger.error(f"Update memory error: {e}")

        return memory