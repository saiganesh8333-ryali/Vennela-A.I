from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskType(str, Enum):
    CONVERSATION = "conversation"
    QUESTION = "question"
    ACTION = "action"
    RESEARCH = "research"
    MULTI_STEP = "multi_step"


class IntentType(str, Enum):
    CONVERSATION = "conversation"
    INFORMATION = "information"
    ACTION = "action"
    RESEARCH = "research"
    MULTI_STEP = "multi_step"
    AMBIGUOUS = "ambiguous"


class ReasoningLevel(str, Enum):
    SIMPLE = "simple"
    DEEP = "deep"


class ResponseStyle(str, Enum):
    CONCISE = "concise"
    CONVERSATIONAL = "conversational"
    SOURCE_GROUNDED = "source_grounded"


class DetailLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CanonicalIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent_type: IntentType = IntentType.CONVERSATION
    user_goal: str = ""
    entities: Dict[str, Any] = Field(default_factory=dict)
    requested_capabilities: List[str] = Field(default_factory=list)
    requires_pc: bool = False
    requires_android: bool = False
    requires_reasoning: bool = True
    requires_verification: bool = False
    is_multi_step: bool = False
    is_parallelizable: bool = False
    priority: int = Field(default=5, ge=1, le=10)
    task_type: TaskType
    action: Optional[str] = None
    delegate: bool = False
    target_agent: Optional[str] = None
    requires_web: bool = False
    requires_memory: bool = False
    requires_tools: bool = False
    reasoning_level: ReasoningLevel = ReasoningLevel.SIMPLE
    response_style: ResponseStyle = ResponseStyle.CONVERSATIONAL
    detail_level: DetailLevel = DetailLevel.MEDIUM
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "canonical_resolver"
    constraints: List[str] = Field(default_factory=list)
    ambiguous: bool = False
    ambiguity_reason: Optional[str] = None

    def with_updates(self, **changes: object) -> "CanonicalIntent":
        """Only orchestration policy may make explicit, immutable replacements."""
        return self.model_copy(update=changes)


def resolve_intent(request: str, conversation_context: Optional[List[str]] = None,
                   memory_context: Optional[List[str]] = None) -> CanonicalIntent:
    """The single authoritative intent-resolution stage."""
    text = request.lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    actions = []
    action_patterns = {
        "OPEN_APP": ("open", "open_app"),
        "GET_DEVICE_TIME": ("device_time", "what_time", "time"),
        "BATTERY_STATUS": ("battery", "battery_status"),
        "FLASHLIGHT": ("flashlight", "torch"),
        "DEVICE_STATUS": ("device_status", "device_status"),
    }
    for name, patterns in action_patterns.items():
        if any(pattern in normalized for pattern in patterns):
            actions.append(name)
    action = actions[0] if actions else None

    # Pure server temporal queries (handled deterministically, not via web research)
    is_pure_temporal = bool(re.search(
        r"^(?:(?:what(?:\'s|\s+is)?\s+(?:the\s+)?(?:current\s+)?(?:time|date|day|year|month))|"
        r"(?:what\s+(?:time|date|day|year|month)\s+is\s+(?:it|this|today))|"
        r"(?:which\s+(?:year|month)\s+(?:is\s+it|are\s+we\s+in))|"
        r"(?:what\s+is\s+today)|"
        r"(?:tell\s+me\s+(?:the\s+)?(?:today(?:\'s)?\s+)?(?:time|date|day|year|month))|"
        r"(?:today(?:\'s)?\s+date)|"
        r"(?:current\s+(?:time|date|year|month)))\s*\??$",
        text.strip()
    ))

    # Comprehensive indicators for web research and fresh external facts
    web_keywords = (
        "web", "search", "research", "latest", "news", "source", "sources", "internet", "online"
    )
    current_keywords = (
        "current", "currently", "recent", "recently", "upcoming", "newest", "breaking",
        "chief minister", "prime minister", "president", "governor",
        "current office holder", "who is the current", "who is current",
        "who won", "price of", "stock price", "weather in", "state of"
    )
    has_web_intent = any(w in text for w in web_keywords)
    has_current_indicator = any(w in text for w in current_keywords) or (
        any(w in text for w in ("today", "now", "this year", "this week"))
        and not is_pure_temporal
    )
    requires_web = (has_web_intent or has_current_indicator) and not is_pure_temporal
    requires_memory = any(word in text for word in ("remember", "memory", "before", "conversation"))
    requires_tools = bool(actions) or any(word in text for word in ("execute", "run", "turn on"))
    requires_pc = any(action in {"OPEN_APP", "GET_DEVICE_TIME", "BATTERY_STATUS"} for action in actions)
    requires_android = any(action in {"FLASHLIGHT", "DEVICE_STATUS"} for action in actions)
    capabilities = []
    if requires_memory:
        capabilities.append("memory.read")
    if requires_web:
        capabilities.append("web.research")
    capabilities.extend({
        "OPEN_APP": "pc.open_app", "GET_DEVICE_TIME": "pc.device_time",
        "BATTERY_STATUS": "pc.battery_status", "FLASHLIGHT": "android.flashlight",
        "DEVICE_STATUS": "android.device_status",
    }[item] for item in actions)
    ambiguous = not request.strip() or (
        any(phrase in text for phrase in ("check this", "search it", "open it", "do that")) and
        not (conversation_context or memory_context)
    )
    task_type = TaskType.ACTION if action else TaskType.RESEARCH if requires_web else (
        TaskType.QUESTION if "?" in request else TaskType.CONVERSATION
    )
    intent_type = (IntentType.AMBIGUOUS if ambiguous else
                   IntentType.MULTI_STEP if len(capabilities) > 1 else
                   IntentType.ACTION if requires_tools else
                   IntentType.RESEARCH if requires_web else
                   IntentType.INFORMATION if "?" in request else IntentType.CONVERSATION)
    if ambiguous:
        capabilities = []
    return CanonicalIntent(
        intent_type=intent_type,
        user_goal=request.strip(),
        entities={"actions": actions},
        requested_capabilities=capabilities,
        requires_pc=requires_pc,
        requires_android=requires_android,
        requires_reasoning=True,
        requires_verification=requires_tools or requires_web,
        is_multi_step=len(capabilities) > 1,
        is_parallelizable=len(capabilities) > 1 and not (requires_web and requires_pc and "open" in text and "search" in text),
        task_type=TaskType.MULTI_STEP if len(capabilities) > 1 else task_type,
        action=action,
        delegate=requires_tools or requires_web or requires_memory,
        target_agent=("pc" if action in {"OPEN_APP", "GET_DEVICE_TIME", "BATTERY_STATUS"} else
                      "android" if action in {"FLASHLIGHT", "DEVICE_STATUS"} else None),
        requires_web=requires_web,
        requires_memory=requires_memory,
        requires_tools=requires_tools,
        reasoning_level=ReasoningLevel.DEEP if requires_web or task_type == TaskType.MULTI_STEP else ReasoningLevel.SIMPLE,
        response_style=ResponseStyle.SOURCE_GROUNDED if requires_web else ResponseStyle.CONVERSATIONAL,
        detail_level=DetailLevel.HIGH if requires_web else DetailLevel.MEDIUM,
        confidence=0.1 if ambiguous else (0.95 if request.strip() else 0.1),
        constraints=[],
        ambiguous=ambiguous,
        ambiguity_reason="The request lacks a resolvable referent or content." if ambiguous else None,
    )
