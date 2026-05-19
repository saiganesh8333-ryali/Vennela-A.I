"""
Event Types and Schemas for Vennela A.I Event Bus Architecture (Phase B)

This module defines all event types and their schemas for the pub/sub event bus system.
It enables decoupling of AI modules through an event-driven architecture.

Author: Vennela A.I Evolution
"""

import time
import logging
import json
from enum import Enum
from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Dict, Any, Type, Optional, List
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class EventType(Enum):
    """
    Enumeration of all event types in the Vennela A.I system.
    
    These events enable communication between decoupled modules through
    a central pub/sub event bus.
    """
    # User Interaction Events
    USER_SPOKE = "user_spoke"
    VOICE_DETECTED = "voice_detected"
    INTENT_DETECTED = "intent_detected"
    
    # Memory Events
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_FORGOTTEN = "memory_forgotten"
    
    # Mood and Personality Events
    MOOD_CHANGED = "mood_changed"
    PERSONALITY_ADAPTED = "personality_adapted"
    
    # Learning and Training Events
    LEARNING_TRIGGERED = "learning_triggered"
    MODEL_TRAINED = "model_trained"
    PATTERN_LEARNED = "pattern_learned"
    
    # Reward and Reinforcement Events
    REWARD_RECEIVED = "reward_received"
    FEEDBACK_COLLECTED = "feedback_collected"
    
    # Reflection and Analysis Events
    REFLECTION_STARTED = "reflection_started"
    REFLECTION_COMPLETED = "reflection_completed"
    ANALYSIS_COMPLETE = "analysis_complete"
    
    # Profile and Context Events
    PROFILE_UPDATED = "profile_updated"
    CONTEXT_CHANGED = "context_changed"
    
    # System Events
    SYSTEM_INITIALIZED = "system_initialized"
    SYSTEM_ERROR = "system_error"


