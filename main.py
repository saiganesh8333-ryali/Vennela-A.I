
"""Vennela AI - Production Ready Main Server"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from firebase_admin import firestore
from pydantic import BaseModel, Field, validator

from ai_router import get_ai_response
from firebase_db import get_db, initialize_firebase
from nlp_engine import detect_intent, get_rule_based_reply
from retrieval import retrieve_memory
from smart_memory import (
    get_memory,
    save_memory,
    update_memory,
)

# =========================================================
# LOAD ENV
# =========================================================

load_dotenv()

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="Vennela AI",
    version="3.0.0",
    description="Production Ready AI Assistant"
)

# =========================================================
# CONFIG
# =========================================================

VENNELA_PROMPT = os.getenv(
    "VENNELA_PROMPT",
    """
You are VENNELA AI.

IMPORTANT RULES:

1. Reply ONLY to the latest user message.
2. Never say:
   - System online
   - How can I assist
   - I am ready
   - Hello I am Vennela
3. Never introduce yourself repeatedly.
4. Never ignore the user's actual question.
5. Be natural and direct.
6. Keep responses conversational.
7. Do not behave like a boot screen assistant.
8. Avoid repeated greetings.
9. Focus on the user's exact request.

If user asks a question:
answer the question directly.
"""
)

RECENT_CHAT_LIMIT = int(
    os.getenv("RECENT_CHAT_LIMIT", "6")
)

RATE_LIMIT_REQUESTS = int(
    os.getenv("RATE_LIMIT_REQUESTS", "100")
)

RATE_LIMIT_WINDOW_MINUTES = int(
    os.getenv("RATE_LIMIT_WINDOW_MINUTES", "1")
)

AI_UNAVAILABLE_REPLY = (
    "AI temporarily unavailable. Please try again."
)

# =========================================================
# RATE LIMIT MEMORY
# =========================================================

_rate_limit_tracker: Dict[str, List[datetime]] = {}

# =========================================================
# BAD RESPONSE FILTER
# =========================================================

BAD_PATTERNS = [
    "system online",
    "how can i assist",
    "i am ready",
    "i'm ready",
    "hello i am vennela",
    "i am vennela",
    "i'm vennela",
    "ready to help",
    "listening...",
    "boot sequence",
]


def is_bad_response(text: str) -> bool:

    if not text:
        return True

    lower = text.lower().strip()

    return any(
        pattern in lower
        for pattern in BAD_PATTERNS
    )

# =========================================================
# MODELS
# =========================================================


class ChatRequest(BaseModel):

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=256
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=5000
    )

    @validator("user_id")
    def validate_user_id(cls, v):

        v = v.strip()

        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Invalid user_id format"
            )

        return v

    @validator("message")
    def validate_message(cls, v):

        v = v.strip()

        if not v:
            raise ValueError("Empty message")

        return v


class ChatResponse(BaseModel):

    reply: str
    provider: str
    intent: Optional[str] = None
    latency_ms: Optional[int] = None
    relevant_memory: Optional[str] = None
    memory_summary: Optional[str] = None
    error: Optional[str] = None

# =========================================================
# STARTUP
# =========================================================


@app.on_event("startup")
async def startup_event():

    logger.info("🚀 Starting Vennela AI")

    try:

        initialize_firebase()

        logger.info("✅ Firebase initialized")

    except Exception as e:

        logger.error(
            f"Firebase init failed: {e}",
            exc_info=True
        )

    logger.info("✅ Startup complete")


# =========================================================
# GLOBAL ERROR HANDLER
# =========================================================


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error"
        }
    )

# =========================================================
# RATE LIMIT
# =========================================================


def check_rate_limit(user_id: str) -> bool:

    now = datetime.now()

    window_start = (
        now - timedelta(
            minutes=RATE_LIMIT_WINDOW_MINUTES
        )
    )

    if user_id not in _rate_limit_tracker:
        _rate_limit_tracker[user_id] = []

    _rate_limit_tracker[user_id] = [
        req
        for req in _rate_limit_tracker[user_id]
        if req > window_start
    ]

    if (
        len(_rate_limit_tracker[user_id])
        >= RATE_LIMIT_REQUESTS
    ):
        return False

    _rate_limit_tracker[user_id].append(now)

    return True

# =========================================================
# MEMORY HELPERS
# =========================================================


def minimal_memory() -> Dict:

    return {
        "profile": {},
        "summary": "",
        "emotions": {},
        "sentiments": {},
        "short_term": [],
        "long_term": [],
        "embeddings": []
    }


def format_memory_prompt(
    memory: Dict,
    relevant_memory: Optional[str]
) -> str:

    summary = (
        memory.get("summary")
        or "No memory."
    )

    relevant = (
        relevant_memory
        or "No relevant memory."
    )

    return f"""
{VENNELA_PROMPT}

USER MEMORY:
{summary}

