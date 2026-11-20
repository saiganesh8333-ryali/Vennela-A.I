"""ML Training - Phase 2 user profile trainer."""

import logging
from typing import Dict, List, Optional
import re
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


def extract_speaking_style(messages: List[str]) -> Dict:
    """
    Extract speaking style patterns from messages.
    
    Returns:
        Dict with formality, language patterns, abbreviations, emoji usage
    """
    if not messages or not isinstance(messages, list):
        return {"formality": 0.5, "language_patterns": {}, "abbreviations": [], "emoji_count": 0}
    
    try:
        style = {
            "formality": 0.5,
            "language_patterns": defaultdict(int),
            "abbreviations": [],
            "emoji_count": 0,
            "punctuation_patterns": defaultdict(int),
            "avg_word_length": 0.0,
            "avg_sentence_length": 0.0
        }
        
        all_text = " ".join(messages)
        
        # Formality analysis
        formal_indicators = ["therefore", "furthermore", "however", "please", "sincerely", "regards"]
        casual_indicators = ["lol", "haha", "yeah", "gonna", "wanna", "can't", "don't"]
        
        formal_count = sum(all_text.lower().count(word) for word in formal_indicators)
        casual_count = sum(all_text.lower().count(word) for word in casual_indicators)
        
        total = formal_count + casual_count
        if total > 0:
            style["formality"] = formal_count / total
        
        # Abbreviations
        abbrev_pattern = r'\b[A-Z]{2,}\b'
        style["abbreviations"] = list(set(re.findall(abbrev_pattern, all_text)))
        
        # Emoji count
        emoji_pattern = r'[😀-🙏🌀-🗿]'
        style["emoji_count"] = len(re.findall(emoji_pattern, all_text))
        
        # Punctuation patterns
        for char in ['!', '?', '.', ',', ';']:
            style["punctuation_patterns"][char] = all_text.count(char)
        
        # Word length analysis
        words = all_text.split()
        if words:
            style["avg_word_length"] = sum(len(w) for w in words) / len(words)
            sentences = re.split(r'[.!?]+', all_text)
            sentences = [s.strip() for s in sentences if s.strip()]
            if sentences:
                style["avg_sentence_length"] = sum(len(s.split()) for s in sentences) / len(sentences)
        
        return dict(style)
    
    except Exception as e:
        logger.error(f"Error extracting speaking style: {e}")
        return {"formality": 0.5, "language_patterns": {}, "abbreviations": [], "emoji_count": 0}


def extract_preferred_responses(ai_responses: List[str], feedback_scores: List[float] = None) -> Dict:
    """
    Extract preferred response characteristics from highly-rated responses.
    
    Returns:
        Dict with length, tone, humor, detail_level preferences
    """
    if not ai_responses or not isinstance(ai_responses, list):
        return {"preferred_length": "medium", "tone": "neutral", "humor_level": 0.5, "detail_level": 0.5}
    
    try:
        feedback_scores = feedback_scores or [0.5] * len(ai_responses)
        
        preferences = {
            "preferred_length": "medium",
            "tone": "neutral",
            "humor_level": 0.5,
            "detail_level": 0.5,
            "avg_length": 0.0,
            "examples": []
        }
        
        # Weight by feedback score
        weighted_responses = [
            (resp, score) for resp, score in zip(ai_responses, feedback_scores) if score > 0.3
        ]
        
        if not weighted_responses:
            return preferences
        
        lengths = []
        for resp, score in weighted_responses:
            length = len(resp)
            lengths.append(length)
            
            # Humor detection (exclamations, emojis, jokes)
            humor_indicators = resp.count('!') + resp.count('😄') + resp.count(':)')
            
            # Detail level (complexity)
            complexity = len(re.findall(r'\b(?:however|therefore|moreover|consequently)\b', resp.lower()))
        
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            if avg_len < 100:
                preferences["preferred_length"] = "concise"
            elif avg_len > 500:
                preferences["preferred_length"] = "detailed"
            else:
                preferences["preferred_length"] = "medium"
            
            preferences["avg_length"] = avg_len
        
        # Humor level from emoji and exclamation patterns
        total_humor = 0
        for resp, score in weighted_responses:
            humor = (resp.count('!') + resp.count('😄') + resp.count(':)')) / max(len(resp), 1) * 100
            total_humor += humor
        
        if weighted_responses:
            preferences["humor_level"] = min(1.0, total_humor / len(weighted_responses) / 10)
        
        preferences["examples"] = [resp for resp, _ in weighted_responses[:3]]
        
        return preferences
    
    except Exception as e:
        logger.error(f"Error extracting preferred responses: {e}")
        return {"preferred_length": "medium", "tone": "neutral", "humor_level": 0.5, "detail_level": 0.5}


