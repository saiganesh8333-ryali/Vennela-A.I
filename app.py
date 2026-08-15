"""
Vennela AI - FastAPI Web Server
Lightweight deployment with all heavyweight modules replaced.

This is the main entry point for Render deployment.
"""

import os
import sys
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

# =========================
# CONFIGURATION
# =========================

# Enable lightweight mode FIRST - before any other imports
LIGHTWEIGHT_MODE = os.getenv('LIGHTWEIGHT_MODE', 'true').lower() == 'true'

if LIGHTWEIGHT_MODE:
    try:
        import lightweight_redirect  # Patches all imports
        print("✓ Lightweight mode enabled - heavy libraries redirected")
    except ImportError as e:
        print(f"Warning: Could not enable lightweight mode: {e}")

# Now safe to import the rest
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="Vennela AI",
    description="Adaptive AI with lightweight deployment",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# REQUEST/RESPONSE MODELS
# =========================

class EmbeddingRequest(BaseModel):
    text: str
    model: Optional[str] = "all-MiniLM-L6-v2"


class EmbeddingResponse(BaseModel):
    embedding: List[float]
    model: str
    dimension: int


class EmotionRequest(BaseModel):
    text: str


class EmotionResponse(BaseModel):
    emotions: Dict[str, float]
    dominant_emotion: str
    confidence: float


class SentimentRequest(BaseModel):
    text: str


class SentimentResponse(BaseModel):
    sentiment: str
    confidence: float
    details: Dict[str, float]


class IntentRequest(BaseModel):
    text: str


class IntentResponse(BaseModel):
    intent: str
    confidence: float
    all_intents: Dict[str, float]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


# =========================
# ROUTES
# =========================

@app.get("/", tags=["health"])
async def root():
    """Root endpoint - health check."""
    return {
        "status": "ok",
        "app": "Vennela AI",
        "lightweight_mode": LIGHTWEIGHT_MODE,
        "version": "1.0.0"
    }


@app.get("/health", tags=["health"])
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "lightweight_mode": LIGHTWEIGHT_MODE}


@app.post("/embed", response_model=EmbeddingResponse, tags=["embeddings"])
async def embed_text(request: EmbeddingRequest):
    """Generate semantic embedding for text."""
    try:
        from lightweight_embeddings import get_embedding
        
        embedding = get_embedding(request.text, request.model)
        
        return EmbeddingResponse(
            embedding=embedding.tolist(),
            model=request.model,
            dimension=len(embedding)
        )
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emotion", response_model=EmotionResponse, tags=["nlp"])
async def detect_emotion(request: EmotionRequest):
    """Detect emotion in text."""
    try:
        from lightweight_nlp import classify_emotion
        
        emotions = classify_emotion(request.text)
        dominant = max(emotions.items(), key=lambda x: x[1]) if emotions else ("neutral", 0.0)
        
        return EmotionResponse(
            emotions=emotions,
            dominant_emotion=dominant[0],
            confidence=dominant[1]
        )
    except Exception as e:
        logger.error(f"Emotion detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sentiment", response_model=SentimentResponse, tags=["nlp"])
