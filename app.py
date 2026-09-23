"""
Vennela AI - FastAPI Web Server
Lightweight deployment with all heavyweight modules replaced.

This is the main entry point for Render deployment.
"""

import os
import sys
import re
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

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
        _llm_adapter_instance = VennelaLLMAdapter()
    return _llm_adapter_instance


def get_conversation_adjuster() -> Any:
    global _conversation_adjuster_instance
    if _conversation_adjuster_instance is None:
        if not ROUTER_AVAILABLE or ConversationAdjuster is None:
            raise RuntimeError("ConversationAdjuster is not available")
        _conversation_adjuster_instance = ConversationAdjuster()
    return _conversation_adjuster_instance


def get_brain() -> Any:
    """Build the Central Brain once, sharing the production router adapter."""
    global _brain_instance
    if _brain_instance is None:
        from agents import AgentOrchestrator, AgentRegistry, VennelaBrain, VennelaReasoningAdapter
        from agents.web_hunt import WebHuntAgent

        registry = AgentRegistry()
        registry.register(WebHuntAgent())
        _brain_instance = VennelaBrain(
            orchestrator=AgentOrchestrator(registry),
            reasoning=VennelaReasoningAdapter(
                adapter=get_llm_adapter(),
                adjuster=get_conversation_adjuster(),
            ),
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


def _basic_memory_context(session_id: Optional[str] = None):
    """Build the single trusted Boss context from server configuration only."""
    from memory import AuthContext

    boss_id = os.getenv("VENNELA_BOSS_ID", "").strip()
    if not boss_id:
        raise RuntimeError("VENNELA_BOSS_ID is required for memory access")
    normalized_session = session_id.strip() if isinstance(session_id, str) and session_id.strip() else None
    return AuthContext(user_id=boss_id, authenticated=True, session_id=normalized_session)


def _basic_memory_api():
    """Construct the production Basic Memory API lazily."""
    from supabase import create_client
    from memory import MemoryAPI, SupabaseMemoryRepository

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for memory access")
    return MemoryAPI(SupabaseMemoryRepository(create_client(url, key)))


def _retrieve_chat_memories(memory_context, memory_api, query: str):
    """Use the existing semantic memory layer for response-time retrieval."""
    from memory import IntelligentMemory

    scored = IntelligentMemory(memory_api).retrieve_semantic(
        memory_context,
        query,
        session_id=memory_context.session_id,
        limit=5,
        min_similarity=0.05,
    )
    return [item.record for item in scored]


def _retrieve_stable_chat_memories(memory_context, memory_api, limit: int = 12):
    """Select a bounded, deterministic profile/project context from canonical memory."""
    from memory import MemoryCategory, MemoryDomain

    if limit <= 0:
        return []

    stable_categories = (
        MemoryCategory.PROFILE,
        MemoryCategory.PREFERENCE,
        MemoryCategory.INTEREST,
        MemoryCategory.GOAL,
        MemoryCategory.PROJECT,
    )
    records = memory_api.retrieve(
        memory_context,
        MemoryDomain.BOSS_PERSONAL.value,
        limit=100,
    )
    active_records = [
        record for record in records
        if record.active
        and record.category in stable_categories
        and not (
            isinstance(record.content, dict)
            and record.content.get("lifecycle_state") in {"SUPERSEDED", "OBSOLETE", "INACTIVE"}
        )
        and not (
            isinstance(record.content, dict)
            and record.content.get("evolution_state") == "historical"
        )
    ]

    selected = []
    for category in stable_categories:
        category_records = [
            record for record in active_records if record.category is category
        ]
        category_records.sort(
            key=lambda record: (
                -_memory_importance(record),
                -record.updated_at.timestamp(),
                record.memory_id,
            )
        )
        selected.extend(category_records[:3])
        if len(selected) >= limit:
            break
    return selected[:limit]


def _memory_text(record) -> str:
    content = record.content
    if isinstance(content, dict):
        content = content.get("text", content.get("content", ""))
    return content.strip() if isinstance(content, str) else ""


def _memory_importance(record) -> float:
    if not isinstance(record.content, dict):
        return 0.5
    try:
        return max(0.0, min(1.0, float(record.content.get("importance", 0.5))))
    except (TypeError, ValueError):
        return 0.5


def _build_chat_memory_instruction(stable_memories, relevant_memories) -> str:
    """Format bounded stable and query-relevant memories without duplicate records."""
    stable_ids = {record.memory_id for record in stable_memories}
    stable_lines = [f"- {_memory_text(record)}" for record in stable_memories if _memory_text(record)]
    relevant_lines = [
        f"- {_memory_text(record)}"
        for record in relevant_memories
        if record.memory_id not in stable_ids and _memory_text(record)
    ]
    sections = []
    if stable_lines:
        sections.append("Stable user context:\n" + "\n".join(stable_lines))
    if relevant_lines:
        sections.append("Relevant memories:\n" + "\n".join(relevant_lines))
    return "\n\n".join(sections)


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
# TEMPORAL, TASK & REMINDER SINGLETONS
# =========================

_temporal_context: Optional[Any] = None
_task_manager: Optional[Any] = None
_reminder_manager: Optional[Any] = None
_reminder_scheduler: Optional[Any] = None


def _get_owner_id(request_user_id: Optional[str] = None) -> str:
    """Resolve authoritative owner id for task/reminder isolation."""
    if request_user_id and request_user_id.strip():
        return request_user_id.strip()
    boss_id = os.getenv("VENNELA_BOSS_ID", "").strip()
    if boss_id:
        return boss_id
    return "boss_user"


def get_temporal_context():
    global _temporal_context
    if _temporal_context is None:
        from core.temporal.context import TemporalContext, DEFAULT_TIMEZONE
        tz = os.getenv("DEFAULT_TIMEZONE", DEFAULT_TIMEZONE)
        _temporal_context = TemporalContext(tz_name=tz)
    return _temporal_context


def get_task_manager():
    global _task_manager
    if _task_manager is None:
        from core.tasks import TaskManager
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if url and key:
            try:
                from supabase import create_client
                from core.tasks.repository import SupabaseTaskRepository
                repo = SupabaseTaskRepository(create_client(url, key))
            except Exception as e:
                logger.warning("Supabase task repo unavailable, falling back to in-memory: %s", e)
                from core.tasks.repository import InMemoryTaskRepository
                repo = InMemoryTaskRepository()
        else:
            from core.tasks.repository import InMemoryTaskRepository
            repo = InMemoryTaskRepository()
        _task_manager = TaskManager(repository=repo, temporal_context=get_temporal_context())
    return _task_manager


def get_reminder_manager():
    global _reminder_manager
    if _reminder_manager is None:
        from core.reminders import ReminderManager
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if url and key:
            try:
                from supabase import create_client
                from core.reminders.repository import SupabaseReminderRepository
                repo = SupabaseReminderRepository(create_client(url, key))
            except Exception as e:
                logger.warning("Supabase reminder repo unavailable, falling back to in-memory: %s", e)
                from core.reminders.repository import InMemoryReminderRepository
                repo = InMemoryReminderRepository()
        else:
            from core.reminders.repository import InMemoryReminderRepository
            repo = InMemoryReminderRepository()
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    from realtime import create_realtime_api

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
    message: str
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


def _chat_request_id(request_id: Optional[str]) -> str:
    if request_id:
        try:
            return str(UUID(request_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="request_id must be a valid UUID")
    return str(uuid4())


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




@app.get("/time", tags=["temporal"])
async def get_current_time():
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
async def get_current_date():
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
async def create_task(request: TaskCreateRequest):
    """Create a new task with temporal due date resolution."""
    try:
        from core.tasks.models import TaskPriority
        task_mgr = get_task_manager()
        owner_id = _get_owner_id(request.user_id)
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Task create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks", tags=["tasks"])
async def list_tasks(status: Optional[str] = None, due_date: Optional[str] = None, user_id: Optional[str] = None):
    """List tasks for authenticated owner."""
    try:
        from core.tasks.models import TaskStatus
        task_mgr = get_task_manager()
        owner_id = _get_owner_id(user_id)
        task_status = TaskStatus(status) if status and status in TaskStatus.__members__ else None

        tasks = task_mgr.list_tasks(owner_id=owner_id, status=task_status, due_date_expr=due_date)
        return [t.to_dict() for t in tasks]
    except Exception as e:
        logger.error(f"Task list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", tags=["tasks"])
async def get_task(task_id: str, user_id: Optional[str] = None):
    """Get single task by ID with owner isolation."""
    try:
        task_mgr = get_task_manager()
        owner_id = _get_owner_id(user_id)
        task = task_mgr.get_task(owner_id=owner_id, task_id=task_id)
        return task.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task get error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/tasks/{task_id}", tags=["tasks"])
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Update task details."""
    try:
        from core.tasks.models import TaskPriority, TaskStatus
        task_mgr = get_task_manager()
        owner_id = _get_owner_id(request.user_id)
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
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/{task_id}/complete", tags=["tasks"])
async def complete_task(task_id: str, user_id: Optional[str] = None):
    """Mark a task as completed."""
    try:
        task_mgr = get_task_manager()
        owner_id = _get_owner_id(user_id)
        task = task_mgr.complete_task(owner_id=owner_id, task_id=task_id)
        return task.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not task owner")
    except Exception as e:
        logger.error(f"Task complete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks/{task_id}", tags=["tasks"])
async def cancel_task(task_id: str, user_id: Optional[str] = None):
    """Cancel a task."""
    try:
        task_mgr = get_task_manager()
        owner_id = _get_owner_id(user_id)
        task = task_mgr.cancel_task(owner_id=owner_id, task_id=task_id)
        return task.to_dict()
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
async def create_reminder(request: ReminderCreateRequest):
    """Create a new reminder with temporal resolution."""
    try:
        rem_mgr = get_reminder_manager()
        owner_id = _get_owner_id(request.user_id)
        reminder = rem_mgr.create_reminder(
            owner_id=owner_id,
            title=request.title,
            description=request.description or "",
            remind_expr=request.remind_expr,
            tz_name=request.timezone,
            task_id=request.task_id,
        )
        return reminder.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Reminder create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reminders", tags=["reminders"])
async def list_reminders(status: Optional[str] = None, user_id: Optional[str] = None):
    """List reminders for authenticated owner."""
    try:
        from core.reminders.models import ReminderStatus
        rem_mgr = get_reminder_manager()
        owner_id = _get_owner_id(user_id)
        rem_status = ReminderStatus(status) if status and status in ReminderStatus.__members__ else None
        reminders = rem_mgr.list_reminders(owner_id=owner_id, status=rem_status)
        return [r.to_dict() for r in reminders]
    except Exception as e:
        logger.error(f"Reminder list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reminders/{reminder_id}", tags=["reminders"])
async def get_reminder(reminder_id: str, user_id: Optional[str] = None):
    """Get reminder by ID."""
    try:
        rem_mgr = get_reminder_manager()
        owner_id = _get_owner_id(user_id)
        reminder = rem_mgr.get_reminder(owner_id=owner_id, reminder_id=reminder_id)
        return reminder.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Reminder not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied: Not reminder owner")
    except Exception as e:
        logger.error(f"Reminder get error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/reminders/{reminder_id}", tags=["reminders"])
async def cancel_reminder(reminder_id: str, user_id: Optional[str] = None):
    """Cancel a reminder."""
    try:
        rem_mgr = get_reminder_manager()
        owner_id = _get_owner_id(user_id)
        reminder = rem_mgr.cancel_reminder(owner_id=owner_id, reminder_id=reminder_id)
        return reminder.to_dict()
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

@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest, http_request: Request):
    """Chat with Vennela AI through the Central Brain and production memory."""
    try:
        chat_request_id = _chat_request_id(request.request_id)
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
            owner_id = _get_owner_id(request.user_id)
            task_mgr = get_task_manager()
            rem_mgr = get_reminder_manager()
            action_resp = execute_nexus_intent(intent_res, task_mgr, rem_mgr, owner_id, temporal)
            return ChatResponse(response=action_resp, request_id=chat_request_id)

        # 2. Memory is always scoped to the server-configured Boss identity.
        memory_api = None
        memory_context = None
        memories = []
        stable_memories = []
        try:
            memory_context = _basic_memory_context(request.session_id)
            memory_api = _basic_memory_api()
            stable_memories = _retrieve_stable_chat_memories(memory_context, memory_api)
            memories = _retrieve_chat_memories(memory_context, memory_api, request.message)
            logger.info(
                "Chat memory retrieval: stable=%d relevant=%d",
                len(stable_memories),
                len(memories),
            )
        except Exception as memory_error:
            memories = []
            stable_memories = []
            logger.warning(
                "Chat memory retrieval unavailable: %s: %s",
                type(memory_error).__name__,
                memory_error,
            )

        retrieved_context = _build_chat_memory_instruction(stable_memories, memories)

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
                context={"_system_instruction": policy.system_instruction},
            )
            if brain_result.status == "failed" or not brain_result.response:
                error = brain_result.error or {}
                logger.error(
                    "Brain request failed: code=%s stage=%s",
                    error.get("code", "BRAIN_FAILURE"),
                    error.get("stage", "brain"),
                )
                raise HTTPException(
                    status_code=503,
                    detail="AI services temporarily unavailable. Please try again later.",
                )
            text = brain_result.response

            # 5. Store to Smart Memory if configured
            if memory_api is not None and memory_context is not None:
                try:
                    from memory import SmartMemory
                    memory_decision = SmartMemory(memory_api).store(
                        memory_context, request.message, domain="boss_personal", existing=memories,
                    )
                    if memory_decision.action in {"create", "update"} and memory_decision.record is None:
                        raise RuntimeError("Basic memory store returned no saved record")
                except Exception as store_err:
                    logger.warning("SmartMemory store warning: %s", store_err)

            return ChatResponse(response=text, request_id=chat_request_id)

        except RoutingError as exc:
            logger.error(f"[LLMRouter] Routing failure [{getattr(exc.failure, 'kind', 'ERROR')}]: {exc}")
            if FailureKind is not None and getattr(exc.failure, "kind", None) in {FailureKind.NO_API_KEY, FailureKind.AUTHENTICATION}:
                raise HTTPException(status_code=401, detail=f"LLM authentication failed: {exc.failure.message}")
            raise HTTPException(status_code=503, detail="AI services temporarily unavailable. Please try again later.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chat execution error: {e}")
            raise HTTPException(status_code=500, detail="Internal AI error")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest, http_request: Request):
    """Stream chat response with token-by-token output via Conversation Adjuster and LLM Router."""
    try:
        # 1. Check for deterministic Temporal / Task / Reminder intent via NEXUS
        from core.nexus_intent import NexusIntentClassifier, execute_nexus_intent
        temporal = get_temporal_context()
        intent_res = NexusIntentClassifier(temporal).classify(request.message)
        if intent_res.is_actionable:
            owner_id = _get_owner_id(request.user_id)
            task_mgr = get_task_manager()
            rem_mgr = get_reminder_manager()
            action_resp = execute_nexus_intent(intent_res, task_mgr, rem_mgr, owner_id, temporal)
            return StreamingResponse(iter([action_resp]), media_type="text/plain; charset=utf-8")

        # Build memory context & personality
        retrieved_context = ""
        try:
            memory_context = _basic_memory_context(request.session_id)
            memory_api = _basic_memory_api()
            stable_memories = _retrieve_stable_chat_memories(memory_context, memory_api)
            memories = _retrieve_chat_memories(memory_context, memory_api, request.message)
            logger.info(
                "Streaming memory retrieval: stable=%d relevant=%d",
                len(stable_memories),
                len(memories),
            )
            retrieved_context = _build_chat_memory_instruction(stable_memories, memories)
        except Exception as memory_error:
            logger.warning(
                "Streaming memory retrieval unavailable: %s: %s",
                type(memory_error).__name__,
                memory_error,
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

        def token_generator():
            try:
                for token in adapter.stream_text(
                    request.message,
                    system_instruction=policy.system_instruction,
                    messages=conversation_messages,
                    latency_sensitive=policy.latency_sensitive,
                    max_tokens=policy.max_tokens,
                ):
                    yield token
            except Exception as exc:
                logger.error(f"[LLMRouter Stream] Error: {exc}")
                yield f"\n[AI stream error: {exc}]"

        return StreamingResponse(token_generator(), media_type="text/plain; charset=utf-8")

    except Exception as e:
        logger.error(f"Chat stream setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/router/health", tags=["router"])
async def router_health():
    """Get diagnostic health and circuit breaker summary of LLM Router."""
    try:
        adapter = get_llm_adapter()
        return adapter.health_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/router/models", tags=["router"])
async def router_models():
    """List configured model profiles in LLM Router."""
    try:
        adapter = get_llm_adapter()
        return adapter.model_catalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/status", tags=["health"])
async def status():
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
    try:
        scheduler = get_reminder_scheduler()
        await scheduler.start()
        logger.info("Reminder scheduler started successfully.")
    except Exception as exc:
        logger.warning(f"Could not start reminder scheduler: {exc}")
    print("SERVER STARTED OK")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on shutdown."""
    logger.info("Vennela AI shutting down...")
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
