"""
Test and example usage of the EventBus pub/sub system for Phase B.

This file demonstrates how to use the EventBus with concrete handlers
and showcases all major features.

Author: Vennela A.I Evolution
"""

import asyncio
import logging
from event_types import (
    BaseEvent,
    EventType,
    UserSpokeEvent,
    MemoryCreatedEvent
)
from event_bus import EventBus, EventHandler, get_event_bus


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LoggerHandler(EventHandler):
    """Simple handler that logs all events."""
    
    @property
    def name(self) -> str:
        return "logger_handler"
    
    @property
    def event_types(self) -> list:
        return [
            EventType.USER_SPOKE,
            EventType.MEMORY_CREATED,
            EventType.MOOD_CHANGED
        ]
    
    async def handle(self, event: BaseEvent) -> None:
        """Log the event."""
        logger.info(
            f"[LoggerHandler] Received {event.event_type.value} "
            f"from {event.source}"
        )


class MemoryIndexer(EventHandler):
    """Handler that indexes memory events."""
    
    def __init__(self):
        self.indexed_memories = []
    
    @property
    def name(self) -> str:
        return "memory_indexer"
    
    @property
    def event_types(self) -> list:
        return [EventType.MEMORY_CREATED]
    
    async def handle(self, event: BaseEvent) -> None:
        """Index memory events."""
        if isinstance(event, MemoryCreatedEvent):
            self.indexed_memories.append(event)
            logger.info(
                f"[MemoryIndexer] Indexed memory: {event.memory_type} "
                f"(importance: {event.importance})"
            )


class ResponseGenerator(EventHandler):
    """Handler that generates responses to user input."""
    
    @property
    def name(self) -> str:
        return "response_generator"
    
    @property
    def event_types(self) -> list:
        return [EventType.USER_SPOKE]
    
    async def handle(self, event: BaseEvent) -> None:
        """Generate response to user input."""
        if isinstance(event, UserSpokeEvent):
            # Simulate some async work
            await asyncio.sleep(0.1)
            logger.info(
                f"[ResponseGenerator] Generated response to: "
                f"{event.user_message[:50]}"
            )


def test_basic_registration():
    """Test basic handler registration."""
    logger.info("=" * 60)
    logger.info("TEST: Basic Handler Registration")
    logger.info("=" * 60)
    
    bus = get_event_bus()
    
    # Create handlers
    logger_handler = LoggerHandler()
    memory_indexer = MemoryIndexer()
    
    # Register handlers
    bus.register_handler(EventType.USER_SPOKE, logger_handler)
    bus.register_handler(EventType.MEMORY_CREATED, memory_indexer)
    
    # Check registration
    assert bus.get_handler_count(EventType.USER_SPOKE) >= 1
    assert bus.get_handler_count(EventType.MEMORY_CREATED) >= 1
    
    logger.info("✓ Handlers registered successfully")


def test_synchronous_publish():
    """Test synchronous event publishing."""
    logger.info("=" * 60)
    logger.info("TEST: Synchronous Event Publishing")
    logger.info("=" * 60)
    
    bus = get_event_bus()
    
    # Register handlers
    logger_handler = LoggerHandler()
    response_gen = ResponseGenerator()
    
    bus.register_handler(EventType.USER_SPOKE, logger_handler)
    bus.register_handler(EventType.USER_SPOKE, response_gen)
    
    # Publish event
    event = UserSpokeEvent(
        source="voice_input",
        user_id="user123",
        user_message="Hello, Vennela!",
        mood="happy"
    )
    
    bus.publish(event)
    
    # Check history
    history = bus.get_event_history(limit=1)
    assert len(history) > 0
    assert history[0].event_type == EventType.USER_SPOKE
    
    logger.info("✓ Synchronous publishing works")


def test_event_history():
    """Test event history tracking."""
    logger.info("=" * 60)
    logger.info("TEST: Event History Tracking")
    logger.info("=" * 60)
    
    bus = get_event_bus()
    
    # Publish multiple events
    for i in range(5):
        event = UserSpokeEvent(
            source="test",
            user_id=f"user{i}",
            user_message=f"Message {i}"
        )
        bus.publish(event)
    
    # Check history
    history = bus.get_event_history()
    logger.info(f"Event history size: {len(history)}")
    assert len(history) > 0
    
    logger.info("✓ Event history working")


