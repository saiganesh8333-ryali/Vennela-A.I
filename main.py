"""Vennela AI - Self-learning AI assistant with semantic memory and emotion detection."""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv
from firebase_admin import firestore

from firebase_db import get_db, initialize_firebase
from ai_router import get_ai_response
from smart_memory import get_memory, save_memory, update_memory
from retrieval import retrieve_memory
from nlp_engine import detect_intent, get_rule_based_reply

# =========================
# CONFIGURATION
# =========================
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vennela AI",
    description="Self-learning AI assistant with semantic memory",
    version="2.0.0"
)

# Prompt
VENNELA_PROMPT = os.getenv("VENNELA_PROMPT", """You are VENNELA AI.

Always respond directly to the user's question.
Do not greet repeatedly.
Do not say system online.
Do not repeat introductions.
Respond naturally.

Be helpful, thoughtful, and understand the user's underlying needs.""")

RECENT_CHAT_LIMIT = int(os.getenv("RECENT_CHAT_LIMIT", "20"))
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "5000"))
AI_UNAVAILABLE_REPLY = os.getenv(
    "AI_UNAVAILABLE_REPLY",
    "AI temporarily unavailable. Please try again in a moment."
)

# Rate limiting
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW_MINUTES = int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "1"))

# In-memory rate limiting tracker
_rate_limit_tracker: Dict[str, list] = {}


# =========================
# REQUEST MODELS
# =========================
class ChatRequest(BaseModel):
    """Chat request with validation."""
    user_id: str = Field(..., min_length=1, max_length=256, description="User ID")
    message: str = Field(..., min_length=1, max_length=5000, description="User message")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id format."""
        if not v or not isinstance(v, str):
            raise ValueError('user_id must be a non-empty string')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('user_id must contain only alphanumeric characters, underscores, and hyphens')
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        """Validate message content."""
        if not v or not isinstance(v, str):
            raise ValueError('message must be a non-empty string')
        v = v.strip()
        if len(v) == 0:
            raise ValueError('message cannot be empty after trimming whitespace')
        return v


class ChatResponse(BaseModel):
    """Chat response with metadata."""
    reply: str
    provider: str
    intent: Optional[str] = None
    relevant_memory: Optional[str] = None
    memory_summary: Optional[str] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


# =========================
# INITIALIZATION
# =========================
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Vennela AI...")
    
    try:
        # Initialize Firebase
        if not initialize_firebase():
            logger.warning("Firebase initialization failed. Using fallback mode.")
    except Exception as e:
        logger.error(f"Startup error during Firebase init: {e}", exc_info=True)
    
    try:
        # Verify environment
        groq_key = os.getenv("GROQ_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        if not groq_key and not openrouter_key:
            logger.warning("No AI provider keys found. Chat will use fallback.")
    except Exception as e:
        logger.error(f"Startup error during environment check: {e}", exc_info=True)
    
    logger.info("Vennela AI startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Vennela AI")


# =========================
# MIDDLEWARE
# =========================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    logger.debug(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.debug(f"Response: {response.status_code}")
    return response


# =========================
# BAD RESPONSE FILTERING
# =========================
BAD_PATTERNS = [
    "system online",
    "listening",
    "how can i assist",
    "i'm ready to help",
    "hello i am vennela",
    "i am vennela",
    "i'm vennela",
    "ready to help",
    "system is online"
]


def is_greeting_response(content: str) -> bool:
    """
    Check if response contains greeting/startup patterns.
    
    Args:
        content: Message content
        
    Returns:
        bool: True if contains bad patterns
    """
    lower_content = content.lower().strip()
    return any(pattern in lower_content for pattern in BAD_PATTERNS)


def filter_history(messages: list) -> list:
    """
    Remove messages with bad greeting patterns.
    
    Args:
        messages: List of message dicts
        
    Returns:
        Filtered list without bad patterns
    """
    filtered = []
    for msg in messages:
        if msg.get("role") == "system":
            filtered.append(msg)
            continue
        
        content = msg.get("content", "")
        if is_greeting_response(content):
            logger.debug(f"⚠️ Filtering out greeting response: {content[:50]}...")
            continue
        
        filtered.append(msg)
    
    return filtered


# =========================
# RATE LIMITING
# =========================
def check_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded rate limit.
    
    Args:
        user_id: User identifier
        
    Returns:
        bool: True if within limit, False if exceeded
    """
    now = datetime.now()
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    
    if user_id not in _rate_limit_tracker:
        _rate_limit_tracker[user_id] = []
    
    # Remove old requests outside window
    _rate_limit_tracker[user_id] = [
        req_time for req_time in _rate_limit_tracker[user_id]
        if req_time > window_start
    ]
    
    # Check limit
    if len(_rate_limit_tracker[user_id]) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return False
    
    # Add current request
    _rate_limit_tracker[user_id].append(now)
    return True


