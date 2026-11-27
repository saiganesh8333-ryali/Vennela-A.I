"""
Vennela AI - FastAPI Web Server
Lightweight deployment with all heavyweight modules replaced.

This is the main entry point for Render deployment.
"""

import asyncio
import contextlib
import hashlib
import hmac
import inspect
import os
from pathlib import Path
import sys
import re
from uuid import UUID, uuid4
from dotenv import load_dotenv

_BACKEND_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_backend_dotenv(env_path: Path | None = None) -> bool:
    """Load Backend/.env locally before security validation without overriding existing env vars."""
    target = env_path if env_path is not None else _BACKEND_ENV_FILE
    if target.is_file():
        return bool(load_dotenv(dotenv_path=target, override=False))
    return False


_load_backend_dotenv()
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
import time
from observability import log_event, log_failure
from core.memory_contracts import (
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    classify_memory_error,
    get_memory_subsystem,
    resolve_supabase_credentials,
)

try:
    from llm_router.adapter import VennelaLLMAdapter
    from llm_router.contracts import RoutingError, FailureKind
    from conversation.response_policy import ConversationAdjuster
    ROUTER_AVAILABLE = True
except ImportError as exc:
    ROUTER_AVAILABLE = False
    VennelaLLMAdapter = None
    RoutingError = Exception
    FailureKind = None
    ConversationAdjuster = None

_llm_adapter_instance: Optional[Any] = None
_conversation_adjuster_instance: Optional[Any] = None
_brain_instance: Optional[Any] = None


def get_llm_adapter() -> Any:
    global _llm_adapter_instance
    if _llm_adapter_instance is None:
        if not ROUTER_AVAILABLE or VennelaLLMAdapter is None:
            raise RuntimeError("LLM Router subsystem is not available")
        mock_mode = os.getenv("LLM_ROUTER_MOCK", "false").lower() == "true"
        _llm_adapter_instance = VennelaLLMAdapter(mock=mock_mode)
    return _llm_adapter_instance


def get_conversation_adjuster() -> Any:
    global _conversation_adjuster_instance
    if _conversation_adjuster_instance is None:
        if not ROUTER_AVAILABLE or ConversationAdjuster is None:
            raise RuntimeError("ConversationAdjuster is not available")
        _conversation_adjuster_instance = ConversationAdjuster()
    return _conversation_adjuster_instance


def get_brain() -> Any:
    """Build Brain B (ProductionLangGraphBrain) as the sole intelligence engine.

    Brain A (VennelaBrain / NEXUS) is no longer instantiated or referenced.
    VENNELA_LANGGRAPH_ENABLED is deprecated — Brain B is always active.
    If initialization fails, the application raises immediately (no silent fallback).
    """
    global _brain_instance
    if _brain_instance is None:
        from production_langgraph_adapter import ProductionLangGraphBrain
        from web_intelligence.web_hunt import WebHuntAgent
        _brain_instance = ProductionLangGraphBrain(
            get_llm_adapter(),
            get_conversation_adjuster(),
            pc_gateway=get_agent_gateway(),
            android_gateway=get_agent_gateway(),
            web_agent=WebHuntAgent(),
        )
    return _brain_instance

# =========================
# CONFIGURATION
# =========================

# Enable lightweight mode FIRST - before any other imports
LIGHTWEIGHT_MODE = os.getenv('LIGHTWEIGHT_MODE', 'true').lower() == 'true'

if LIGHTWEIGHT_MODE:
    try:
        import lightweight_redirect  # Patches all imports
        print("[OK] Lightweight mode enabled - heavy libraries redirected")
    except ImportError as e:
        print(f"Warning: Could not enable lightweight mode: {e}")

# Now safe to import the rest
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# TEMPORAL, TASK & REMINDER SINGLETONS
# =========================

_temporal_context: Optional[Any] = None
_task_manager: Optional[Any] = None
_reminder_manager: Optional[Any] = None
_reminder_scheduler: Optional[Any] = None


def _resolve_and_verify_owner(
    current_user: Any,
    requested_user_id: Optional[str] = None,
) -> str:
    """Resolve and verify user identity against authenticated user to prevent BOLA/IDOR."""
    authenticated_id = getattr(current_user, "user_id", str(current_user)).strip()
    if requested_user_id and requested_user_id.strip():
        req_clean = requested_user_id.strip()
        if req_clean != authenticated_id:
            logger.warning(
                "IDOR/BOLA attempt detected: authenticated user '%s' attempted to access data for '%s'",
                authenticated_id,
                req_clean,
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: Cannot access or manipulate resources belonging to another user.",
            )
    return authenticated_id


def get_temporal_context():
    global _temporal_context
    if _temporal_context is None:
        from core.temporal.context import TemporalContext, DEFAULT_TIMEZONE
        tz = os.getenv("DEFAULT_TIMEZONE", DEFAULT_TIMEZONE)
        _temporal_context = TemporalContext(tz_name=tz)
    return _temporal_context


def _build_repo_with_supabase_fallback(
    supabase_repo_factory: Any,
    fallback_repo_factory: Any,
    label: str,
) -> Any:
    """Initialize a Supabase repository when configured, safely falling back in-memory."""
    url, key, _ = resolve_supabase_credentials()
    if url and key:
        try:
            from supabase import create_client
            return supabase_repo_factory(create_client(url, key))
        except Exception as exc:
            logger.warning(
                "Supabase %s repo unavailable (%s), falling back to in-memory",
                label,
                type(exc).__name__,
            )
    return fallback_repo_factory()


def get_task_manager():
    global _task_manager
    if _task_manager is None:
        from core.tasks import TaskManager
        from core.tasks.repository import InMemoryTaskRepository, SupabaseTaskRepository

        repo = _build_repo_with_supabase_fallback(
            SupabaseTaskRepository,
            InMemoryTaskRepository,
            "task",
        )
        _task_manager = TaskManager(repository=repo, temporal_context=get_temporal_context())
    return _task_manager


