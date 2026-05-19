"""
Event Bus (Pub/Sub System) for Vennela A.I Event-Driven Architecture (Phase B)

This module provides a thread-safe, production-ready pub/sub event bus that enables
loose coupling between AI modules. It supports both synchronous and asynchronous event
handling with comprehensive monitoring, error handling, and performance metrics.

Key Features:
- Thread-safe handler registration and publishing
- Async event processing with background queue
- Event history tracking with bounded memory
- Priority-based event handling
- Comprehensive metrics and statistics
- Graceful error handling with logging

Author: Vennela A.I Evolution
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from event_types import BaseEvent, EventType

logger = logging.getLogger(__name__)


@dataclass
class EventPriority:
    """Priority levels for events."""
    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class HandlerStats:
    """Statistics for a single event handler."""
    handler_name: str
    event_types: List[EventType]
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_execution_time: float = 0.0
    total_execution_time: float = 0.0
    last_execution_time: Optional[float] = None
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None


@dataclass
class BusStats:
    """Statistics for the entire event bus."""
    total_events_published: int = 0
    total_events_queued: int = 0
    events_published_by_type: Dict[str, int] = field(default_factory=dict)
    current_queue_size: int = 0
    max_queue_size: int = 0
    total_handlers: int = 0
    handlers_by_event_type: Dict[str, int] = field(default_factory=dict)
    uptime_seconds: float = 0.0


class EventHandler(ABC):
    """
    Abstract base class for all event handlers.
    
    Handlers must implement the async handle method and provide metadata
    about which event types they process.
    """
    
    @abstractmethod
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle an event asynchronously.
        
        Args:
            event: The event to handle
            
        Raises:
            Exception: May raise any exception, which will be caught and logged
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this handler."""
        pass
    
    @property
    @abstractmethod
    def event_types(self) -> List[EventType]:
        """List of event types this handler subscribes to."""
        pass