RELEVANT MEMORY:
{relevant}
"""


def save_message(
    user_id: str,
    role: str,
    content: str
):

    try:

        if (
            role == "assistant"
            and is_bad_response(content)
        ):
            logger.warning(
                "⚠️ Skipping bad assistant reply"
            )
            return

        db = get_db()

        if not db:
            return

        db.collection("chat_memory") \
            .document(user_id) \
            .collection("messages") \
            .add({
                "role": role,
                "content": content[:5000],
                "timestamp": firestore.SERVER_TIMESTAMP
            })

    except Exception as e:

        logger.error(
            f"Save message error: {e}"
        )


def load_messages(
    user_id: str,
    memory: Dict,
    relevant_memory: Optional[str],
    user_message: str
) -> list:

    system_prompt = format_memory_prompt(
        memory,
        relevant_memory
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    try:

        db = get_db()

        if not db:
            raise Exception("No DB")

        docs = db.collection("chat_memory") \
            .document(user_id) \
            .collection("messages") \
            .order_by("timestamp") \
            .stream()

        history = list(docs)[-RECENT_CHAT_LIMIT:]

        for doc in history:

            data = doc.to_dict()

            if not data:
                continue

            role = data.get("role")
            content = data.get("content")

            if not role or not content:
                continue

            if is_bad_response(content):
                continue

            messages.append({
                "role": role,
                "content": content
            })

    except Exception as e:

        logger.warning(
            f"History load failed: {e}"
        )

    # VERY IMPORTANT FIX
    # ALWAYS APPEND CURRENT USER MESSAGE

    messages.append({
        "role": "user",
        "content": user_message
    })

    # DEBUG PRINT
    logger.info("========== FINAL AI MESSAGES ==========")

    for i, msg in enumerate(messages):

        logger.info(
            f"{i}. {msg['role']}: "
            f"{msg['content'][:120]}"
        )

    logger.info("=======================================")

    return messages

# =========================================================
# ROUTES
# =========================================================


@app.get("/")
async def root():

    return {
        "message": "Vennela AI Running 🚀"
    }


@app.get("/health")
async def health():

    return {
        "status": "ok",
        "version": "3.0.0"
    }

# =========================================================
# CHAT
# =========================================================


@app.post(
    "/chat",
    response_model=ChatResponse
)
async def chat(
    request: ChatRequest
):

    start_time = time.time()

    user_id = request.user_id
    user_message = request.message.strip()

    logger.info(
        f"💬 {user_id}: {user_message}"
    )

    try:

        # RATE LIMIT

        if not check_rate_limit(user_id):

            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )

        # LOAD MEMORY

        try:

            memory = get_memory(user_id)

        except Exception as e:

            logger.error(
                f"Memory load failed: {e}"
            )

            memory = minimal_memory()

        # RETRIEVE RELEVANT MEMORY

        try:

            relevant_memory = retrieve_memory(
                memory,
                user_message
            )

        except Exception as e:

            logger.error(
                f"Retrieve memory failed: {e}"
            )

            relevant_memory = None

        # INTENT

        intent = detect_intent(user_message)

        # SAVE USER MESSAGE

        save_message(
            user_id,
            "user",
            user_message
        )

        # LOCAL RULE RESPONSE

        try:

            local_reply = get_rule_based_reply(
                intent,
                user_message,
                memory,
                relevant_memory
            )

        except Exception as e:

            logger.error(
                f"Rule engine failed: {e}"
            )

            local_reply = None

        if local_reply:

            save_message(
                user_id,
                "assistant",
                local_reply
            )

            elapsed = int(
                (time.time() - start_time) * 1000
            )

            return ChatResponse(
                reply=local_reply,
                provider="local_rules",
                intent=intent,
                relevant_memory=relevant_memory,
                memory_summary=memory.get(
                    "summary"
                ),
                latency_ms=elapsed
            )

        # LOAD AI CONTEXT

        messages = load_messages(
            user_id=user_id,
            memory=memory,
            relevant_memory=relevant_memory,
            user_message=user_message
        )

        # AI RESPONSE

        ai_result = get_ai_response(messages)

        ai_reply = ai_result.get(
            "response",
            ""
        ).strip()

        provider = ai_result.get(
            "provider",
            "unknown"
        )

        # FINAL FILTER

        if is_bad_response(ai_reply):

            logger.warning(
                "⚠️ AI produced bad startup response"
            )

            ai_reply = (
                "Sorry, something went wrong. "
                "Please send the message again."
            )

        # EMPTY CHECK

        if not ai_reply:

            ai_reply = AI_UNAVAILABLE_REPLY

        # SAVE ASSISTANT MESSAGE

        save_message(
            user_id,
            "assistant",
            ai_reply
        )

        # UPDATE MEMORY

        try:

            updated_memory = update_memory(
                user_id,
                user_message,
                ai_reply,
                memory
            )

            save_memory(
                user_id,
                updated_memory
            )

        except Exception as e:

            logger.error(
                f"Memory update failed: {e}"
            )

            updated_memory = memory

        # LATENCY

        elapsed = int(
            (time.time() - start_time) * 1000
        )

        logger.info(
            f"✅ Response generated "
            f"({provider}) {elapsed}ms"
        )

        return ChatResponse(
            reply=ai_reply,
            provider=provider,
            intent=intent,
            relevant_memory=relevant_memory,
            memory_summary=updated_memory.get(
                "summary"
            ),
            latency_ms=elapsed
        )

    except HTTPException:
        raise

    except Exception as e:

        logger.error(
            f"Chat endpoint error: {e}",
            exc_info=True
        )

        elapsed = int(
            (time.time() - start_time) * 1000
        )

        return ChatResponse(
            reply=AI_UNAVAILABLE_REPLY,
            provider="error",
            intent="error",
            latency_ms=elapsed,
            error=str(e)
        )

# =========================================================
# MEMORY API
# =========================================================


@app.get("/memory/{user_id}")
async def get_user_memory(
    user_id: str
):

    try:

        memory = get_memory(user_id)

        return {
            "summary": memory.get(
                "summary"
            ),
            "emotions": memory.get(
                "emotions"
            ),
            "sentiments": memory.get(
                "sentiments"
            ),
            "profile": memory.get(
                "profile"
            )
        }

    except Exception as e:

        logger.error(
            f"Memory API error: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Memory fetch failed"
        )

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.getenv("PORT", "8000")
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

