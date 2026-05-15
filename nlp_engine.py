import logging
import os
from typing import Optional

os.environ.setdefault("HF_HOME", os.path.join(os.getcwd(), ".hf_cache"))
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(os.getcwd(), ".hf_cache", "transformers"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

logger = logging.getLogger(__name__)

_emotion_model = None
_sentiment_model = None


def _load_emotion_model():
    """Load lightweight emotion detection model with error handling."""
    global _emotion_model
    
    if _emotion_model is not None:
        return _emotion_model
    
    try:
        from transformers import pipeline
        logger.info("Loading lightweight emotion detection model...")
        # Using distilroberta: smaller and faster than full roberta
        _emotion_model = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,
            device=-1  # Use CPU for lighter memory footprint
        )
        # Apply quantization to reduce memory
        try:
            from transformers import AutoModelForSequenceClassification
            model = AutoModelForSequenceClassification.from_pretrained(
                "j-hartmann/emotion-english-distilroberta-base"
            )
            model.half()  # Convert to FP16
            _emotion_model.model = model
            logger.info("✅ Emotion model loaded with FP16 quantization")
        except:
            logger.info("✅ Emotion model loaded successfully")
        return _emotion_model
    except Exception as e:
        logger.warning(f"Failed to load emotion model: {e}. Using fallback.")
        return None


def _load_sentiment_model():
    """Load lightweight sentiment analysis model with error handling."""
    global _sentiment_model
    
    if _sentiment_model is not None:
        return _sentiment_model
    
    try:
        from transformers import pipeline
        logger.info("Loading lightweight sentiment analysis model...")
        _sentiment_model = pipeline(
            "sentiment-analysis",
            model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
            device=-1  # Use CPU for lighter memory footprint
        )
        # Apply quantization to reduce memory
        try:
            from transformers import AutoModelForSequenceClassification
            model = AutoModelForSequenceClassification.from_pretrained(
                "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
            )
            model.half()  # Convert to FP16
            _sentiment_model.model = model
            logger.info("✅ Sentiment model loaded with FP16 quantization")
        except:
            logger.info("✅ Sentiment model loaded successfully")
        return _sentiment_model
    except Exception as e:
        logger.warning(f"Failed to load sentiment model: {e}. Using fallback.")
        return None


def _fallback_emotion(text: str) -> str:
    """Fallback emotion detection using keyword matching."""
    text = text.lower()
    
    emotions = {
        "joy": ["happy", "great", "love", "good", "awesome", "excited", "wonderful", "fantastic"],
        "sadness": ["sad", "depressed", "bad", "terrible", "awful", "hate", "miserable"],
        "anger": ["angry", "mad", "furious", "rage", "irritated", "frustrated"],
        "fear": ["scared", "afraid", "worried", "anxious", "nervous", "terrified"],
        "surprise": ["surprised", "shocked", "amazed", "wow", "astonished"],
    }
    
    for emotion, keywords in emotions.items():
        if any(keyword in text for keyword in keywords):
            return emotion
    
    return "neutral"


def _fallback_sentiment(text: str) -> str:
    """Fallback sentiment detection using keyword matching."""
    text = text.lower()
    
    if any(word in text for word in ["happy", "great", "love", "good", "awesome", "excited", "wonderful"]):
        return "POSITIVE"
    
    if any(word in text for word in ["sad", "bad", "angry", "hate", "problem", "stuck", "worried", "awful"]):
        return "NEGATIVE"
    
    return "NEUTRAL"


def detect_emotion(text: str) -> str:
    """
    Detect emotion from text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        str: Detected emotion label (joy, sadness, anger, fear, surprise, neutral)
    """
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input for emotion detection: {type(text)}")
        return "neutral"
    
    try:
        model = _load_emotion_model()
        if model is None:
            return _fallback_emotion(text)
        
        result = model(text[:512])  # Truncate to 512 chars to avoid memory issues
        while result and isinstance(result[0], list):
            result = result[0]

        if result:
            return max(result, key=lambda item: item["score"])["label"]
    except Exception as e:
        logger.error(f"Error detecting emotion: {e}")
    
    return _fallback_emotion(text)


def detect_sentiment(text: str) -> str:
    """
    Detect sentiment from text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        str: Sentiment label (POSITIVE, NEGATIVE, NEUTRAL)
    """
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input for sentiment detection: {type(text)}")
        return "NEUTRAL"
    
    try:
        model = _load_sentiment_model()
        if model is None:
            return _fallback_sentiment(text)
        
        result = model(text[:512])  # Truncate to 512 chars
        if result:
            return result[0]["label"]
    except Exception as e:
        logger.error(f"Error detecting sentiment: {e}")
    
    return _fallback_sentiment(text)
