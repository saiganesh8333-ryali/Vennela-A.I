"""Smart memory engine with short-term, long-term, emotion and semantic storage."""
import logging
import re
from typing import Dict, List, Optional

from embedding_engine import get_embedding
from firebase_db import get_db
from nlp_engine import detect_emotion, detect_sentiment

logger = logging.getLogger(__name__)

# =========================
# CONSTANTS
# =========================
MAX_SHORT_TERM = 30
MAX_LONG_TERM = 100
MAX_IMPORTANCE = 100
MAX_EMBEDDINGS = 200
MAX_MESSAGE_LENGTH = 5000


# =========================
# MEMORY SCHEMA
# =========================
def _default_memory() -> Dict:
    """Get default memory structure."""
    return {
        "profile": {},
        "short_term": [],
        "long_term": [],
        "emotions": {},
        "sentiments": {},
        "importance": [],
        "summary": "",
        "embeddings": []
    }


def _normalize_memory(data: Optional[Dict]) -> Dict:
    """
    Normalize and validate memory data with backward compatibility.
    
    Args:
        data: Raw memory data from Firestore
        
    Returns:
        Normalized memory dictionary
    """
    if not data or not isinstance(data, dict):
        return _default_memory()
    
    memory = _default_memory()
    
    try:
        memory["profile"] = data.get("profile", {}) or {}
        memory["short_term"] = data.get("short_term", []) or []
        memory["long_term"] = data.get("long_term", []) or data.get("facts", []) or []
        memory["emotions"] = data.get("emotions", {}) or data.get("emotional_state", {}) or {}
        memory["sentiments"] = data.get("sentiments", {}) or {}
        memory["importance"] = data.get("importance", []) or data.get("importance_index", []) or []
        memory["summary"] = data.get("summary", "") or ""
        memory["embeddings"] = data.get("embeddings", []) or []
        
        # Handle legacy vector_memory format
        if not memory["embeddings"] and data.get("vector_memory"):
            memory["embeddings"] = [
                {"text": item.get("text", ""), "vector": item.get("vector", [])}
                for item in data.get("vector_memory", [])
                if item.get("text")
            ]
        
        return memory
    except Exception as e:
        logger.error(f"Error normalizing memory: {e}")
        return _default_memory()


# =========================
# MEMORY OPERATIONS
# =========================
def get_memory(user_id: str) -> Dict:
    """
    Load user memory from Firestore.
    
    Args:
        user_id: User identifier
        
    Returns:
        Normalized memory dictionary
    """
    if not user_id or not isinstance(user_id, str):
        logger.error(f"Invalid user_id: {user_id}")
        return _default_memory()
    
    try:
        db = get_db()
        if not db:
            logger.error("Database connection failed")
            return _default_memory()
        
        doc = db.collection("memory").document(user_id).get()
        memory = _normalize_memory(doc.to_dict() if doc.exists else {})
        logger.debug(f"Loaded memory for user {user_id}")
        return memory
        
    except Exception as e:
        logger.error(f"Error loading memory for {user_id}: {e}")
        return _default_memory()


def save_memory(user_id: str, data: Dict) -> bool:
    """
    Save user memory to Firestore.
    
    Args:
        user_id: User identifier
        data: Memory data to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not user_id or not isinstance(user_id, str):
        logger.error(f"Invalid user_id: {user_id}")
        return False
    
    if not data or not isinstance(data, dict):
        logger.error(f"Invalid memory data: {type(data)}")
        return False
    
    try:
        db = get_db()
        if not db:
            logger.error("Database connection failed")
            return False
        
        db.collection("memory").document(user_id).set(data, merge=True)
        logger.debug(f"Saved memory for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving memory for {user_id}: {e}")
        return False


# =========================
# IMPORTANCE SCORING
# =========================
def importance_score(text: str) -> int:
    """
    Calculate importance score for storing in long-term memory.
    
    Args:
        text: Input text to score
        
    Returns:
        int: Importance score (0-10)
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
        "remember": 5
    }
    
    for keyword, weight in keyword_weights.items():
        if keyword in text:
            score += weight
    
    if len(text) > 50:
        score += 1
    
    return min(score, 10)


def _append_unique(items: List, value: str) -> None:
    """
    Append value to list if not already present.
    
    Args:
        items: List to append to
        value: Value to append
    """
    clean_value = value.strip() if isinstance(value, str) else str(value)
    
    if clean_value and clean_value not in items:
        items.append(clean_value)


