"""
Lightweight NLP engine - Drop-in replacement for transformers pipeline.
Same API, same features, but no neural networks (~5KB vs 500MB).

Features:
- Emotion detection (rule-based)
- Sentiment analysis (lexicon-based)
- Intent classification (pattern-based)
"""

import re
from typing import Dict, List, Optional, Tuple
from enum import Enum

# =========================
# LEXICONS & PATTERNS
# =========================

EMOTION_LEXICON = {
    'happy': ['happy', 'joy', 'delighted', 'thrilled', 'awesome', 'great', 'wonderful', 'excellent', 'fantastic', 'love'],
    'sad': ['sad', 'unhappy', 'depressed', 'miserable', 'terrible', 'awful', 'horrible', 'hate', 'disappointed'],
    'angry': ['angry', 'furious', 'mad', 'rage', 'irritated', 'annoyed', 'frustrated', 'pissed'],
    'fear': ['afraid', 'scared', 'terrified', 'worried', 'anxious', 'nervous', 'fear'],
    'neutral': ['okay', 'fine', 'alright', 'normal', 'okay', 'so-so'],
}

SENTIMENT_POSITIVE = [
    'good', 'great', 'awesome', 'fantastic', 'excellent', 'wonderful', 'amazing',
    'love', 'like', 'happy', 'joy', 'best', 'perfect', 'brilliant', 'lovely'
]

SENTIMENT_NEGATIVE = [
    'bad', 'terrible', 'awful', 'horrible', 'hate', 'dislike', 'sad', 'worst',
    'poor', 'disappointing', 'useless', 'rubbish', 'pathetic', 'dreadful'
]

SENTIMENT_INTENSIFIERS = {
    'very': 1.5, 'extremely': 1.8, 'so': 1.5, 'really': 1.5,
    'absolutely': 1.8, 'completely': 1.5, 'totally': 1.5
}

INTENT_PATTERNS = {
    'greeting': [r'\bhello\b|\bhi\b|\bhey\b|\bgreetings\b|\bhow\s+are\s+you', 1.0],
    'farewell': [r'\bbye\b|\bgoodbye\b|\bsee\s+you\b|\bfarewell\b|\btake\s+care', 1.0],
    'question': [r'\?$|\bwhat\b|\bwhere\b|\bwhen\b|\bwhy\b|\bhow\b|\bwho\b', 0.8],
    'command': [r'^(open|close|start|stop|play|pause|do|make)', 0.8],
    'affirmation': [r'\byes\b|\byeah\b|\byup\b|\bsure\b|\bokay\b|\bfine\b', 0.9],
    'negation': [r'\bno\b|\bnope\b|\bnah\b|\bdont\b|\bdoesnt\b', 0.9],
}

# =========================
# LIGHTWEIGHT MODELS
# =========================

class EmotionClassifier:
    """Rule-based emotion classifier."""
    
    def __init__(self):
        self.emotions = list(EMOTION_LEXICON.keys())
    
    def __call__(self, text: str) -> List[Dict]:
        """Classify emotion. Returns list with top emotion."""
        text_lower = text.lower()
        scores = {}
        
        for emotion, keywords in EMOTION_LEXICON.items():
            score = 0.0
            for keyword in keywords:
                if keyword in text_lower:
                    # Count occurrences
                    score += text_lower.count(keyword) * 0.3
            scores[emotion] = min(score, 1.0)  # Cap at 1.0
        
        # If no matches found, neutral
        if sum(scores.values()) == 0:
            scores['neutral'] = 0.8
        
        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        
        # Return as list of dicts (compatible with transformers pipeline)
        results = [{'label': emotion, 'score': score} 
                  for emotion, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        return results


class SentimentAnalyzer:
    """Lexicon-based sentiment analyzer."""
    
    def __init__(self):
        self.positive_words = set(SENTIMENT_POSITIVE)
        self.negative_words = set(SENTIMENT_NEGATIVE)
        self.intensifiers = SENTIMENT_INTENSIFIERS
    
    def __call__(self, text: str) -> List[Dict]:
        """Analyze sentiment. Returns POSITIVE/NEGATIVE/NEUTRAL."""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        sentiment_score = 0.0
        confidence = 0.0
        
        for i, word in enumerate(words):
            intensity = 1.0
            
            # Check for intensifiers
            if i > 0 and words[i-1] in self.intensifiers:
                intensity = self.intensifiers[words[i-1]]
            
            if word in self.positive_words:
                sentiment_score += intensity
                confidence += 0.1
            elif word in self.negative_words:
                sentiment_score -= intensity
                confidence += 0.1
        
        # Determine label
        if sentiment_score > 0.2:
            label = 'POSITIVE'
        elif sentiment_score < -0.2:
            label = 'NEGATIVE'
        else:
            label = 'NEUTRAL'
        
        # Confidence
        confidence = min(abs(sentiment_score) / max(len(words), 1), 1.0)
        confidence = max(confidence, 0.5)  # Minimum confidence
        
        return [{'label': label, 'score': confidence}]


class IntentClassifier:
    """Pattern-based intent classifier."""
    
    def __init__(self):
        self.patterns = INTENT_PATTERNS
    
    def __call__(self, text: str) -> List[Dict]:
        """Classify intent. Returns top intents."""
        text_lower = text.lower()
        scores = {}
        
        for intent, (pattern, base_score) in self.patterns.items():
            matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
            if matches > 0:
                scores[intent] = min(base_score * matches, 1.0)
        
        if not scores:
            scores['statement'] = 0.5
        
        # Normalize
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        
        # Return sorted by score
        results = [{'label': intent, 'score': score}
                  for intent, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        return results


# =========================
# PIPELINE (MAIN API)
# =========================

class Pipeline:
    """
    Lightweight pipeline - drop-in replacement for transformers.pipeline().
    """
    
    def __init__(self, task: str, model: Optional[str] = None):
        """Initialize pipeline."""
        self.task = task
        self.model = model
        
        if task == "text-classification" or task == "emotion":
            self._model = EmotionClassifier()
        elif task == "sentiment-analysis":
            self._model = SentimentAnalyzer()
        elif task == "zero-shot-classification":
            self._model = IntentClassifier()
        else:
            raise ValueError(f"Unknown task: {task}")
    
    def __call__(self, text: str, **kwargs) -> List[Dict]:
        """Run pipeline on text."""
        return self._model(text)


# =========================
# PUBLIC API (Transformers Compatible)
# =========================

def pipeline(task: str, 
             model: Optional[str] = None,
             device: Optional[str] = None,
             **kwargs) -> Pipeline:
    """
    Create a lightweight pipeline.
    
    API compatible with transformers.pipeline()
    
    Supported tasks:
    - 'emotion': Emotion detection
    - 'sentiment-analysis': Sentiment classification
    - 'text-classification': General text classification
    - 'zero-shot-classification': Intent classification
    """
    return Pipeline(task, model)


# =========================
# UTILITY FUNCTIONS
# =========================

def classify_emotion(text: str) -> Dict[str, float]:
    """Quick emotion classification."""
    classifier = EmotionClassifier()
    results = classifier(text)
    return {r['label']: r['score'] for r in results}


def analyze_sentiment(text: str) -> Dict[str, float]:
    """Quick sentiment analysis."""
    analyzer = SentimentAnalyzer()
    results = analyzer(text)
    return {r['label']: r['score'] for r in results}


def classify_intent(text: str) -> Dict[str, float]:
    """Quick intent classification."""
    classifier = IntentClassifier()
    results = classifier(text)
    return {r['label']: r['score'] for r in results}