async def analyze_sentiment(request: SentimentRequest):
    """Analyze sentiment of text."""
    try:
        from lightweight_nlp import analyze_sentiment
        
        sentiments = analyze_sentiment(request.text)
        sentiment_label = max(sentiments.items(), key=lambda x: x[1])[0] if sentiments else "NEUTRAL"
        
        return SentimentResponse(
            sentiment=sentiment_label,
            confidence=sentiments.get(sentiment_label, 0.5),
            details=sentiments
        )
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/intent", response_model=IntentResponse, tags=["nlp"])
async def classify_intent(request: IntentRequest):
    """Classify intent of user input."""
    try:
        from lightweight_nlp import classify_intent
        
        intents = classify_intent(request.text)
        top_intent = max(intents.items(), key=lambda x: x[1]) if intents else ("statement", 0.5)
        
        return IntentResponse(
            intent=top_intent[0],
            confidence=top_intent[1],
            all_intents=intents
        )
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process", tags=["nlp"])
async def process_text(request: Dict[str, Any]):
    """Process text - run all NLP tasks."""
    try:
        text = request.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="text field required")
        
        from lightweight_embeddings import get_embedding
        from lightweight_nlp import classify_emotion, analyze_sentiment, classify_intent
        
        # Run all tasks
        embedding = get_embedding(text)
        emotions = classify_emotion(text)
        sentiments = analyze_sentiment(text)
        intents = classify_intent(text)
        
        return {
            "text": text,
            "embedding": {
                "vector": embedding.tolist()[:10],  # First 10 dims
                "dimension": len(embedding)
            },
            "emotion": max(emotions.items(), key=lambda x: x[1]),
            "sentiment": max(sentiments.items(), key=lambda x: x[1]),
            "intent": max(intents.items(), key=lambda x: x[1]),
            "all_emotions": emotions,
            "all_sentiments": sentiments,
            "all_intents": intents
        }
    except Exception as e:
        logger.error(f"Process error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest):
    """Chat with Gemini AI."""
    try:
        import google.generativeai as genai
        import time as _time

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")

        genai.configure(api_key=api_key)

        # Read personality from environment (keep existing prompts unchanged)
        VENNELA_PERSONALITY = os.getenv("VENNELA_PERSONALITY", "")
        # Read existing prompts if provided via environment (do not modify them)
        VENNELA_PROMPT = os.getenv("VENNELA_PROMPT", "")
        SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

        # Prefer VENNELA_PROMPT if present, otherwise SYSTEM_PROMPT
        base_system = VENNELA_PROMPT or SYSTEM_PROMPT or ""

        # Combine base system instruction with personality (if any)
        combined_system_instruction = "\n\n".join([s for s in (base_system, VENNELA_PERSONALITY) if s])

        # Centralized model chain obtained from gemini_config (env override supported)
        try:
            from gemini_config import get_gemini_model_chain
            model_chain = get_gemini_model_chain()
        except Exception:
            # Fallback to single-model chain using the currently configured primary model
            model_chain = ["gemini-3.5-flash"]
            logger.warning("[Gemini] Could not load centralized GEMINI_MODEL_CHAIN; using default single primary model")

        # Use centralized fallback helper
        from gemini_fallback import call_gemini_with_fallback, GeminiFallbackError

        GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
        GEMINI_BACKOFF_BASE = float(os.getenv("GEMINI_BACKOFF_BASE", "0.5"))

        try:
            response = call_gemini_with_fallback(
                genai,
                request.message,
                system_instruction=combined_system_instruction,
                model_chain=model_chain,
                preferred_first=None,
                max_retries=GEMINI_MAX_RETRIES,
                backoff_base=GEMINI_BACKOFF_BASE,
            )

            # response is the SDK response object; return text if present
            text = getattr(response, 'text', None)
            if text is None:
                # Some SDK variants put content differently
                text = str(response)

            return ChatResponse(response=text)

        except HTTPException:
            raise
        except GeminiFallbackError as gf:
            logger.error(f"[Gemini] All configured models failed: {gf}")
            raise HTTPException(status_code=503, detail="AI services temporarily unavailable. Please try again later.")
        except Exception as e:
            # Permanent errors will surface here; map to clean client-facing errors
            logger.error(f"Chat error: {e}")
            status = getattr(e, 'status_code', None) or getattr(e, 'code', None) or None
            # Map explicit authentication/invalid-key messages to 401 so callers see auth failure
            msg = str(e).lower() if e is not None else ''
            if status == 401 or any(token in msg for token in ("invalid api key", "invalidapikey", "unauthorized", "authentication", "invalid api", "invalid auth")):
                raise HTTPException(status_code=401, detail="Gemini authentication failed")
            # Generic internal error
            raise HTTPException(status_code=500, detail="Internal AI error")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        # Do not include provider raw error text in HTTP response
        raise HTTPException(status_code=500, detail="Internal AI error")

@app.get("/status", tags=["health"])
async def status():
    """Get detailed status."""
    return {
        "status": "running",
        "lightweight_mode": LIGHTWEIGHT_MODE,
        "phases": "1-5 (All systems active)",
        "modules": {
            "embeddings": "lightweight_embeddings",
            "nlp": "lightweight_nlp",
            "ml": "lightweight_ml",
            "phase_4_proactive": "proactive_engine",
            "phase_5_autonomous": "autonomous_engine",
        },
        "size_reduction": "90% smaller than full deployment"
    }


# =========================
# PHASE 4 & 5 ENDPOINTS
# =========================

class ProactiveSuggestionRequest(BaseModel):
    topic: str
    current_intent: str
    user_patterns: Optional[Dict[str, Any]] = {}


class ProactiveSuggestionResponse(BaseModel):
    suggestions: List[Dict[str, Any]]
    count: int


@app.post("/phase4/suggestions", response_model=ProactiveSuggestionResponse, tags=["phase_4"])
async def get_proactive_suggestions(request: ProactiveSuggestionRequest):
    """Get proactive suggestions (Phase 4)"""
    try:
        from proactive_engine import get_proactive_engine
        
        engine = get_proactive_engine()
        suggestions = engine.get_proactive_suggestions(
            request.topic,
            request.current_intent,
            request.user_patterns or {}
        )
        
        return ProactiveSuggestionResponse(
            suggestions=suggestions,
            count=len(suggestions)
        )
    except Exception as e:
        logger.error(f"Proactive suggestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class GoalCreationRequest(BaseModel):
    title: str
    description: str
    target_days: Optional[int] = 30
    user_patterns: Optional[Dict[str, Any]] = {}


class GoalCreationResponse(BaseModel):
    goal_id: str
    goal: Dict[str, Any]
    plan: Dict[str, Any]


@app.post("/phase5/goal", response_model=GoalCreationResponse, tags=["phase_5"])
async def create_goal_with_plan(request: GoalCreationRequest):
    """Create goal with autonomous action plan (Phase 5)"""
    try:
        from autonomous_engine import get_autonomous_engine
        
        engine = get_autonomous_engine()
        plan = engine.create_and_plan_goal(
            request.title,
            request.description,
            request.user_patterns or {},
            request.target_days
        )
        
        return GoalCreationResponse(
            goal_id=plan["goal_id"],
            goal=plan["goal"],
            plan=plan["plan"]
        )
    except Exception as e:
        logger.error(f"Goal creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ActionRecommendationRequest(BaseModel):
    goal_id: str


class ActionRecommendationResponse(BaseModel):
    action: Optional[Dict[str, Any]]
    message: str


@app.post("/phase5/action", response_model=ActionRecommendationResponse, tags=["phase_5"])
async def get_next_action(request: ActionRecommendationRequest):
    """Get next recommended action for goal (Phase 5)"""
    try:
        from autonomous_engine import get_autonomous_engine
        
        engine = get_autonomous_engine()
        action = engine.get_recommended_action(request.goal_id)
        
        if action:
            return ActionRecommendationResponse(
                action=action,
                message="Next action ready. User approval required."
            )
        else:
            return ActionRecommendationResponse(
                action=None,
                message="All actions completed or goal not found"
            )
    except Exception as e:
        logger.error(f"Action recommendation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ERROR HANDLERS
# =========================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return {
        "error": str(exc),
        "type": type(exc).__name__
    }


# =========================
# STARTUP/SHUTDOWN
# =========================

@app.on_event("startup")
async def startup_event():
    """Run on startup."""
    logger.info("Vennela AI starting up...")
    logger.info(f"Lightweight mode: {LIGHTWEIGHT_MODE}")
    logger.info(f"Python runtime: {sys.version.split()[0]}")
    print("SERVER STARTED OK")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on shutdown."""
    logger.info("Vennela AI shutting down...")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
