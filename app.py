"""
Vennela AI - FastAPI Web Server
Lightweight deployment with all heavyweight modules replaced.

This is the main entry point for Render deployment.
"""

import os
import sys
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

try:
    from llm_router.adapter import VennelaLLMAdapter
    from llm_router.contracts import RoutingError, FailureKind
    from conversation.response_policy import ConversationAdjuster
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False
    VennelaLLMAdapter = None
    RoutingError = Exception
    FailureKind = None
    ConversationAdjuster = None

_llm_adapter_instance: Optional[Any] = None
_conversation_adjuster_instance: Optional[Any] = None


def get_llm_adapter() -> Any:
    global _llm_adapter_instance
    if _llm_adapter_instance is None:
        if not ROUTER_AVAILABLE or VennelaLLMAdapter is None:
            raise RuntimeError("LLM Router subsystem is not available")
        _llm_adapter_instance = VennelaLLMAdapter()
    return _llm_adapter_instance


def get_conversation_adjuster() -> Any:
    global _conversation_adjuster_instance
    if _conversation_adjuster_instance is None:
        if not ROUTER_AVAILABLE or ConversationAdjuster is None:
            raise RuntimeError("ConversationAdjuster is not available")
        _conversation_adjuster_instance = ConversationAdjuster()
    return _conversation_adjuster_instance

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


def _basic_memory_context():
    """Build the single trusted Boss context from server configuration only."""
    from memory import AuthContext

    boss_id = os.getenv("VENNELA_BOSS_ID", "").strip()
    if not boss_id:
        raise RuntimeError("VENNELA_BOSS_ID is required for memory access")
    return AuthContext(user_id=boss_id, authenticated=True, session_id=None)


def _basic_memory_api():
    """Construct the production Basic Memory API lazily."""
    from supabase import create_client
    from memory import MemoryAPI, SupabaseMemoryRepository

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for memory access")
    return MemoryAPI(SupabaseMemoryRepository(create_client(url, key)))


def _memory_category(message: str):
    lower = message.lower()
    if "my name is" in lower or "call me" in lower:
        return "Profile"
    if "goal" in lower or "i want" in lower:
        return "Goal"
    if "project" in lower:
        return "Project"
    if "skill" in lower or "i can " in lower:
        return "Skill"
    if "i like" in lower or "i love" in lower or "favorite" in lower or "prefer" in lower:
        return "Preference"
    if "interested" in lower:
        return "Interest"
    return "Fact"