def extract_emotional_patterns(messages: List[str], emotions: Dict = None) -> Dict:
    """
    Extract emotional triggers and sensitivities.
    
    Returns:
        Dict with triggers, sensitivities, mood_cycles
    """
    if not messages or not isinstance(messages, list):
        return {"triggers": {}, "sensitivities": [], "mood_cycles": {}, "avg_sentiment": 0.0}
    
    try:
        emotions = emotions or {}
        
        patterns = {
            "triggers": defaultdict(int),
            "sensitivities": [],
            "mood_cycles": {},
            "avg_sentiment": 0.0,
            "emotional_keywords": defaultdict(int)
        }
        
        # Emotional keyword detection
        emotional_keywords = {
            "happy": ["happy", "great", "wonderful", "fantastic", "love"],
            "sad": ["sad", "upset", "terrible", "hate", "disappointed"],
            "angry": ["angry", "frustrated", "furious", "annoyed", "mad"],
            "anxious": ["worried", "anxious", "stressed", "nervous", "concerned"]
        }
        
        for emotion, keywords in emotional_keywords.items():
            count = 0
            for msg in messages:
                count += sum(msg.lower().count(kw) for kw in keywords)
            if count > 0:
                patterns["emotional_keywords"][emotion] = count
        
        # Sensitivity detection
        sensitive_topics = ["health", "money", "relationship", "family", "work", "death", "illness"]
        for msg in messages:
            for topic in sensitive_topics:
                if topic in msg.lower():
                    patterns["sensitivities"].append(topic)
        
        patterns["sensitivities"] = list(set(patterns["sensitivities"]))
        
        # Mood from emotions dict
        if emotions:
            patterns["avg_sentiment"] = sum(emotions.values()) / len(emotions) if emotions else 0.0
        
        return dict(patterns)
    
    except Exception as e:
        logger.error(f"Error extracting emotional patterns: {e}")
        return {"triggers": {}, "sensitivities": [], "mood_cycles": {}, "avg_sentiment": 0.0}


def extract_routines(messages: List[str], timestamps: List[str] = None) -> Dict:
    """
    Extract time patterns, recurring tasks, favorite topics.
    
    Returns:
        Dict with time_patterns, recurring_tasks, favorite_topics
    """
    if not messages or not isinstance(messages, list):
        return {"time_patterns": {}, "recurring_tasks": [], "favorite_topics": []}
    
    try:
        routines = {
            "time_patterns": {},
            "recurring_tasks": [],
            "favorite_topics": [],
            "message_frequency": 0.0
        }
        
        # Topic extraction (most common words)
        all_words = " ".join(messages).lower().split()
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
        
        topic_words = [w.strip('.,!?;:') for w in all_words if w not in stop_words and len(w) > 3]
        word_freq = Counter(topic_words)
        
        favorite_topics = [word for word, _ in word_freq.most_common(5)]
        routines["favorite_topics"] = favorite_topics
        
        # Recurring task detection
        recurring_keywords = ["every", "daily", "weekly", "monthly", "usually", "always", "often"]
        for msg in messages:
            lower_msg = msg.lower()
            for keyword in recurring_keywords:
                if keyword in lower_msg:
                    routines["recurring_tasks"].append(msg[:100])
        
        # Message frequency
        routines["message_frequency"] = len(messages)
        
        return routines
    
    except Exception as e:
        logger.error(f"Error extracting routines: {e}")
        return {"time_patterns": {}, "recurring_tasks": [], "favorite_topics": []}


def train_user_profile(user_memory: Dict, feedback_scores: List[float] = None) -> Dict:
    """
    Orchestrate profile training from all sources.
    
    Args:
        user_memory: Loaded user memory
        feedback_scores: Optional reinforcement scores
    
    Returns:
        Complete user profile
    """
    if not user_memory or not isinstance(user_memory, dict):
        return {"speaking_style": {}, "preferred_responses": {}, "emotional_patterns": {}, "routines": {}}
    
    try:
        # Extract messages from short_term and long_term
        short_term = user_memory.get("short_term", [])
        long_term = user_memory.get("long_term", [])
        
        user_messages = [
            msg.get("content", msg) if isinstance(msg, dict) else msg
            for msg in short_term + long_term
        ]
        
        profile = {
            "speaking_style": extract_speaking_style(user_messages),
            "preferred_responses": extract_preferred_responses(user_messages, feedback_scores),
            "emotional_patterns": extract_emotional_patterns(user_messages, user_memory.get("emotions")),
            "routines": extract_routines(user_messages),
            "profile_info": user_memory.get("profile", {}),
            "embeddings_summary": {
                "total_embeddings": len(user_memory.get("embeddings", [])),
                "avg_importance": sum(e.get("importance", 0) for e in user_memory.get("embeddings", [])) / max(len(user_memory.get("embeddings", [])), 1)
            }
        }
        
        logger.debug("User profile trained successfully")
        return profile
    
    except Exception as e:
        logger.error(f"Error training user profile: {e}")
        return {"speaking_style": {}, "preferred_responses": {}, "emotional_patterns": {}, "routines": {}}