@dataclass
class BaseEvent:
    """
    Base class for all events in the system.
    
    All events inherit from this base and include core metadata about
    when, where, and by whom the event was triggered.
    
    Attributes:
        event_type: The type of event (EventType enum)
        timestamp: Unix timestamp when event was created
        source: Module or component that triggered the event
        user_id: ID of the user associated with this event
        metadata: Additional key-value data specific to event type
    """
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    user_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate event after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """
        Validate that all required fields are properly set.
        
        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not isinstance(self.event_type, EventType):
            raise ValueError(f"event_type must be EventType enum, got {type(self.event_type)}")
        
        if not isinstance(self.timestamp, (int, float)) or self.timestamp <= 0:
            raise ValueError(f"timestamp must be positive number, got {self.timestamp}")
        
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError(f"source must be non-empty string, got {self.source}")
        
        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError(f"user_id must be non-empty string, got {self.user_id}")
        
        if not isinstance(self.metadata, dict):
            raise ValueError(f"metadata must be dict, got {type(self.metadata)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of the event
        """
        try:
            event_dict = asdict(self)
            event_dict['event_type'] = self.event_type.value
            event_dict['timestamp'] = float(self.timestamp)
            return event_dict
        except Exception as e:
            logger.error(f"Error converting event to dict: {e}", exc_info=True)
            raise
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEvent':
        """
        Create event from dictionary (deserialization).
        
        Args:
            data: Dictionary containing event data
            
        Returns:
            Event instance
            
        Raises:
            ValueError: If data is invalid or missing required fields
        """
        try:
            if isinstance(data.get('event_type'), str):
                data['event_type'] = EventType(data['event_type'])
            
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception as e:
            logger.error(f"Error creating event from dict: {e}", exc_info=True)
            raise ValueError(f"Invalid event data: {e}")
    
    def to_json(self) -> str:
        """
        Convert event to JSON string.
        
        Returns:
            JSON representation of the event
        """
        try:
            return json.dumps(self.to_dict())
        except Exception as e:
            logger.error(f"Error converting event to JSON: {e}", exc_info=True)
            raise
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BaseEvent':
        """
        Create event from JSON string.
        
        Args:
            json_str: JSON string containing event data
            
        Returns:
            Event instance
            
        Raises:
            ValueError: If JSON is invalid
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for event: {e}", exc_info=True)
            raise ValueError(f"Invalid JSON format: {e}")


@dataclass
class UserSpokeEvent(BaseEvent):
    """
    Event triggered when user provides input (text or voice).
    
    Attributes:
        user_message: The message provided by the user
        mood: User's detected emotional state
        intent: Detected intent of the user's message
    """
    event_type: EventType = field(default=EventType.USER_SPOKE, init=False)
    user_message: str = ""
    mood: Optional[str] = None
    intent: Optional[str] = None
    
    def validate(self) -> None:
        """Validate UserSpokeEvent specific fields."""
        super().validate()
        if not isinstance(self.user_message, str) or not self.user_message.strip():
            raise ValueError(f"user_message must be non-empty string, got {self.user_message}")


@dataclass
class MemoryCreatedEvent(BaseEvent):
    """
    Event triggered when a new memory is stored.
    
    Attributes:
        memory_type: Category of memory (semantic, episodic, skill, etc.)
        content: The actual memory content
        importance: Importance score (0-1)
    """
    event_type: EventType = field(default=EventType.MEMORY_CREATED, init=False)
    memory_type: str = ""
    content: str = ""
    importance: float = 0.5
    
    def validate(self) -> None:
        """Validate MemoryCreatedEvent specific fields."""
        super().validate()
        if not isinstance(self.memory_type, str) or not self.memory_type.strip():
            raise ValueError(f"memory_type must be non-empty string")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError(f"content must be non-empty string")
        if not isinstance(self.importance, (int, float)) or not (0 <= self.importance <= 1):
            raise ValueError(f"importance must be between 0 and 1, got {self.importance}")


@dataclass
class MemoryUpdatedEvent(BaseEvent):
    """
    Event triggered when an existing memory is updated.
    
    Attributes:
        memory_id: ID of the memory being updated
        old_content: Previous memory content
        new_content: Updated memory content
        update_reason: Reason for the update
    """
    event_type: EventType = field(default=EventType.MEMORY_UPDATED, init=False)
    memory_id: str = ""
    old_content: str = ""
    new_content: str = ""
    update_reason: str = ""
    
    def validate(self) -> None:
        """Validate MemoryUpdatedEvent specific fields."""
        super().validate()
        if not isinstance(self.memory_id, str) or not self.memory_id.strip():
            raise ValueError(f"memory_id must be non-empty string")


@dataclass
class MoodChangedEvent(BaseEvent):
    """
    Event triggered when user's detected mood changes.
    
    Attributes:
        old_mood: Previous mood state
        new_mood: Current mood state
        trigger: What caused the mood change
        intensity: Intensity of the mood (0-1)
    """
    event_type: EventType = field(default=EventType.MOOD_CHANGED, init=False)
    old_mood: str = ""
    new_mood: str = ""
    trigger: str = ""
    intensity: float = 0.5
    
    def validate(self) -> None:
        """Validate MoodChangedEvent specific fields."""
        super().validate()
        if not isinstance(self.old_mood, str):
            raise ValueError(f"old_mood must be string")
        if not isinstance(self.new_mood, str) or not self.new_mood.strip():
            raise ValueError(f"new_mood must be non-empty string")
        if not isinstance(self.intensity, (int, float)) or not (0 <= self.intensity <= 1):
            raise ValueError(f"intensity must be between 0 and 1")


@dataclass
class RewardReceivedEvent(BaseEvent):
    """
    Event triggered when the system receives positive feedback (reward).
    
    Attributes:
        reward_score: Numeric reward score
        reason: Reason for the reward
        action_taken: What action was rewarded
    """
    event_type: EventType = field(default=EventType.REWARD_RECEIVED, init=False)
    reward_score: float = 0.0
    reason: str = ""
    action_taken: str = ""
    
    def validate(self) -> None:
        """Validate RewardReceivedEvent specific fields."""
        super().validate()
        if not isinstance(self.reward_score, (int, float)):
            raise ValueError(f"reward_score must be numeric, got {type(self.reward_score)}")
        if not isinstance(self.reason, str):
            raise ValueError(f"reason must be string")


@dataclass
class LearningTriggeredEvent(BaseEvent):
    """
    Event triggered when a learning process is initiated.
    
    Attributes:
        learning_type: Type of learning (reinforcement, supervised, etc.)
        status: Current status of learning (started, in_progress, completed, failed)
        data_size: Amount of data used for learning
    """
    event_type: EventType = field(default=EventType.LEARNING_TRIGGERED, init=False)
    learning_type: str = ""
    status: str = "started"
    data_size: int = 0
    
    def validate(self) -> None:
        """Validate LearningTriggeredEvent specific fields."""
        super().validate()
        if not isinstance(self.learning_type, str) or not self.learning_type.strip():
            raise ValueError(f"learning_type must be non-empty string")
        valid_statuses = ["started", "in_progress", "completed", "failed"]
        if self.status not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got {self.status}")


@dataclass
class ReflectionStartedEvent(BaseEvent):
    """
    Event triggered when reflection process begins.
    
    Attributes:
        reflection_type: Type of reflection (self-assessment, pattern-analysis, etc.)
        context: Additional context for the reflection
    """
    event_type: EventType = field(default=EventType.REFLECTION_STARTED, init=False)
    reflection_type: str = ""
    context: str = ""
    
    def validate(self) -> None:
        """Validate ReflectionStartedEvent specific fields."""
        super().validate()
        if not isinstance(self.reflection_type, str) or not self.reflection_type.strip():
            raise ValueError(f"reflection_type must be non-empty string")


@dataclass
class ReflectionCompletedEvent(BaseEvent):
    """
    Event triggered when reflection process completes.
    
    Attributes:
        findings: Key findings from reflection
        patterns_found: List of patterns discovered
        recommendations: Recommended actions based on reflection
    """
    event_type: EventType = field(default=EventType.REFLECTION_COMPLETED, init=False)
    findings: str = ""
    patterns_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def validate(self) -> None:
        """Validate ReflectionCompletedEvent specific fields."""
        super().validate()
        if not isinstance(self.patterns_found, list):
            raise ValueError(f"patterns_found must be list")
        if not isinstance(self.recommendations, list):
            raise ValueError(f"recommendations must be list")


@dataclass
class IntentDetectedEvent(BaseEvent):
    """
    Event triggered when user intent is detected.
    
    Attributes:
        intent_type: Category of detected intent
        confidence: Confidence score (0-1)
        alternatives: Alternative intent interpretations
    """
    event_type: EventType = field(default=EventType.INTENT_DETECTED, init=False)
    intent_type: str = ""
    confidence: float = 0.0
    alternatives: List[str] = field(default_factory=list)
    
    def validate(self) -> None:
        """Validate IntentDetectedEvent specific fields."""
        super().validate()
        if not isinstance(self.intent_type, str) or not self.intent_type.strip():
            raise ValueError(f"intent_type must be non-empty string")
        if not isinstance(self.confidence, (int, float)) or not (0 <= self.confidence <= 1):
            raise ValueError(f"confidence must be between 0 and 1")


@dataclass
class ProfileUpdatedEvent(BaseEvent):
    """
    Event triggered when user profile is updated.
    
    Attributes:
        profile_section: Which part of profile was updated
        changes: Dictionary of changes made
    """
    event_type: EventType = field(default=EventType.PROFILE_UPDATED, init=False)
    profile_section: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate ProfileUpdatedEvent specific fields."""
        super().validate()
        if not isinstance(self.profile_section, str) or not self.profile_section.strip():
            raise ValueError(f"profile_section must be non-empty string")