class EventBus:
    """
    Thread-safe pub/sub event bus for Vennela A.I.
    
    This is a singleton that manages event publication and subscription.
    It supports both synchronous and asynchronous event processing with
    comprehensive metrics, error handling, and memory management.
    
    Attributes:
        _handlers: Dict mapping EventType -> List[EventHandler]
        _event_history: Bounded deque of recent events
        _lock: Threading lock for thread-safety
        _event_queue: Async queue for background event processing
        _handler_stats: Performance metrics per handler
        _start_time: When the bus was created
    """
    
    _instance: Optional['EventBus'] = None
    _instance_lock = threading.Lock()
    
    def __init__(self, max_history: int = 1000, max_queue_size: int = 10000):
        """
        Initialize the EventBus.
        
        Args:
            max_history: Maximum number of events to keep in history
            max_queue_size: Maximum size of the async event queue
        """
        self._handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._event_history: deque = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._handler_stats: Dict[str, HandlerStats] = {}
        self._start_time = time.time()
        self._max_queue_size = max_queue_size
        self._max_history = max_history
        
        logger.info(
            f"EventBus initialized with max_history={max_history}, "
            f"max_queue_size={max_queue_size}"
        )
    
    @classmethod
    def get_instance(cls, max_history: int = 1000) -> 'EventBus':
        """
        Get or create the singleton EventBus instance.
        
        Args:
            max_history: Max history size (only used on first call)
            
        Returns:
            The EventBus singleton instance
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(max_history=max_history)
        return cls._instance
    
    def register_handler(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """
        Register a handler for a specific event type.
        
        Args:
            event_type: The event type to subscribe to
            handler: The handler to register
            
        Raises:
            ValueError: If event_type is invalid or handler is None
            
        Example:
            bus.register_handler(EventType.USER_SPOKE, my_handler)
        """
        if not isinstance(event_type, EventType):
            raise ValueError(f"event_type must be EventType enum, got {type(event_type)}")
        
        if handler is None:
            raise ValueError("handler cannot be None")
        
        with self._lock:
            # Check if handler already registered for this event type
            if any(h.name == handler.name for h in self._handlers[event_type]):
                logger.warning(
                    f"Handler '{handler.name}' already registered for {event_type.value}"
                )
                return
            
            self._handlers[event_type].append(handler)
            
            # Initialize stats if new handler
            if handler.name not in self._handler_stats:
                self._handler_stats[handler.name] = HandlerStats(
                    handler_name=handler.name,
                    event_types=handler.event_types
                )
            
            logger.debug(
                f"Registered handler '{handler.name}' for event type {event_type.value}"
            )
    
    def unregister_handler(
        self,
        event_type: EventType,
        handler_name: str
    ) -> bool:
        """
        Unregister a handler from a specific event type.
        
        Args:
            event_type: The event type to unsubscribe from
            handler_name: The name of the handler to remove
            
        Returns:
            True if handler was removed, False if not found
            
        Example:
            bus.unregister_handler(EventType.USER_SPOKE, 'my_handler')
        """
        if not isinstance(event_type, EventType):
            raise ValueError(f"event_type must be EventType enum, got {type(event_type)}")
        
        with self._lock:
            handlers = self._handlers[event_type]
            original_count = len(handlers)
            
            # Remove handler(s) with matching name
            self._handlers[event_type] = [
                h for h in handlers if h.name != handler_name
            ]
            
            removed = original_count - len(self._handlers[event_type])
            
            if removed > 0:
                logger.debug(
                    f"Unregistered handler '{handler_name}' from {event_type.value}"
                )
            else:
                logger.debug(
                    f"Handler '{handler_name}' not found for {event_type.value}"
                )
            
            return removed > 0
    
    def get_handlers(self, event_type: EventType) -> List[EventHandler]:
        """
        Get all handlers subscribed to an event type.
        
        Args:
            event_type: The event type
            
        Returns:
            List of handlers (copy to avoid concurrent modification)
            
        Raises:
            ValueError: If event_type is invalid
        """
        if not isinstance(event_type, EventType):
            raise ValueError(f"event_type must be EventType enum, got {type(event_type)}")
        
        with self._lock:
            return list(self._handlers.get(event_type, []))
    
    def publish(self, event: BaseEvent, priority: int = EventPriority.NORMAL) -> None:
        """
        Publish an event synchronously to all registered handlers.
        
        This method calls all handlers sequentially in the current thread.
        Errors in handlers are logged but don't prevent other handlers from running.
        
        Args:
            event: The event to publish
            priority: Priority level (lower = higher priority, currently unused
                      but provided for future optimization)
            
        Raises:
            ValueError: If event is invalid
            
        Example:
            bus.publish(UserSpokeEvent(source='voice_input', user_id='user123',
                                       user_message='Hello'))
        """
        if not isinstance(event, BaseEvent):
            raise ValueError(f"event must be BaseEvent instance, got {type(event)}")
        
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            self._event_history.append(event)
        
        logger.debug(f"Publishing {event.event_type.value} to {len(handlers)} handlers")
        
        # Create async tasks and run them
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread
            logger.debug(
                "No event loop in current thread, creating new one for publish"
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run handlers concurrently
        tasks = [self._handle_event_safe(event, handler) for handler in handlers]
        if tasks:
            try:
                if not loop.is_running():
                    loop.run_until_complete(asyncio.gather(*tasks))
                else:
                    # If loop is already running, schedule as tasks
                    for task in tasks:
                        asyncio.ensure_future(task)
            except Exception as e:
                logger.error(f"Error during event publishing: {e}", exc_info=True)
    
    def publish_async(self, event: BaseEvent) -> Optional[asyncio.Task]:
        """
        Queue an event for asynchronous processing in the background.
        
        This method is non-blocking and returns immediately. The event
        is queued for later processing by drain_queue().
        
        Args:
            event: The event to publish asynchronously
            
        Returns:
            asyncio.Task or None if queue is full
            
        Raises:
            ValueError: If event is invalid
            
        Example:
            task = bus.publish_async(UserSpokeEvent(...))
        """
        if not isinstance(event, BaseEvent):
            raise ValueError(f"event must be BaseEvent instance, got {type(event)}")
        
        try:
            self._event_queue.put_nowait(event)
            logger.debug(
                f"Queued {event.event_type.value} (queue size: {self._event_queue.qsize()})"
            )
            return None
        except asyncio.QueueFull:
            logger.error(
                f"Event queue full! Dropping event {event.event_type.value}. "
                "Consider increasing max_queue_size."
            )
            return None
    
    async def drain_queue(self) -> int:
        """
        Process all queued events asynchronously.
        
        This should be called periodically in the event loop to process
        events that were queued via publish_async().
        
        Returns:
            Number of events processed
            
        Example:
            count = await bus.drain_queue()
            logger.info(f"Processed {count} queued events")
        """
        processed_count = 0
        
        try:
            while True:
                try:
                    event = self._event_queue.get_nowait()
                    self.publish(event)
                    processed_count += 1
                except asyncio.QueueEmpty:
                    break
        except Exception as e:
            logger.error(f"Error draining queue: {e}", exc_info=True)
        
        return processed_count
    
    async def _handle_event_safe(
        self,
        event: BaseEvent,
        handler: EventHandler
    ) -> None:
        """
        Safely execute a handler with error handling and metrics collection.
        
        Args:
            event: The event to handle
            handler: The handler to execute
        """
        start_time = time.time()
        handler_name = handler.name
        
        try:
            await handler.handle(event)
            
            # Update success metrics
            with self._lock:
                if handler_name in self._handler_stats:
                    stats = self._handler_stats[handler_name]
                    stats.successful_calls += 1
                    stats.total_calls += 1
            
            logger.debug(
                f"Handler '{handler_name}' successfully handled {event.event_type.value}"
            )
        
        except Exception as e:
            logger.error(
                f"Error in handler '{handler_name}' for {event.event_type.value}: {e}",
                exc_info=True
            )
            
            # Update error metrics
            with self._lock:
                if handler_name in self._handler_stats:
                    stats = self._handler_stats[handler_name]
                    stats.failed_calls += 1
                    stats.total_calls += 1
                    stats.last_error = str(e)
                    stats.last_error_time = time.time()
        
        finally:
            # Update execution time metrics
            execution_time = time.time() - start_time
            with self._lock:
                if handler_name in self._handler_stats:
                    stats = self._handler_stats[handler_name]
                    stats.last_execution_time = execution_time
                    stats.total_execution_time += execution_time
                    if stats.total_calls > 0:
                        stats.avg_execution_time = (
                            stats.total_execution_time / stats.total_calls
                        )
    
    def clear_history(self) -> None:
        """
        Clear all event history.
        
        Warning: This will delete all stored event history. Use with caution.
        """
        with self._lock:
            self._event_history.clear()
            logger.info("Event history cleared")
    
    def get_event_history(self, limit: Optional[int] = None) -> List[BaseEvent]:
        """
        Get recent events from history.
        
        Args:
            limit: Maximum number of events to return (None = all)
            
        Returns:
            List of events from most recent first
        """
        with self._lock:
            events = list(self._event_history)
        
        events.reverse()  # Most recent first
        
        if limit:
            events = events[:limit]
        
        return events
    
    def get_event_stats(self) -> Dict[str, int]:
        """
        Get statistics about events published.
        
        Returns:
            Dict with event counts by type
            
        Example:
            stats = bus.get_event_stats()
            # {'user_spoke': 42, 'mood_changed': 15, ...}
        """
        stats: Dict[str, int] = {}
        
        with self._lock:
            for event in self._event_history:
                event_type_str = event.event_type.value
                stats[event_type_str] = stats.get(event_type_str, 0) + 1
        
        return stats
    
    def get_handler_stats(self) -> Dict[str, HandlerStats]:
        """
        Get performance metrics for all handlers.
        
        Returns:
            Dict mapping handler name -> HandlerStats
            
        Example:
            stats = bus.get_handler_stats()
            for handler_name, stats in stats.items():
                print(f"{handler_name}: {stats.successful_calls} successful calls")
        """
        with self._lock:
            return dict(self._handler_stats)
    
    def get_bus_stats(self) -> BusStats:
        """
        Get comprehensive statistics about the event bus.
        
        Returns:
            BusStats object with all metrics
            
        Example:
            stats = bus.get_bus_stats()
            print(f"Total events: {stats.total_events_published}")
            print(f"Queue size: {stats.current_queue_size}")
        """
        with self._lock:
            uptime = time.time() - self._start_time
            
            # Count total handlers
            total_handlers = len(set(
                handler.name
                for handlers in self._handlers.values()
                for handler in handlers
            ))
            
            # Count handlers by event type
            handlers_by_type = {
                event_type.value: len(handlers)
                for event_type, handlers in self._handlers.items()
            }
            
            # Get event type counts
            event_stats = self.get_event_stats()
            
            return BusStats(
                total_events_published=len(self._event_history),
                total_events_queued=0,  # Would need tracking
                events_published_by_type=event_stats,
                current_queue_size=self._event_queue.qsize(),
                max_queue_size=self._max_queue_size,
                total_handlers=total_handlers,
                handlers_by_event_type=handlers_by_type,
                uptime_seconds=uptime
            )
    
    def get_handler_count(self, event_type: EventType) -> int:
        """
        Get the number of handlers registered for an event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            Number of handlers
            
        Raises:
            ValueError: If event_type is invalid
        """
        if not isinstance(event_type, EventType):
            raise ValueError(f"event_type must be EventType enum, got {type(event_type)}")
        
        with self._lock:
            return len(self._handlers.get(event_type, []))
    
    def get_all_handlers(self) -> Dict[EventType, List[EventHandler]]:
        """
        Get all registered handlers grouped by event type.
        
        Returns:
            Dict mapping EventType -> List[EventHandler]
        """
        with self._lock:
            return {
                event_type: list(handlers)
                for event_type, handlers in self._handlers.items()
            }
    
    def reset_stats(self) -> None:
        """Reset all handler statistics."""
        with self._lock:
            for stats in self._handler_stats.values():
                stats.total_calls = 0
                stats.successful_calls = 0
                stats.failed_calls = 0
                stats.avg_execution_time = 0.0
                stats.total_execution_time = 0.0
                stats.last_execution_time = None
                stats.last_error = None
                stats.last_error_time = None
            
            logger.info("Handler statistics reset")


def get_event_bus(max_history: int = 1000) -> EventBus:
    """
    Convenience function to get the EventBus singleton.
    
    Args:
        max_history: Max events to keep in history (only used on first call)
        
    Returns:
        The EventBus singleton instance
        
    Example:
        from event_bus import get_event_bus
        bus = get_event_bus()
        bus.register_handler(EventType.USER_SPOKE, my_handler)
        bus.publish(UserSpokeEvent(...))
    """
    return EventBus.get_instance(max_history=max_history)