def _is_memory_eligible(message: str) -> bool:
    lower = message.lower()
    return any(marker in lower for marker in (
        "remember", "my name is", "call me", "favorite", "i like", "i love",
        "prefer", "my goal", "i want", "my project", "my skill", "i can ",
        "interested in",
    ))

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
    user_id: Optional[str] = None
    session_id: Optional[str] = None


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
async def chat(request: ChatRequest, http_request: Request):
    """Chat with Vennela AI via Conversation Adjuster and LLM Router."""
    try:
        # Memory is always scoped to the server-configured Boss identity.
        memory_api = None
        memory_context = None
        try:
            memory_context = _basic_memory_context()
            memory_api = _basic_memory_api()
            memories = memory_api.retrieve(
                memory_context, domain="boss_personal", query=request.message, limit=5
            )
        except Exception as memory_error:
            memories = []
            logger.warning("Basic memory load unavailable: %s", memory_error)

        retrieved_context = ""
        if memories:
            retrieved_context = "\n".join(
                f"- {item.content}" for item in memories if item.content
            )

        # Read personality from environment (keep existing prompts unchanged)
        VENNELA_PERSONALITY = os.getenv("VENNELA_PERSONALITY", "")
        # Read existing prompts if provided via environment (do not modify them)
        VENNELA_PROMPT = os.getenv("VENNELA_PROMPT", "")
        SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

        # Prefer VENNELA_PROMPT if present, otherwise SYSTEM_PROMPT
        base_system = VENNELA_PROMPT or SYSTEM_PROMPT or ""

        # Combine base system instruction with personality (if any)
        memory_instruction = (
            "Relevant durable user memories:\n" + retrieved_context
            if retrieved_context else ""
        )
        combined_system_instruction = "\n\n".join(
            s for s in (base_system, VENNELA_PERSONALITY, memory_instruction) if s
        )

        adjuster = get_conversation_adjuster()
        policy = adjuster.adjust(
            request.message,
            user_system_instruction=combined_system_instruction or None,
        )
        adapter = get_llm_adapter()

        try:
            result = adapter.route_text(
                request.message,
                system_instruction=policy.system_instruction,
                latency_sensitive=policy.latency_sensitive,
                max_tokens=policy.max_tokens,
                task_hint=policy.task_hint,
            )
            text = result.get("text", "")

            if memory_api is not None and memory_context is not None and _is_memory_eligible(request.message):
                stored_memory = memory_api.store(
                    memory_context,
                    request.message,
                    _memory_category(request.message),
                    domain="boss_personal",
                )
                if not stored_memory:
                    raise RuntimeError("Basic memory store returned no saved record")

            return ChatResponse(response=text)

        except RoutingError as exc:
            logger.error("[LLMRouter] Routing failure [%s]: %s", getattr(exc.failure, "kind", "ERROR"), exc)
            if FailureKind is not None and getattr(exc.failure, "kind", None) in {
                FailureKind.NO_API_KEY,
                FailureKind.AUTHENTICATION,
            }:
                raise HTTPException(status_code=401, detail=f"LLM authentication failed: {exc.failure.message}")
            raise HTTPException(status_code=503, detail="AI services temporarily unavailable. Please try again later.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Chat execution error: %s", e)
            raise HTTPException(status_code=500, detail="Internal AI error")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal AI error")


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest, http_request: Request):
    """Stream chat response via Conversation Adjuster and LLM Router."""
    try:
        retrieved_context = ""
        try:
            memory_context = _basic_memory_context()
            memory_api = _basic_memory_api()
            memories = memory_api.retrieve(
                memory_context, domain="boss_personal", query=request.message, limit=5
            )
            if memories:
                retrieved_context = "\n".join(
                    f"- {item.content}" for item in memories if item.content
                )
        except Exception as memory_error:
            logger.warning("Basic memory load unavailable: %s", memory_error)

        base_system = os.getenv("VENNELA_PROMPT", "") or os.getenv("SYSTEM_PROMPT", "")
        combined_system_instruction = "\n\n".join(
            s for s in (
                base_system,
                os.getenv("VENNELA_PERSONALITY", ""),
                "Relevant durable user memories:\n" + retrieved_context if retrieved_context else "",
            ) if s
        )
        policy = get_conversation_adjuster().adjust(
            request.message,
            user_system_instruction=combined_system_instruction or None,
        )
        adapter = get_llm_adapter()

        def token_generator():
            try:
                yield from adapter.stream_text(
                    request.message,
                    system_instruction=policy.system_instruction,
                    latency_sensitive=policy.latency_sensitive,
                    max_tokens=policy.max_tokens,
                )
            except Exception as exc:
                logger.error("[LLMRouter Stream] Error: %s", exc)
                yield "\n[AI stream error]"

        return StreamingResponse(token_generator(), media_type="text/plain; charset=utf-8")
    except Exception as exc:
        logger.error("Chat stream setup error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal AI error")


@app.get("/router/health", tags=["router"])
async def router_health():
    """Get diagnostic health and circuit breaker summary of LLM Router."""
    try:
        return get_llm_adapter().health_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/router/models", tags=["router"])
async def router_models():
    """List configured model profiles in LLM Router."""
    try:
        return get_llm_adapter().model_catalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/status", tags=["health"])
async def status():
    """Get detailed status."""
    router_status = "unavailable"
    health_info = {}
    try:
        health_info = get_llm_adapter().health_summary()
        router_status = "active"
    except Exception as exc:
        router_status = f"error: {exc}"

    return {
        "status": "running",
        "lightweight_mode": LIGHTWEIGHT_MODE,
        "phases": "1-5 (All systems active)",
        "router": {
            "status": router_status,
            "providers": health_info,
        },
        "modules": {
            "llm_router": "llm_router.adapter.VennelaLLMAdapter",
            "conversation_adjuster": "conversation.response_policy.ConversationAdjuster",
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