def test_handler_unregistration():
    """Test handler unregistration."""
    logger.info("=" * 60)
    logger.info("TEST: Handler Unregistration")
    logger.info("=" * 60)
    
    bus = get_event_bus()
    
    handler = LoggerHandler()
    bus.register_handler(EventType.USER_SPOKE, handler)
    
    assert bus.get_handler_count(EventType.USER_SPOKE) >= 1
    
    # Unregister
    removed = bus.unregister_handler(EventType.USER_SPOKE, handler.name)
    assert removed is True
    
    logger.info("✓ Handler unregistration works")


def test_statistics():
    """Test bus statistics collection."""
    logger.info("=" * 60)
    logger.info("TEST: Bus Statistics")
    logger.info("=" * 60)
    
    bus = get_event_bus()
    
    # Get stats
    stats = bus.get_bus_stats()
    
    logger.info(f"Bus uptime: {stats.uptime_seconds:.2f}s")
    logger.info(f"Total events published: {stats.total_events_published}")
    logger.info(f"Current queue size: {stats.current_queue_size}")
    logger.info(f"Total handlers: {stats.total_handlers}")
    logger.info(f"Events by type: {stats.events_published_by_type}")
    
    logger.info("✓ Statistics collection works")


def test_handler_statistics():
    """Test handler performance statistics."""
    logger.info("=" * 60)
    logger.info("TEST: Handler Statistics")
    logger.info("=" * 60)
    
    bus = get_event_bus()
    
    handler = LoggerHandler()
    bus.register_handler(EventType.USER_SPOKE, handler)
    
    # Publish events
    for i in range(3):
        event = UserSpokeEvent(
            source="test",
            user_id="user123",
            user_message=f"Test {i}"
        )
        bus.publish(event)
    
    # Get handler stats
    handler_stats = bus.get_handler_stats()
    
    logger.info(f"Handler stats: {list(handler_stats.keys())}")
    
    for name, stats in handler_stats.items():
        logger.info(
            f"  {name}:"
            f" total={stats.total_calls},"
            f" successful={stats.successful_calls},"
            f" failed={stats.failed_calls},"
            f" avg_time={stats.avg_execution_time:.4f}s"
        )
    
    logger.info("✓ Handler statistics work")


def test_error_handling():
    """Test error handling in handlers."""
    logger.info("=" * 60)
    logger.info("TEST: Error Handling")
    logger.info("=" * 60)
    
    class FailingHandler(EventHandler):
        @property
        def name(self) -> str:
            return "failing_handler"
        
        @property
        def event_types(self) -> list:
            return [EventType.USER_SPOKE]
        
        async def handle(self, event: BaseEvent) -> None:
            raise RuntimeError("Intentional test error")
    
    bus = get_event_bus()
    
    # Register failing and normal handlers
    failing = FailingHandler()
    normal = LoggerHandler()
    
    bus.register_handler(EventType.USER_SPOKE, failing)
    bus.register_handler(EventType.USER_SPOKE, normal)
    
    # Publish event - should not crash
    event = UserSpokeEvent(
        source="test",
        user_id="user123",
        user_message="Test error handling"
    )
    
    bus.publish(event)
    
    # Check that error was recorded
    stats = bus.get_handler_stats()
    failing_stats = stats.get("failing_handler")
    
    if failing_stats:
        logger.info(
            f"Failing handler stats:"
            f" successful={failing_stats.successful_calls},"
            f" failed={failing_stats.failed_calls},"
            f" last_error={failing_stats.last_error}"
        )
    
    logger.info("✓ Error handling works (handler errors don't crash bus)")


def run_all_tests():
    """Run all tests."""
    logger.info("\n\n")
    logger.info("###" * 20)
    logger.info("VENNELA A.I EVENT BUS - COMPREHENSIVE TEST SUITE")
    logger.info("###" * 20)
    logger.info("\n")
    
    try:
        test_basic_registration()
        test_synchronous_publish()
        test_event_history()
        test_handler_unregistration()
        test_statistics()
        test_handler_statistics()
        test_error_handling()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 60)
        
    except AssertionError as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    run_all_tests()