# =========================
# CHAT FUNCTIONS
# =========================
def save_message(user_id: str, role: str, content: str) -> bool:
    """
    Save message to Firestore (skip if greeting response).
    
    Args:
        user_id: User identifier
        role: Message role (user/assistant)
        content: Message content
        
    Returns:
        bool: True if successful
    """
    try:
        # Never save assistant greeting responses
        if role == "assistant" and is_greeting_response(content):
            logger.info(f"⏭️ Skipping greeting response: {content[:50]}...")
            return True
        
        db = get_db()
        if not db:
            logger.error("Database not available")
            return False
        
        db.collection("chat_memory") \
            .document(user_id) \
            .collection("messages") \
            .add({
                "role": role,
                "content": content[:5000],  # Truncate
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        return True
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return False


def format_smart_memory(
    memory: Dict,
    relevant_memory: Optional[str] = None
) -> str:
    """
    Format memory for AI context.
    
    Args:
        memory: Memory dictionary
        relevant_memory: Retrieved relevant memory
        
    Returns:
        str: Formatted memory for prompt
    """
    summary = memory.get("summary", "") or "No long-term memory yet."
    emotions = memory.get("emotions", {}) or {}
    sentiments = memory.get("sentiments", {}) or {}
    
    emotion_summary = ", ".join(f"{key}={value}" for key, value in emotions.items()) \
        if emotions else "No emotional trend yet."
    sentiment_summary = ", ".join(f"{key}={value}" for key, value in sentiments.items()) \
        if sentiments else "No sentiment trend yet."
    
    relevant_memory_str = relevant_memory or "No directly relevant memory found."
    
    system_content = f"""{VENNELA_PROMPT}

USER PROFILE:
{summary}

EMOTIONAL TRENDS:
{emotion_summary}

SENTIMENT TRENDS:
{sentiment_summary}

RELEVANT MEMORY FOR THIS MESSAGE:
{relevant_memory_str}"""
    
    return system_content


def load_messages(user_id: str, smart_memory: Dict, relevant_memory: Optional[str] = None) -> list:
    """
    Load recent chat history with smart memory context.
    Filters out greeting responses and limits to 6 messages.
    
    Args:
        user_id: User identifier
        smart_memory: Memory dictionary
        relevant_memory: Retrieved relevant memory
        
    Returns:
        List of message dicts for AI
    """
    try:
        db = get_db()
        if not db:
            logger.warning("Database not available - creating minimal context")
            messages = [
                {
                    "role": "system",
                    "content": format_smart_memory(smart_memory, relevant_memory)
                }
            ]
            return messages
        
        docs = db.collection("chat_memory") \
            .document(user_id) \
            .collection("messages") \
            .order_by("timestamp") \
            .stream()
        
        messages = [
            {
                "role": "system",
                "content": format_smart_memory(smart_memory, relevant_memory)
            }
        ]
        
        chat_history = list(docs)[-RECENT_CHAT_LIMIT:]
        
        for doc in chat_history:
            data = doc.to_dict()
            if data and "role" in data and "content" in data:
                messages.append({
                    "role": data["role"],
                    "content": data["content"]
                })
        
        # Filter out greeting responses from history
        messages = filter_history(messages)
        
        # Keep only system + last 6 messages to avoid old bad behavior
        system_msg = [msg for msg in messages if msg.get("role") == "system"]
        other_msgs = [msg for msg in messages if msg.get("role") != "system"]
        other_msgs = other_msgs[-6:]
        
        filtered_messages = system_msg + other_msgs
        
        logger.info(f"📋 Loaded {len(filtered_messages)} messages (system + {len(other_msgs)} history)")
        
        return filtered_messages
        
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        messages = [
            {
                "role": "system",
                "content": format_smart_memory(smart_memory, relevant_memory)
            }
        ]
        return messages


def _minimal_memory() -> Dict:
    """Return a safe empty memory object when memory services are unavailable."""
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


# =========================
# API ENDPOINTS
# =========================
@app.get("/")
async def root():
    """Root endpoint for quick deployment checks."""
    return {"message": "Vennela AI Running 🚀"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db = get_db()
    firebase_ok = db is not None
    
    return {
        "status": "ok",
        "firebase": "connected" if firebase_ok else "disconnected",
        "version": "2.0.0"
    }


@app.get("/ai-health")
async def ai_health_check():
    """
    Test both AI providers (Groq and OpenRouter) health status.
    
    Returns:
        Dict with provider health status
    """
    from openai import OpenAI
    
    result = {}
    
    # Test GROQ
    try:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            result["groq"] = "not_configured"
        else:
            groq_client = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=10
            )
            
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            
            result["groq"] = "healthy"
            logger.info("✅ Groq provider is healthy")
    except Exception as e:
        result["groq"] = f"failed: {str(e)}"
        logger.warning(f"⚠️ Groq health check failed: {e}")
    
    # Test OPENROUTER
    try:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_key:
            result["openrouter"] = "not_configured"
        else:
            openrouter_client = OpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=10
            )
            
            response = openrouter_client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            
            result["openrouter"] = "healthy"
            logger.info("✅ OpenRouter provider is healthy")
    except Exception as e:
        result["openrouter"] = f"failed: {str(e)}"
        logger.warning(f"⚠️ OpenRouter health check failed: {e}")
    
    return result


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process chat message with memory and AI response.
    
    Args:
        request: Chat request with user_id and message
        
    Returns:
        ChatResponse with reply and metadata
    """
    import time
    start_time = time.time()
    
    user_id = request.user_id
    user_message = request.message
    
    logger.info(f"Chat request from {user_id}: {len(user_message)} chars")
    
    try:
        # Check rate limit
        if not check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for {user_id}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW_MINUTES} minute(s)"
            )
        
        # Load memory, but keep chat alive if Firebase or memory retrieval fails.
        try:
            memory = get_memory(user_id)
        except Exception as e:
            logger.error(f"Memory load failed for {user_id}: {e}", exc_info=True)
            memory = _minimal_memory()

        try:
            relevant_memory = retrieve_memory(memory, user_message)
        except Exception as e:
            logger.error(f"Relevant memory retrieval failed for {user_id}: {e}", exc_info=True)
            relevant_memory = None

        intent = detect_intent(user_message)
        
        # Save user message
        save_message(user_id, "user", user_message)

        local_reply = get_rule_based_reply(intent, user_message, memory, relevant_memory)
        if local_reply:
            save_message(user_id, "assistant", local_reply)

            try:
                updated_memory = update_memory(user_id, user_message, local_reply, memory)
                save_memory(user_id, updated_memory)
            except Exception as e:
                logger.error(f"Memory update failed for {user_id}: {e}", exc_info=True)
                updated_memory = memory

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Local response sent ({intent}, {elapsed_ms}ms)")

            return ChatResponse(
                reply=local_reply,
                provider="local_rules",
                intent=intent,
                relevant_memory=relevant_memory,
                memory_summary=updated_memory.get("summary"),
                latency_ms=elapsed_ms
            )
        
        # Load recent chat with context
        messages = load_messages(user_id, memory, relevant_memory)
        
        if not messages or len(messages) < 1:
            logger.error(f"Failed to load chat messages for {user_id}")
            raise HTTPException(status_code=500, detail="Failed to load chat context")
        
        # DEBUG: Log message structure before sending to Groq
        logger.debug("=" * 60)
        logger.debug("🔍 DEBUG: Message structure before Groq call:")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]
            logger.debug(f"  [{i}] {role}: {content}...")
        logger.debug("=" * 60)
        
        logger.info(f"Chat context loaded with {len(messages)} messages")
        
        # Get AI response
        try:
            ai_result = get_ai_response(messages)
        except Exception as e:
            logger.error(f"AI provider call failed: {e}", exc_info=True)
            ai_result = {
                "provider": "error",
                "response": AI_UNAVAILABLE_REPLY,
                "error": str(e)
            }

        ai_reply = ai_result.get("response", "")
        provider = ai_result.get("provider", "unknown")
        
        if not ai_reply:
            logger.error("Empty response from AI provider")
            ai_reply = AI_UNAVAILABLE_REPLY
            provider = "error"
        
        # Save AI response (filtered in save_message)
        save_message(user_id, "assistant", ai_reply)
        
        # Update memory, but never block the chat response on memory writes.
        try:
            updated_memory = update_memory(user_id, user_message, ai_reply, memory)
            save_memory(user_id, updated_memory)
        except Exception as e:
            logger.error(f"Memory update failed for {user_id}: {e}", exc_info=True)
            updated_memory = memory
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Chat response sent ({provider}, {elapsed_ms}ms)")
        
        return ChatResponse(
            reply=ai_reply,
            provider=provider,
            intent=intent,
            relevant_memory=relevant_memory,
            memory_summary=updated_memory.get("summary"),
            latency_ms=elapsed_ms,
            error=ai_result.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        elapsed_ms = int((time.time() - start_time) * 1000)
        return ChatResponse(
            reply=AI_UNAVAILABLE_REPLY,
            provider="error",
            intent="error",
            latency_ms=elapsed_ms,
            error=str(e)
        )


@app.get("/memory/{user_id}")
async def get_user_memory(user_id: str):
    """
    Retrieve user memory (profile, summary, emotional trends).
    
    Args:
        user_id: User identifier
        
    Returns:
        Memory summary
    """
    try:
        if not user_id or len(user_id) > 256:
            raise HTTPException(status_code=400, detail="Invalid user_id")
        
        memory = get_memory(user_id)
        
        return {
            "profile": memory.get("profile"),
            "summary": memory.get("summary"),
            "emotions": memory.get("emotions"),
            "sentiments": memory.get("sentiments"),
            "long_term_count": len(memory.get("long_term", [])),
            "embeddings_count": len(memory.get("embeddings", []))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve memory")


# =========================
# ERROR HANDLERS
# =========================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