class EventRegistry:
    """
    Singleton registry for managing event types and their classes.
    
    Provides centralized access to all event type classes and enables
    dynamic event creation based on event type.
    """
    
    _instance: Optional['EventRegistry'] = None
    _events: Dict[EventType, Type[BaseEvent]] = {}
    
    def __new__(cls) -> 'EventRegistry':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """Initialize event registry with all event type mappings."""
        self._events = {
            EventType.USER_SPOKE: UserSpokeEvent,
            EventType.MEMORY_CREATED: MemoryCreatedEvent,
            EventType.MEMORY_UPDATED: MemoryUpdatedEvent,
            EventType.MOOD_CHANGED: MoodChangedEvent,
            EventType.REWARD_RECEIVED: RewardReceivedEvent,
            EventType.LEARNING_TRIGGERED: LearningTriggeredEvent,
            EventType.REFLECTION_STARTED: ReflectionStartedEvent,
            EventType.REFLECTION_COMPLETED: ReflectionCompletedEvent,
            EventType.INTENT_DETECTED: IntentDetectedEvent,
            EventType.PROFILE_UPDATED: ProfileUpdatedEvent,
        }
        logger.info(f"EventRegistry initialized with {len(self._events)} event types")
    
    def get_event_class(self, event_type: EventType) -> Type[BaseEvent]:
        """
        Get the event class for a specific event type.
        
        Args:
            event_type: The event type to look up
            
        Returns:
            The event class associated with this type
            
        Raises:
            ValueError: If event type is not registered
        """
        if event_type not in self._events:
            logger.error(f"Unknown event type: {event_type}")
            raise ValueError(f"Unknown event type: {event_type}")
        return self._events[event_type]
    
    def create_event(self, event_type: EventType, **kwargs) -> BaseEvent:
        """
        Factory method to create an event of the specified type.
        
        Args:
            event_type: The type of event to create
            **kwargs: Arguments to pass to the event constructor
            
        Returns:
            An instance of the appropriate event class
            
        Raises:
            ValueError: If event type is not registered
        """
        try:
            event_class = self.get_event_class(event_type)
            event = event_class(**kwargs)
            logger.debug(f"Created event: {event_type.value}")
            return event
        except Exception as e:
            logger.error(f"Error creating event of type {event_type}: {e}", exc_info=True)
            raise
    
    def list_event_types(self) -> List[str]:
        """
        Get list of all registered event type names.
        
        Returns:
            List of event type value strings
        """
        return [event_type.value for event_type in self._events.keys()]
    
    def get_all_event_classes(self) -> Dict[EventType, Type[BaseEvent]]:
        """
        Get mapping of all event types to their classes.
        
        Returns:
            Dictionary mapping EventType to event class
        """
        return dict(self._events)