def _extract_phrase_after(text: str, marker: str) -> str:
    """
    Extract a phrase after a marker in text.
    
    Args:
        text: Text to search
        marker: Marker to find
        
    Returns:
        str: Extracted phrase or empty string
    """
    try:
        pattern = rf"{re.escape(marker)}\s+([a-zA-Z][a-zA-Z ]*)"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return ""
        
        phrase = match.group(1)
        phrase = re.split(r"\s+(?:and|but|because|so|then)\s+", phrase, maxsplit=1)[0]
        words = phrase.strip(" .,!?:;").split()
        
        return " ".join(words[:3])
    except Exception as e:
        logger.debug(f"Error extracting phrase: {e}")
        return ""


def _update_profile(user_message: str, memory: Dict) -> None:
    """
    Extract and update user profile from message.
    
    Args:
        user_message: User message to analyze
        memory: Memory dict to update
    """
    if not user_message or not isinstance(user_message, str):
        return
    
    try:
        profile = memory.setdefault("profile", {})
        lower_message = user_message.lower()
        
        if "my name is" in lower_message:
            name = _extract_phrase_after(user_message, "my name is")
            if name:
                profile["name"] = name.title()
        
        if "call me" in lower_message:
            preferred_name = _extract_phrase_after(user_message, "call me")
            if preferred_name:
                profile["preferred_name"] = preferred_name.title()
    
    except Exception as e:
        logger.error(f"Error updating profile: {e}")


def summarize_memory(memory: Dict) -> Dict:
    """
    Create a summary of important memory points.
    
    Args:
        memory: Memory dictionary
        
    Returns:
        Memory dict with updated summary
    """
    if not memory or not isinstance(memory, dict):
        return memory
    
    try:
        profile = memory.get("profile", {}) or {}
        long_term = memory.get("long_term", []) or []
        emotions = memory.get("emotions", {}) or {}
        sentiments = memory.get("sentiments", {}) or {}
        
        summary_parts = []
        
        if profile.get("name"):
            summary_parts.append(f"User name: {profile['name']}")
        
        if profile.get("preferred_name"):
            summary_parts.append(f"Preferred name: {profile['preferred_name']}")
        
        if emotions:
            main_emotion = max(emotions, key=emotions.get)
            summary_parts.append(f"Main emotional trend: {main_emotion}")
        
        if sentiments:
            main_sentiment = max(sentiments, key=sentiments.get)
            summary_parts.append(f"Main sentiment trend: {main_sentiment}")
        
        summary_parts.extend(long_term[-10:])
        memory["summary"] = " | ".join(summary_parts[:20])  # Limit summary length
        
        return memory
    except Exception as e:
        logger.error(f"Error summarizing memory: {e}")
        return memory


# =========================
# MEMORY UPDATE ENGINE
# =========================
def update_memory(
    user_id: str,
    user_msg: str,
    ai_reply: str,
    memory: Dict
) -> Dict:
    """
    Update memory with new interaction data.
    
    Args:
        user_id: User identifier
        user_msg: User message
        ai_reply: AI response
        memory: Current memory dictionary
        
    Returns:
        Updated memory dictionary
    """
    if not user_msg or not isinstance(user_msg, str):
        logger.warning("Invalid user message for memory update")
        return memory
    
    memory = _normalize_memory(memory)
    
    # Truncate very long messages
    user_msg = user_msg[:MAX_MESSAGE_LENGTH]
    
    try:
        # Detect emotion and sentiment
        emotion = detect_emotion(user_msg)
        sentiment = detect_sentiment(user_msg)
        
        memory["emotions"][emotion] = memory["emotions"].get(emotion, 0) + 1
        memory["sentiments"][sentiment] = memory["sentiments"].get(sentiment, 0) + 1
        
        # Score importance and store accordingly
        score = importance_score(user_msg)
        if score > 5:
            _append_unique(memory["long_term"], user_msg)
        else:
            memory["short_term"].append({
                "role": "user",
                "content": user_msg
            })
        
        # Store importance record
        memory["importance"].append({
            "text": user_msg,
            "score": score,
            "emotion": emotion,
            "sentiment": sentiment
        })
        
        # Store embedding
        embedding = get_embedding(user_msg)
        memory["embeddings"].append({
            "text": user_msg,
            "vector": embedding,
            "importance": score,
            "emotion": emotion,
            "sentiment": sentiment
        })
        
        # Update profile
        _update_profile(user_msg, memory)
        
        # Maintain size limits
        memory["short_term"] = memory["short_term"][-MAX_SHORT_TERM:]
        memory["long_term"] = memory["long_term"][-MAX_LONG_TERM:]
        memory["importance"] = memory["importance"][-MAX_IMPORTANCE:]
        memory["embeddings"] = memory["embeddings"][-MAX_EMBEDDINGS:]
        
        # Generate summary
        memory = summarize_memory(memory)
        
        logger.debug(f"Updated memory for user {user_id}")
        return memory
        
    except Exception as e:
        logger.error(f"Error updating memory: {e}")
        return memory