def get_reminder_manager():
    global _reminder_manager
    if _reminder_manager is None:
        from core.reminders import ReminderManager
        from core.reminders.repository import InMemoryReminderRepository, SupabaseReminderRepository

        repo = _build_repo_with_supabase_fallback(
            SupabaseReminderRepository,
            InMemoryReminderRepository,
            "reminder",
        )
        _reminder_manager = ReminderManager(repository=repo, temporal_context=get_temporal_context())
    return _reminder_manager


def get_reminder_scheduler():
    global _reminder_scheduler
    if _reminder_scheduler is None:
        from core.scheduler import ReminderScheduler
        rm = get_reminder_manager()
        _reminder_scheduler = ReminderScheduler(repository=rm.repository, temporal_context=get_temporal_context())
    return _reminder_scheduler


# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="Vennela AI",
    description="Adaptive AI with lightweight deployment",
    version="1.0.0"
)

_telegram_application = None
_telegram_webhook_secret = None


@app.middleware("http")
async def request_observability(request: Request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log_event(
            "response",
            f"{request.method} {request.url.path}",
            request_id=request_id,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response
    except Exception as exc:
        log_failure(
            "response",
            f"{request.method} {request.url.path}",
            exc,
            request_id=request_id,
            status=500,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        raise


def _telegram_secret_token(bot_token: str) -> str:
    """Derive Telegram's webhook authentication secret without exposing the bot token."""
    return hashlib.sha256(f"vennela-telegram-webhook:{bot_token}".encode()).hexdigest()


async def _stop_telegram_application(application) -> None:
    if application is None:
        return
    if application.running:
        try:
            await application.stop()
        except Exception as exc:
            logger.error(
                "Telegram application stop failed error_class=%s",
                type(exc).__name__,
            )
    if application.initialized:
        try:
            await application.shutdown()
        except Exception as exc:
            logger.error(
                "Telegram application shutdown failed error_class=%s",
                type(exc).__name__,
            )


async def _start_telegram_webhook() -> None:
    global _telegram_application, _telegram_webhook_secret
    if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
        return

    from telegram import Update
    from telegram_interface.bot import build_application, _suppress_sensitive_http_logs
    from telegram_interface.config import load_config

    application = None
    try:
        config = load_config(os.environ)
        if not config.webhook_url:
            raise RuntimeError("TELEGRAM_WEBHOOK_URL is required for the web service")
        _suppress_sensitive_http_logs()
        application = build_application(config)
        _telegram_application = application
        _telegram_webhook_secret = _telegram_secret_token(config.bot_token)
        await application.initialize()
        await application.start()
        await application.bot.set_webhook(
            url=config.webhook_url,
            allowed_updates=Update.ALL_TYPES,
            secret_token=_telegram_webhook_secret,
        )
    except Exception as exc:
        logger.error(
            "Telegram webhook startup failed error_class=%s",
            type(exc).__name__,
        )
        await _stop_telegram_application(application)
        _telegram_application = None
        _telegram_webhook_secret = None
        raise RuntimeError("Telegram webhook startup failed") from None

    logger.info("Telegram webhook registered url=%s", config.webhook_url)


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    application = _telegram_application
    secret = _telegram_webhook_secret
    if application is None or secret is None:
        raise HTTPException(status_code=503, detail="Telegram webhook unavailable")

    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(provided_secret, secret):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram update")

    from telegram import Update

    try:
        update = Update.de_json(payload, application.bot)
    except Exception as exc:
        logger.warning(
            "Telegram webhook update decoding failed error_class=%s",
            type(exc).__name__,
        )
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from None
    if update is None:
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from None
    try:
        await application.process_update(update)
    except Exception as exc:
        logger.error(
            "Telegram webhook processing failed error_class=%s",
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Telegram update processing failed"},
        )
    return {"ok": True}


# ==============================================================================
# SECURITY & AUTHENTICATION (SEC-02, SEC-03)
# ==============================================================================

class AuthenticatedUser(BaseModel):
    user_id: str
    is_boss: bool = True
    role: str = "authenticated_user"

security_bearer = HTTPBearer(auto_error=False)


def validate_startup_security_config() -> None:
    """Validate required security configuration at startup. Fail fast if missing."""
    boss_id = os.getenv("VENNELA_BOSS_ID", "").strip()
    agent_token = os.getenv("VENNELA_AGENT_TOKEN", "").strip()
    missing: list[str] = []
    if not boss_id:
        missing.append("VENNELA_BOSS_ID")
    if not agent_token:
        missing.append("VENNELA_AGENT_TOKEN")
    if missing:
        msg = f"[SEC-02 FATAL] Missing required security configuration: {', '.join(missing)}. Server cannot start securely."
        logger.critical(msg)
        raise RuntimeError(msg)

    # Reject LLM_ROUTER_MOCK=true in production/Render environments
    is_mock = os.getenv("LLM_ROUTER_MOCK", "false").lower() == "true"
    env = os.getenv("ENVIRONMENT", "").lower()
    is_prod = env in {"production", "prod", "staging"} or os.getenv("RENDER", "").lower() == "true"
    if is_mock and is_prod:
        msg = "[SEC-MOCK-01 FATAL] Mock mode (LLM_ROUTER_MOCK=true) cannot be enabled in production or Render environments."
        logger.critical(msg)
        raise RuntimeError(msg)


# Execute fail-fast security validation on module load
validate_startup_security_config()


async def get_current_authenticated_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> AuthenticatedUser:
    """Centralized Bearer token authentication dependency enforcing SEC-02 & SEC-03."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: Missing Bearer token in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_token = os.getenv("VENNELA_AGENT_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(
            status_code=500,
            detail="Server security configuration error: VENNELA_AGENT_TOKEN is unconfigured.",
        )

    supplied_token = credentials.credentials.strip()
    if not hmac.compare_digest(supplied_token, expected_token):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid or expired Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    boss_id = os.getenv("VENNELA_BOSS_ID", "").strip()
    if not boss_id:
        raise HTTPException(
            status_code=500,
            detail="Server security configuration error: VENNELA_BOSS_ID is unconfigured.",
        )
    return AuthenticatedUser(user_id=boss_id, is_boss=True, role="boss")


# ==============================================================================
# CORS CONFIGURATION (SEC-05)
# ==============================================================================

def _get_configured_cors_origins() -> list[str]:
    raw = os.getenv("VENNELA_CORS_ORIGINS", "").strip()
    if raw:
        origins = [item.strip() for item in raw.split(",") if item.strip()]
        if "*" in origins:
            raise ValueError(
                "[SEC-05 FATAL] Insecure CORS configuration: Wildcard '*' origin cannot be used with allow_credentials=True."
            )
        return origins
    # Safe explicit defaults for local desktop and web development
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://vennela-a-i.onrender.com",
        "https://vennela.ai",
    ]


cors_origins = _get_configured_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

# =========================
# AUTOMATION AGENT GATEWAY
# =========================
_agent_gateway_instance: Optional[Any] = None
_agent_transport_manager_instance: Optional[Any] = None


def get_agent_gateway():
    global _agent_gateway_instance
    if _agent_gateway_instance is None:
        from automation import AgentGateway
        _agent_gateway_instance = AgentGateway()
    return _agent_gateway_instance


try:
    from automation import create_agent_transport_api
    _agent_gw = get_agent_gateway()
    _agent_router, _agent_tm = create_agent_transport_api(_agent_gw)
    _agent_transport_manager_instance = _agent_tm
    app.include_router(_agent_router)
    logger.info("Automation Agent WebSocket router mounted at /ws/agents/{agent_id}")
except ImportError as exc:
    logger.warning(f"Automation layer not available: {exc}")

try:
    from vennela_realtime import create_realtime_api

    app.include_router(create_realtime_api())
    logger.info("Gemini Live WebSocket router mounted at /ws/gemini/live")
except ImportError as exc:
    logger.warning(f"Realtime layer not available: {exc}")

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
    message: str = Field(..., min_length=1, max_length=8192, description="User prompt message")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    request_id: Optional[str] = None


class DeviceRef(BaseModel):
    kind: str
    id: str


class AgentActionResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    device: DeviceRef
    type: str
    args: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ActionResultResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[ActionError] = None


class ChatResponse(BaseModel):
    response: str
    request_id: str
    actions: List[AgentActionResponse] = Field(default_factory=list)
    action_results: List[ActionResultResponse] = Field(default_factory=list)
    memory_status: Optional[str] = None


class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "NORMAL"
    due_expr: Optional[str] = None
    due_at: Optional[str] = None
    start_expr: Optional[str] = None
    start_at: Optional[str] = None
    user_id: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_expr: Optional[str] = None
    due_at: Optional[str] = None
    user_id: Optional[str] = None


class ReminderCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    remind_expr: Optional[str] = None
    remind_at: Optional[str] = None
    timezone: Optional[str] = None
    task_id: Optional[str] = None
    user_id: Optional[str] = None


_PC_APP_ALIASES = {
    "notepad": "notepad",
    "calculator": "calculator",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "explorer": "explorer",
    "file explorer": "explorer",
    "settings": "settings",
    "vs code": "vs code",
    "visual studio code": "vs code",
}


def _chat_request_id(request_id: Optional[str], fallback: str | None = None) -> str:
    if request_id:
        try:
            return str(UUID(request_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="request_id must be a valid UUID")
    return fallback or str(uuid4())


def _brain_failure_status(error: dict[str, Any]) -> int:
    """Map normalized internal categories to deliberate public HTTP statuses."""
    return {
        "VALIDATION_ERROR": 400,
        "AUTH_ERROR": 401,
        "RATE_LIMIT_ERROR": 429,
        "TIMEOUT_ERROR": 504,
        "CONFIG_ERROR": 500,
        "PROVIDER_ERROR": 503,
        "FALLBACK_ERROR": 503,
        "ROUTER_ERROR": 502,
    }.get(error.get("code"), 500)


def _pc_action_for_message(message: str) -> tuple[Optional[AgentActionResponse], Optional[ActionResultResponse]]:
    """Recognize only explicit, supported PC intents; ordinary text stays text-only."""
    normalized = " ".join(re.sub(r"[?.!]+$", "", message.lower().strip()).split())
    action_request_id = str(uuid4())
    device = DeviceRef(kind="pc", id="local-pc")

    if re.search(r"\b(open|launch|start)\s+([a-z0-9 ._-]+)$", normalized):
        target = re.sub(r"^(open|launch|start)\s+", "", normalized).strip()
        app = _PC_APP_ALIASES.get(target)
        if app is None:
            return None, ActionResultResponse(
                request_id=action_request_id,
                success=False,
                error=ActionError(
                    code="APP_NOT_ALLOWED",
                    message="The requested application is not in the PC Agent allowlist.",
                ),
            )
        return AgentActionResponse(
            request_id=action_request_id,
            device=device,
            type="OPEN_APP",
            args={"app": app},
        ), None

    if re.search(r"\b(close|quit|stop)\s+([a-z0-9 ._-]+)$", normalized):
        target = re.sub(r"^(close|quit|stop)\s+", "", normalized).strip()
        app = _PC_APP_ALIASES.get(target)
        if app is None:
            return None, ActionResultResponse(
                request_id=action_request_id,
                success=False,
                error=ActionError(
                    code="APP_NOT_ALLOWED",
                    message="The requested application is not in the PC Agent allowlist.",
                ),
            )
        return AgentActionResponse(
            request_id=action_request_id,
            device=device,
            type="CLOSE_APP",
            args={"app": app},
        ), None

    if re.search(r"\b(?:what\s+time\s+is\s+it|what(?:'s| is)\s+the\s+time)\s+on\s+my\s+pc\b", normalized):
        return AgentActionResponse(request_id=action_request_id, device=device, type="GET_PC_TIME"), None
    if re.search(r"\b(?:what(?:'s| is)\s+)?my\s+pc\s+battery\b|\bbattery\s+status\s+on\s+my\s+pc\b", normalized):
        return AgentActionResponse(request_id=action_request_id, device=device, type="GET_BATTERY"), None
    if re.search(r"\b(?:show|get|what(?:'s| is))\s+(?:my\s+)?active\s+window\b", normalized):
        return AgentActionResponse(request_id=action_request_id, device=device, type="GET_ACTIVE_WINDOW"), None
    if re.search(r"\b(?:show|get|what(?:'s| is))\s+(?:my\s+)?pc\s+system\s+info\b", normalized):
        return AgentActionResponse(request_id=action_request_id, device=device, type="GET_SYSTEM_INFO"), None
    return None, None


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
    """Health check endpoint (liveness)."""
    mem_mode = "unknown"
    mem_status = "unknown"
    try:
        subsystem = get_memory_subsystem()
        mem_mode = subsystem.mode.value
        mem_status = getattr(subsystem, "memory_status", "healthy")
    except Exception:
        mem_mode = "error"
        mem_status = "degraded"
    return {
        "status": "healthy",
        "lightweight_mode": LIGHTWEIGHT_MODE,
        "brain": "brain_b_langgraph",
        "memory_mode": mem_mode,
        "memory_status": mem_status,
    }


@app.get("/ready", tags=["health"])
async def ready():
    """Readiness probe verifying required Brain B memory subsystem connectivity."""
    try:
        subsystem = get_memory_subsystem()
        if subsystem is None:
            raise RuntimeError("Memory subsystem is unavailable")
        mem_mode = subsystem.mode.value
        boss_id = os.getenv("VENNELA_BOSS_ID", "").strip() or None
        check_fn = getattr(subsystem, "check_readiness", None)
        if callable(check_fn):
            if "owner_id" in inspect.signature(check_fn).parameters:
                is_ready, details = await asyncio.to_thread(check_fn, owner_id=boss_id)
            else:
                is_ready, details = await asyncio.to_thread(check_fn)
        else:
            is_ready, details = True, {"memory_status": "healthy"}
    except Exception as exc:
        diag_reason = classify_memory_error(exc)
        logger.warning(
            "Readiness check failed reason=%s error_type=%s",
            diag_reason,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "brain": "brain_b_langgraph",
                "memory_mode": "error",
                "memory_status": "degraded",
                "reason": diag_reason,
            },
        )

    mem_status = details.get("memory_status", "healthy" if is_ready else "degraded")
    if not is_ready or mem_status == "degraded":
        logger.warning(
            "Readiness check degraded memory_mode=%s memory_status=%s reason=%s diagnostic_reason=%s",
            mem_mode,
            mem_status,
            details.get("reason", "unknown"),
            details.get("diagnostic_reason", details.get("reason", "unknown")),
        )
        not_ready_payload: Dict[str, Any] = {
            "status": "not_ready",
            "brain": "brain_b_langgraph",
            "memory_mode": mem_mode,
            "memory_status": "degraded",
        }
        if details.get("reason"):
            not_ready_payload["reason"] = details["reason"]
        if details.get("diagnostic_reason") and details.get("diagnostic_reason") != details.get("reason"):
            not_ready_payload["diagnostic_reason"] = details["diagnostic_reason"]
        return JSONResponse(
            status_code=503,
            content=not_ready_payload,
        )

    if mem_mode == MemoryIsolationMode.STATELESS_ISOLATED.value:
        logger.info(
            "Readiness check evaluated memory_mode=%s memory_status=%s memory_enabled=%s reason=%s",
            mem_mode,
            mem_status,
            details.get("memory_enabled", False),
            details.get("reason", "provider_disabled"),
        )
    else:
        logger.info(
            "Readiness check evaluated memory_mode=%s memory_status=%s memory_enabled=%s owner_scoped=%s",
            mem_mode,
            mem_status,
            details.get("memory_enabled", True),
            details.get("owner_scoped", False),
        )

    ready_payload: Dict[str, Any] = {
        "status": "ready",
        "brain": "brain_b_langgraph",
        "memory_mode": mem_mode,
        "memory_status": mem_status,
    }
    for safe_key in ("memory_enabled", "owner_scoped", "owner_records_present", "reason"):
        if safe_key in details:
            ready_payload[safe_key] = details[safe_key]
    return ready_payload


@app.post("/embed", response_model=EmbeddingResponse, tags=["embeddings"])
async def embed_text(
    request: EmbeddingRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
async def detect_emotion(
    request: EmotionRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
async def analyze_sentiment(
    request: SentimentRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
async def classify_intent(
    request: IntentRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
async def process_text(
    request: Dict[str, Any],
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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




@app.get("/time", tags=["temporal"])
async def get_current_time(
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Get current timezone-aware time."""
    temporal = get_temporal_context()
    now_dt = temporal.now()
    return {
        "timezone": temporal.timezone_name,
        "time": temporal.format_time(now_dt),
        "iso": now_dt.isoformat(),
        "hour": now_dt.hour,
        "minute": now_dt.minute,
        "second": now_dt.second,
    }


@app.get("/date", tags=["temporal"])
async def get_current_date(
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Get current timezone-aware date and weekday information."""
    temporal = get_temporal_context()
    now_dt = temporal.now()
    tomorrow_dt = temporal.tomorrow()
    return {
        "timezone": temporal.timezone_name,
        "date": temporal.format_date(now_dt),
        "day_of_week": temporal.day_of_week(now_dt),
        "iso": now_dt.date().isoformat(),
        "tomorrow": {
            "date": temporal.format_date(tomorrow_dt),
            "day_of_week": temporal.day_of_week(tomorrow_dt),
            "iso": tomorrow_dt.date().isoformat(),
        }
    }


# =========================
# TASK ENDPOINTS
# =========================

@app.post("/tasks", tags=["tasks"])
async def create_task(
    request: TaskCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Create a new task with temporal due date resolution and owner authorization."""
    try:
        from core.tasks.models import TaskPriority
        task_mgr = get_task_manager()
        owner_id = _resolve_and_verify_owner(current_user, request.user_id)
        priority = TaskPriority(request.priority) if request.priority in TaskPriority.__members__ else TaskPriority.NORMAL

        task = task_mgr.create_task(
            owner_id=owner_id,
            title=request.title,
            description=request.description or "",
            priority=priority,
            due_expr=request.due_expr,
            start_expr=request.start_expr,
        )
        return task.to_dict()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Task create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks", tags=["tasks"])
async def list_tasks(
    status: Optional[str] = None,
    due_date: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """List tasks for authenticated owner."""
    try:
        from core.tasks.models import TaskStatus
        task_mgr = get_task_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        task_status = TaskStatus(status) if status and status in TaskStatus.__members__ else None

        tasks = task_mgr.list_tasks(owner_id=owner_id, status=task_status, due_date_expr=due_date)
        return [t.to_dict() for t in tasks]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", tags=["tasks"])
async def get_task(
    task_id: str,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Get single task by ID with owner isolation."""
    try:
        task_mgr = get_task_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        task = task_mgr.get_task(owner_id=owner_id, task_id=task_id)
        return task.to_dict()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task get error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/tasks/{task_id}", tags=["tasks"])
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Update task details."""
    try:
        from core.tasks.models import TaskPriority, TaskStatus
        task_mgr = get_task_manager()
        owner_id = _resolve_and_verify_owner(current_user, request.user_id)
        task_status = TaskStatus(request.status) if request.status and request.status in TaskStatus.__members__ else None
        priority = TaskPriority(request.priority) if request.priority and request.priority in TaskPriority.__members__ else None

        task = task_mgr.update_task(
            owner_id=owner_id,
            task_id=task_id,
            title=request.title,
            description=request.description,
            status=task_status,
            priority=priority,
            due_expr=request.due_expr,
        )
        return task.to_dict()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/{task_id}/complete", tags=["tasks"])
async def complete_task(
    task_id: str,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Mark a task as completed."""
    try:
        task_mgr = get_task_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        task = task_mgr.complete_task(owner_id=owner_id, task_id=task_id)
        return task.to_dict()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task complete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks/{task_id}", tags=["tasks"])
async def cancel_task(
    task_id: str,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Cancel a task."""
    try:
        task_mgr = get_task_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        task = task_mgr.cancel_task(owner_id=owner_id, task_id=task_id)
        return task.to_dict()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task cancel error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# REMINDER ENDPOINTS
# =========================

@app.post("/reminders", tags=["reminders"])
async def create_reminder(
    request: ReminderCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Create a new reminder with temporal resolution."""
    try:
        rem_mgr = get_reminder_manager()
        owner_id = _resolve_and_verify_owner(current_user, request.user_id)
        reminder = rem_mgr.create_reminder(
            owner_id=owner_id,
            title=request.title,
            description=request.description or "",
            remind_expr=request.remind_expr,
            tz_name=request.timezone,
            task_id=request.task_id,
        )
        return reminder.to_dict()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Reminder create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reminders", tags=["reminders"])
async def list_reminders(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """List reminders for authenticated owner."""
    try:
        from core.reminders.models import ReminderStatus
        rem_mgr = get_reminder_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        rem_status = ReminderStatus(status) if status and status in ReminderStatus.__members__ else None
        reminders = rem_mgr.list_reminders(owner_id=owner_id, status=rem_status)
        return [r.to_dict() for r in reminders]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reminder list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reminders/{reminder_id}", tags=["reminders"])
async def get_reminder(
    reminder_id: str,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Get reminder by ID."""
    try:
        rem_mgr = get_reminder_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        reminder = rem_mgr.get_reminder(owner_id=owner_id, reminder_id=reminder_id)
        return reminder.to_dict()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Reminder not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not reminder owner")
    except Exception as e:
        logger.error(f"Reminder get error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/reminders/{reminder_id}", tags=["reminders"])
async def cancel_reminder(
    reminder_id: str,
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Cancel a reminder."""
    try:
        rem_mgr = get_reminder_manager()
        owner_id = _resolve_and_verify_owner(current_user, user_id)
        reminder = rem_mgr.cancel_reminder(owner_id=owner_id, reminder_id=reminder_id)
        return reminder.to_dict()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Reminder not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not reminder owner")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Reminder cancel error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# CHAT ENDPOINTS
# =========================

@app.post(
    "/chat",
    response_model=ChatResponse,
    response_model_exclude_none=True,
    tags=["chat"],
)
async def chat(
    request: ChatRequest,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    request_started = time.perf_counter()
    chat_request_id = getattr(http_request.state, "request_id", None)
    timing = {
        "memory_stable_ms": None,
        "memory_relevant_ms": None,
        "memory_stable_count": 0,
        "memory_relevant_count": 0,
        "persistence_ms": None,
        "langgraph_ms": None,
        "llm_events": [],
        "status": "completed",
    }
    """Chat with Vennela AI through the Central Brain and production memory."""
    started = time.perf_counter()
    try:
        chat_request_id = _chat_request_id(
            request.request_id,
            getattr(http_request.state, "request_id", None),
        )
        log_event("request", "/chat_received", request_id=chat_request_id, session_id=request.session_id)
        owner_id = _resolve_and_verify_owner(current_user, request.user_id)

        pc_action, action_result = _pc_action_for_message(request.message)
        if pc_action is not None:
            action_text = {
                "OPEN_APP": f"Opening {pc_action.args.get('app')}, Boss.",
                "CLOSE_APP": f"Closing {pc_action.args.get('app')}, Boss.",
                "GET_PC_TIME": "Checking the time on your PC, Boss.",
                "GET_BATTERY": "Checking your PC battery, Boss.",
                "GET_ACTIVE_WINDOW": "Checking your active window, Boss.",
                "GET_SYSTEM_INFO": "Checking your PC system information, Boss.",
            }[pc_action.type]
            return ChatResponse(
                request_id=chat_request_id,
                response=action_text,
                actions=[pc_action],
            )
        if action_result is not None:
            return ChatResponse(
                request_id=chat_request_id,
                response="I couldn't complete that PC action.",
                action_results=[action_result],
            )

        # 1. Check for deterministic Temporal / Task / Reminder intent via NEXUS
        from core.nexus_intent import NexusIntentClassifier, execute_nexus_intent
        temporal = get_temporal_context()
        intent_res = NexusIntentClassifier(temporal).classify(request.message)
        if intent_res.is_actionable:
            task_mgr = get_task_manager()
            rem_mgr = get_reminder_manager()
            action_resp = execute_nexus_intent(intent_res, task_mgr, rem_mgr, owner_id, temporal)
            return ChatResponse(response=action_resp, request_id=chat_request_id)

        # 2. Memory Subsystem: Canonical interface (Stateless, Temporary MARK-I, or future MARK-II)
        mem_subsystem = get_memory_subsystem()
        mem_response = await asyncio.to_thread(
            mem_subsystem.retrieve,
            MemoryRetrievalRequest(
                query=request.message,
                user_id=owner_id,
                session_id=request.session_id,
                metadata={"request_id": chat_request_id},
            ),
        )
        mem_status = mem_response.metadata.get(
            "memory_status", getattr(mem_subsystem, "memory_status", "healthy")
        )
        timing["memory_mode"] = mem_response.mode.value
        timing["memory_status"] = mem_status
        timing["memory_stable_count"] = mem_response.metadata.get("stable_count", 0)
        timing["memory_relevant_count"] = mem_response.metadata.get("relevant_count", len(mem_response.context_strings))
        timing["memory_stable_ms"] = 0.0
        timing["memory_relevant_ms"] = mem_response.duration_ms

        retrieved_context = "\n".join(mem_response.context_strings) if mem_status != "degraded" else ""
        logger.info(
            "Memory subsystem evaluated: mode=%s count=%d request_id=%s",
            mem_response.mode.value,
            mem_response.memory_count,
            chat_request_id,
        )

        # Read personality from environment (keep existing prompts unchanged)
        VENNELA_PERSONALITY = os.getenv("VENNELA_PERSONALITY", "")
        # Read existing prompts if provided via environment (do not modify them)
        VENNELA_PROMPT = os.getenv("VENNELA_PROMPT", "")
        SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

        # Prefer VENNELA_PROMPT if present, otherwise SYSTEM_PROMPT
        base_system = VENNELA_PROMPT or SYSTEM_PROMPT or ""

        # Combine base system instruction with personality (if any)
        memory_instruction = retrieved_context
        combined_system_instruction = "\n\n".join(
            s for s in (base_system, VENNELA_PERSONALITY, memory_instruction) if s
        )

        # Preserve client-supplied ordered history while remaining compatible with single-turn clients.
        conversation_messages = list(request.messages or [])
        if not conversation_messages or not any(
            message.get("role") == "user" and message.get("content") == request.message
            for message in conversation_messages
        ):
            conversation_messages.append({"role": "user", "content": request.message})

        # Preserve the existing response policy before entering the Brain boundary.
        adjuster = get_conversation_adjuster()
        policy = adjuster.adjust(
            request.message,
            user_system_instruction=combined_system_instruction or None,
        )

        try:
            brain = get_brain()
            brain_result = await brain.process(
                request.message,
                request_id=chat_request_id,
                messages=conversation_messages,
                context={
                    "_system_instruction": policy.system_instruction,
                    "_session_id": request.session_id,
                    "_user_id": owner_id,
                    "_memory_context": [
                        line[2:] for line in retrieved_context.splitlines()
                        if line.startswith("- ")
                    ],
                    "_timing": timing,
                },
            )
            timing.update(
                {
                    "langgraph_ms": (
                        brain_result.metadata.get("timings_ms", {}).get(
                            "graph_execution"
                        )
                        if isinstance(brain_result.metadata, dict)
                        else None
                    )
                }
            )
            if brain_result.status == "failed" or not brain_result.response:
                error = brain_result.error or {}
                logger.error(
                    "Brain request failed: code=%s stage=%s",
                    error.get("code", "BRAIN_FAILURE"),
                    error.get("stage", "brain"),
                )
                raise HTTPException(
                    status_code=_brain_failure_status(error),
                    detail="AI services temporarily unavailable. Please try again later.",
                )
            text = brain_result.response

            # 5. Store to memory subsystem after successful Brain B validation (no-op in stateless mode)
            persistence_started = time.perf_counter()
            try:
                await asyncio.to_thread(
                    mem_subsystem.store,
                    request.message,
                    user_id=owner_id,
                    session_id=request.session_id,
                    metadata={"store_session": True, "request_id": chat_request_id},
                )
            except Exception as store_err:
                mem_status = "degraded"
                logger.warning("Memory store warning (%s)", type(store_err).__name__)
            finally:
                if getattr(mem_subsystem, "memory_status", "healthy") == "degraded":
                    mem_status = "degraded"
                timing["persistence_ms"] = round(
                    (time.perf_counter() - persistence_started) * 1000, 3
                )

            return ChatResponse(
                response=text,
                request_id=chat_request_id,
                memory_status="degraded" if mem_status == "degraded" else None,
            )

        except RoutingError as exc:
            timing["status"] = "failed"
            log_failure(
                "router",
                "chat_routing_failed",
                exc,
                request_id=chat_request_id,
                session_id=request.session_id,
                error_kind=getattr(exc.failure, "kind", "unknown"),
            )
            if FailureKind is not None and getattr(exc.failure, "kind", None) in {FailureKind.NO_API_KEY, FailureKind.AUTHENTICATION}:
                raise HTTPException(status_code=401, detail="LLM authentication failed")
            raise HTTPException(status_code=503, detail="AI services temporarily unavailable. Please try again later.")
        except HTTPException:
            timing["status"] = "failed"
            raise
        except Exception as e:
            timing["status"] = "failed"
            logger.error(f"Chat execution error: {e}")
            raise HTTPException(status_code=500, detail="Internal AI error")
    except HTTPException:
        timing["status"] = "failed"
        raise
    except Exception as e:
        timing["status"] = "failed"
        log_failure(
            "request",
            "/chat_failed",
            e,
            request_id=getattr(http_request.state, "request_id", None),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        raise HTTPException(status_code=500, detail="Internal AI error")
    finally:
        llm_events = timing.get("llm_events", [])
        latest_llm = llm_events[-1] if llm_events else {}
        logger.info(
            "chat_timing request_id=%s status=%s total_ms=%.3f "
            "memory_stable_ms=%s memory_stable_count=%s "
            "memory_relevant_ms=%s memory_relevant_count=%s langgraph_ms=%s "
            "llm_ms=%s persistence_ms=%s provider=%s model=%s "
            "llm_success=%s fallback_used=%s attempt_count=%s",
            chat_request_id,
            timing["status"],
            (time.perf_counter() - request_started) * 1000,
            timing["memory_stable_ms"],
            timing["memory_stable_count"],
            timing["memory_relevant_ms"],
            timing["memory_relevant_count"],
            timing["langgraph_ms"],
            latest_llm.get("duration_ms"),
            timing["persistence_ms"],
            latest_llm.get("provider"),
            latest_llm.get("model"),
            latest_llm.get("success"),
            latest_llm.get("fallback_used"),
            latest_llm.get("attempt_count"),
        )


_STREAM_END = object()


class _ClientDisconnectedError(Exception):
    """Internal signal raised when an HTTP streaming client disconnects."""


def _close_iterator(iterator: Any) -> None:
    """Close a synchronous stream iterator when it exposes a close hook."""
    close_fn = getattr(iterator, "close", None)
    if callable(close_fn):
        close_fn()


def _next_stream_chunk(iterator: Any) -> Any:
    """Pull the next chunk from a synchronous stream iterator."""
    return next(iterator, _STREAM_END)


async def _await_with_disconnect(
    task: asyncio.Task[Any],
    http_request: Request,
    poll_interval: float = 0.05,
) -> Any:
    """Wait for a thread-offloaded task while polling client disconnect state."""
    while True:
        done, _ = await asyncio.wait({task}, timeout=poll_interval)
        if done:
            return task.result()
        if await http_request.is_disconnected():
            raise _ClientDisconnectedError()


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Stream chat response with token-by-token output via Conversation Adjuster and LLM Router."""
    chat_request_id = _chat_request_id(
        request.request_id,
        getattr(http_request.state, "request_id", None),
    )
    log_event("request", "/chat_stream_received", request_id=chat_request_id, session_id=request.session_id)
    try:
        owner_id = _resolve_and_verify_owner(current_user, request.user_id)
        # 1. Check for deterministic Temporal / Task / Reminder intent via NEXUS
        from core.nexus_intent import NexusIntentClassifier, execute_nexus_intent
        temporal = get_temporal_context()
        intent_res = NexusIntentClassifier(temporal).classify(request.message)
        if intent_res.is_actionable:
            task_mgr = get_task_manager()
            rem_mgr = get_reminder_manager()
            action_resp = execute_nexus_intent(intent_res, task_mgr, rem_mgr, owner_id, temporal)
            return StreamingResponse(iter([action_resp]), media_type="text/plain; charset=utf-8")

        # Build memory context & personality via canonical memory subsystem
        mem_subsystem = get_memory_subsystem()
        mem_response = await asyncio.to_thread(
            mem_subsystem.retrieve,
            MemoryRetrievalRequest(
                query=request.message,
                user_id=owner_id,
                session_id=request.session_id,
                metadata={"request_id": chat_request_id},
            ),
        )
        retrieved_context = (
            "\n".join(mem_response.context_strings)
            if mem_response.metadata.get("memory_status") != "degraded"
            else ""
        )
        stream_headers = (
            {"X-Memory-Status": "degraded"}
            if mem_response.metadata.get("memory_status") == "degraded"
            else {}
        )

        VENNELA_PERSONALITY = os.getenv("VENNELA_PERSONALITY", "")
        VENNELA_PROMPT = os.getenv("VENNELA_PROMPT", "")
        SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")
        base_system = VENNELA_PROMPT or SYSTEM_PROMPT or ""
        memory_instruction = retrieved_context
        combined_system_instruction = "\n\n".join(
            s for s in (base_system, VENNELA_PERSONALITY, memory_instruction) if s
        )
        conversation_messages = list(request.messages or [])
        if not conversation_messages or not any(
            message.get("role") == "user" and message.get("content") == request.message
            for message in conversation_messages
        ):
            conversation_messages.append({"role": "user", "content": request.message})

        adjuster = get_conversation_adjuster()
        policy = adjuster.adjust(
            request.message,
            user_system_instruction=combined_system_instruction or None,
        )

        adapter = get_llm_adapter()

        async def token_generator():
            stream_iter: Any = None
            in_flight_task: asyncio.Task[Any] | None = None
            has_output = False
            clean_eof = False
            disconnected = False
            cancelled = False
            stream_failed = False

            def _start_stream():
                return iter(
                    adapter.stream_text(
                        request.message,
                        system_instruction=policy.system_instruction,
                        messages=conversation_messages,
                        latency_sensitive=policy.latency_sensitive,
                        max_tokens=policy.max_tokens,
                        request_id=chat_request_id,
                    )
                )

            try:
                if await http_request.is_disconnected():
                    disconnected = True
                    log_event(
                        "request",
                        "chat_stream_disconnected",
                        request_id=chat_request_id,
                        session_id=request.session_id,
                    )
                    return

                in_flight_task = asyncio.create_task(asyncio.to_thread(_start_stream))
                stream_iter = await _await_with_disconnect(in_flight_task, http_request)
                in_flight_task = None

                while True:
                    if await http_request.is_disconnected():
                        disconnected = True
                        log_event(
                            "request",
                            "chat_stream_disconnected",
                            request_id=chat_request_id,
                            session_id=request.session_id,
                        )
                        break

                    in_flight_task = asyncio.create_task(
                        asyncio.to_thread(_next_stream_chunk, stream_iter)
                    )
                    token = await _await_with_disconnect(in_flight_task, http_request)
                    in_flight_task = None

                    if token is _STREAM_END:
                        if await http_request.is_disconnected():
                            disconnected = True
                            log_event(
                                "request",
                                "chat_stream_disconnected",
                                request_id=chat_request_id,
                                session_id=request.session_id,
                            )
                        else:
                            clean_eof = True
                        break

                    if await http_request.is_disconnected():
                        disconnected = True
                        log_event(
                            "request",
                            "chat_stream_disconnected",
                            request_id=chat_request_id,
                            session_id=request.session_id,
                        )
                        break

                    if token:
                        if str(token).strip():
                            has_output = True
                        yield token

                # Persist turn strictly after verified clean EOF without cancellation or disconnect
                if (
                    clean_eof
                    and not disconnected
                    and not cancelled
                    and not stream_failed
                    and has_output
                ):
                    try:
                        await asyncio.to_thread(
                            mem_subsystem.store,
                            request.message,
                            user_id=owner_id,
                            session_id=request.session_id,
                            metadata={"store_session": True, "request_id": chat_request_id},
                        )
                    except Exception as store_err:
                        logger.warning("Streaming memory store warning (%s)", type(store_err).__name__)

            except _ClientDisconnectedError:
                disconnected = True
                log_event(
                    "request",
                    "chat_stream_disconnected",
                    request_id=chat_request_id,
                    session_id=request.session_id,
                )
                return
            except asyncio.CancelledError:
                cancelled = True
                log_event(
                    "request",
                    "chat_stream_cancelled",
                    request_id=chat_request_id,
                    session_id=request.session_id,
                )
                raise
            except GeneratorExit:
                cancelled = True
                raise
            except Exception as exc:
                stream_failed = True
                log_failure(
                    "router",
                    "stream_failed",
                    exc,
                    request_id=chat_request_id,
                    session_id=request.session_id,
                )
                if not await http_request.is_disconnected():
                    yield "\n[AI service temporarily unavailable]"
            finally:
                if in_flight_task is not None and not in_flight_task.done():
                    def _cleanup_after_task(
                        completed: asyncio.Task[Any],
                        active_iter: Any = stream_iter,
                    ) -> None:
                        target = active_iter
                        if not completed.cancelled():
                            exc: BaseException | None = None
                            with contextlib.suppress(BaseException):
                                exc = completed.exception()
                            if exc is None and target is None:
                                with contextlib.suppress(BaseException):
                                    target = completed.result()
                        if target is not None:
                            with contextlib.suppress(Exception):
                                _close_iterator(target)

                    in_flight_task.add_done_callback(_cleanup_after_task)
                elif stream_iter is not None:
                    with contextlib.suppress(Exception):
                        _close_iterator(stream_iter)

        return StreamingResponse(
            token_generator(),
            media_type="text/plain; charset=utf-8",
            headers=stream_headers,
        )

    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise
    except RoutingError as exc:
        log_failure(
            "router",
            "chat_stream_routing_failed",
            exc,
            request_id=chat_request_id,
            session_id=request.session_id,
            error_kind=getattr(getattr(exc, "failure", None), "kind", "unknown"),
        )
        if FailureKind is not None and getattr(getattr(exc, "failure", None), "kind", None) in {
            FailureKind.NO_API_KEY,
            FailureKind.AUTHENTICATION,
        }:
            raise HTTPException(status_code=401, detail="LLM authentication failed")
        raise HTTPException(status_code=503, detail="AI services temporarily unavailable. Please try again later.")
    except Exception as exc:
        log_failure(
            "request",
            "/chat_stream_failed",
            exc,
            request_id=chat_request_id,
            session_id=request.session_id,
        )
        raise HTTPException(status_code=500, detail="Internal AI error")


@app.get("/router/health", tags=["router"])
async def router_health(
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Get diagnostic health and circuit breaker summary of LLM Router."""
    try:
        adapter = get_llm_adapter()
        return adapter.health_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/router/models", tags=["router"])
async def router_models(
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """List configured model profiles in LLM Router."""
    try:
        adapter = get_llm_adapter()
        return adapter.model_catalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/status", tags=["health"])
async def status(
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
    """Get detailed status."""
    router_status = "unavailable"
    health_info = {}
    try:
        adapter = get_llm_adapter()
        health_info = adapter.health_summary()
        router_status = "active"
    except Exception as exc:
        router_status = f"error: {exc}"

    return {
        "status": "running",
        "lightweight_mode": LIGHTWEIGHT_MODE,
        "phases": "1-5 + Temporal/Task/Reminder (All systems active)",
        "router": {
            "status": router_status,
            "providers": health_info,
        },
        "modules": {
            "llm_router": "llm_router.adapter.VennelaLLMAdapter",
            "conversation_adjuster": "conversation.response_policy.ConversationAdjuster",
            "temporal_context": "core.temporal.TemporalContext",
            "task_manager": "core.tasks.TaskManager",
            "reminder_manager": "core.reminders.ReminderManager",
            "reminder_scheduler": "core.scheduler.ReminderScheduler",
            "nexus_intent": "core.nexus_intent.NexusIntentClassifier",
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
async def get_proactive_suggestions(
    request: ProactiveSuggestionRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
async def create_goal_with_plan(
    request: GoalCreationRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
async def get_next_action(
    request: ActionRecommendationRequest,
    current_user: AuthenticatedUser = Depends(get_current_authenticated_user),
):
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
    """Return a stable internal-error response without exposing exception details."""
    log_failure(
        "response",
        "unhandled_exception",
        exc,
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "type": "INTERNAL_ERROR"},
    )


# =========================
# STARTUP/SHUTDOWN
# =========================

def validate_memory_startup() -> None:
    """Validate and probe the configured memory subsystem during application startup."""
    mem_subsystem = get_memory_subsystem()
    validate_fn = getattr(mem_subsystem, "validate_startup", None)
    if callable(validate_fn):
        validate_fn()


@app.on_event("startup")
async def startup_event():
    """Run on startup."""
    logger.info("Vennela AI starting up...")
    logger.info(f"Lightweight mode: {LIGHTWEIGHT_MODE}")
    logger.info(f"Python runtime: {sys.version.split()[0]}")
    await asyncio.to_thread(validate_memory_startup)
    try:
        scheduler = get_reminder_scheduler()
        await scheduler.start()
        logger.info("Reminder scheduler started successfully.")
    except Exception as exc:
        logger.warning(f"Could not start reminder scheduler: {exc}")
    await _start_telegram_webhook()
    print("SERVER STARTED OK")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on shutdown."""
    logger.info("Vennela AI shutting down...")
    global _telegram_application, _telegram_webhook_secret
    await _stop_telegram_application(_telegram_application)
    _telegram_application = None
    _telegram_webhook_secret = None
    try:
        global _reminder_scheduler
        if _reminder_scheduler is not None:
            await _reminder_scheduler.stop()
    except Exception as exc:
        logger.warning(f"Error stopping reminder scheduler: {exc}")


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