# Singleton instance
event_registry = EventRegistry()


def get_event_class(event_type: EventType) -> Type[BaseEvent]:
    """
    Convenience function to get event class from registry.
    
    Args:
        event_type: The event type to look up
        
    Returns:
        The event class
    """
    return event_registry.get_event_class(event_type)


def create_event(event_type: EventType, **kwargs) -> BaseEvent:
    """
    Convenience function to create an event.
    
    Args:
        event_type: Type of event to create
        **kwargs: Event data
        
    Returns:
        Created event instance
    """
    return event_registry.create_event(event_type, **kwargs)


def list_all_event_types() -> List[str]:
    """
    Get list of all available event types.
    
    Returns:
        List of event type names
    """
    return event_registry.list_event_types()


if __name__ == "__main__":
    # Configure logging for demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Demo: Create various events
    print("=== Vennela A.I Event Types Demo ===\n")
    
    # Create a UserSpokeEvent
    user_event = UserSpokeEvent(
        user_message="Hello, how are you today?",
        mood="happy",
        intent="greeting",
        source="voice_module",
        user_id="user_123"
    )
    print(f"UserSpokeEvent created:\n{user_event}\n")
    print(f"JSON: {user_event.to_json()}\n")
    
    # Create a MemoryCreatedEvent
    memory_event = MemoryCreatedEvent(
        memory_type="episodic",
        content="User preferences: likes coffee in the morning",
        importance=0.8,
        source="memory_module",
        user_id="user_123"
    )
    print(f"MemoryCreatedEvent created:\n{memory_event}\n")
    
    # Create a MoodChangedEvent
    mood_event = MoodChangedEvent(
        old_mood="neutral",
        new_mood="happy",
        trigger="received positive feedback",
        intensity=0.7,
        source="mood_detector",
        user_id="user_123"
    )
    print(f"MoodChangedEvent created:\n{mood_event}\n")
    
    # Use event registry
    print("=== Event Registry Demo ===\n")
    print(f"Available event types: {list_all_event_types()}\n")
    
    # Create event via registry
    reward_event = create_event(
        EventType.REWARD_RECEIVED,
        reward_score=10.0,
        reason="Helpful response",
        action_taken="answered_question",
        source="reinforcement_module",
        user_id="user_123"
    )
    print(f"Created via registry:\n{reward_event}\n")
    
    # Test deserialization
    json_str = reward_event.to_json()
    deserialized = RewardReceivedEvent.from_json(json_str)
    print(f"Deserialized event: {deserialized}\n")
    
    print("=== Demo Complete ===")
