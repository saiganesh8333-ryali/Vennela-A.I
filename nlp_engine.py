"""Lightweight NLP utilities for intent, sentiment, and emotion detection."""
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

ENABLE_TRANSFORMER_NLP = os.getenv("VENNELA_ENABLE_TRANSFORMER_NLP", "false").lower() == "true"

_emotion_model = None
_sentiment_model = None


INTENT_PATTERNS = {
    "greeting": [
        r"\b(hi|hello|hey|namaste|namaskaram|yo)\b",
        r"\b(good morning|good afternoon|good evening)\b",
    ],
    "identity": [
        r"\b(who are you|what are you|nee peru enti|nuvvu evaru)\b",
    ],
    "thanks": [
        r"\b(thanks|thank you|tq|dhanyavad|super thanks)\b",
    ],
    "help": [
        r"\b(help|what can you do|commands|how to use|emi cheyagalavu)\b",
    ],
    "status": [
        r"\b(status|health|are you working|backend working|server ok)\b",
    ],
    "memory_query": [
        r"\b(what do you remember|na gurinchi|my memory|remember about me)\b",
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text for cheap NLP rules."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def detect_intent(text: str) -> str:
    """Detect a simple user intent with regex rules."""
    normalized = normalize_text(text)
    if not normalized:
        return "unknown"

    for intent, patterns in INTENT_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            return intent

    if normalized.endswith("?"):
        return "question"

    return "chat"


def get_rule_based_reply(
    intent: str,
    user_message: str,
    memory: Optional[Dict] = None,
    relevant_memory: Optional[str] = None,
) -> Optional[str]:
    """Return a local reply for intents that do not need an AI provider."""
    memory = memory or {}
    profile = memory.get("profile", {}) or {}
    name = profile.get("preferred_name") or profile.get("name")
    address = f", {name}" if name else ""

    replies = {
        "greeting": f"Hi{address}! Vennela ready. Cheppu, em kavali?",
        "identity": "Nenu Vennela AI, nee lightweight memory assistant. Fast replies, memory, and AI fallback tho help chestha.",
        "thanks": f"Always{address}. Happy to help.",
        "help": (
            "Nenu chat, memory, project help, code guidance, and quick status checks cheyagalanu. "
            "Simple queries ki local fast reply, deeper questions ki AI fallback use chestha."
        ),
        "status": "Backend alive. Lightweight NLP layer active, Firebase/AI provider status kosam /health and /ai-health check cheyyi.",
    }

    if intent == "memory_query":
        summary = memory.get("summary") or "Inka strong long-term memory build avvaledu."
        if relevant_memory:
            return f"Naaku gurthunna relevant point: {relevant_memory}\n\nOverall memory: {summary}"
        return f"Overall memory: {summary}"

    return replies.get(intent)


def _load_emotion_model():
    """Load optional transformer emotion model only when explicitly enabled."""
    global _emotion_model

    if not ENABLE_TRANSFORMER_NLP:
        return None
    if _emotion_model is not None:
        return _emotion_model

    try:
        from transformers import pipeline

        logger.info("Loading optional transformer emotion model...")
        _emotion_model = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,
            device=-1,
        )
        return _emotion_model
    except Exception as e:
        logger.warning(f"Failed to load emotion model: {e}. Using keyword fallback.")
        return None


def _load_sentiment_model():
    """Load optional transformer sentiment model only when explicitly enabled."""
    global _sentiment_model

    if not ENABLE_TRANSFORMER_NLP:
        return None
    if _sentiment_model is not None:
        return _sentiment_model

    try:
        from transformers import pipeline

        logger.info("Loading optional transformer sentiment model...")
        _sentiment_model = pipeline(
            "sentiment-analysis",
            model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
            device=-1,
        )
        return _sentiment_model
    except Exception as e:
        logger.warning(f"Failed to load sentiment model: {e}. Using keyword fallback.")
        return None


def _fallback_emotion(text: str) -> str:
    """Detect emotion with a tiny keyword lexicon."""
    text = normalize_text(text)

    emotions = {
        "joy": ["happy", "great", "love", "good", "awesome", "excited", "wonderful", "super", "nice"],
        "sadness": ["sad", "depressed", "bad", "terrible", "awful", "miserable", "hurt"],
        "anger": ["angry", "mad", "furious", "irritated", "frustrated"],
        "fear": ["scared", "afraid", "worried", "anxious", "nervous", "tension"],
        "surprise": ["surprised", "shocked", "amazed", "wow"],
    }

    for emotion, keywords in emotions.items():
        if any(keyword in text for keyword in keywords):
            return emotion

    return "neutral"


def _fallback_sentiment(text: str) -> str:
    """Detect sentiment with a tiny keyword lexicon."""
    text = normalize_text(text)

    positive = ["happy", "great", "love", "good", "awesome", "excited", "wonderful", "super", "nice", "thanks"]
    negative = ["sad", "bad", "angry", "hate", "problem", "stuck", "worried", "awful", "error", "failed"]

    if any(word in text for word in positive):
        return "POSITIVE"
    if any(word in text for word in negative):
        return "NEGATIVE"
    return "NEUTRAL"


def detect_emotion(text: str) -> str:
    """Detect emotion from text using optional transformer or keyword fallback."""
    if not text or not isinstance(text, str):
        return "neutral"

    try:
        model = _load_emotion_model()
        if model is None:
            return _fallback_emotion(text)

        result = model(text[:512])
        while result and isinstance(result[0], list):
            result = result[0]

        if result:
            return max(result, key=lambda item: item["score"])["label"]
    except Exception as e:
        logger.error(f"Error detecting emotion: {e}")

    return _fallback_emotion(text)


def detect_sentiment(text: str) -> str:
    """Detect sentiment from text using optional transformer or keyword fallback."""
    if not text or not isinstance(text, str):
        return "NEUTRAL"

    try:
        model = _load_sentiment_model()
        if model is None:
            return _fallback_sentiment(text)

        result = model(text[:512])
        if result:
            return result[0]["label"]
    except Exception as e:
        logger.error(f"Error detecting sentiment: {e}")

    return _fallback_sentiment(text)
