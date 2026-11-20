# Event Bus Documentation - Phase B

## Overview

The EventBus is the core pub/sub (publish/subscribe) system that enables loose coupling between Vennela A.I modules. It allows different components to communicate without knowing about each other directly, making the system scalable, maintainable, and testable.

## Architecture

### Key Components

1. **EventBus (Singleton)** - Central pub/sub coordinator
2. **EventHandler (ABC)** - Abstract base for all event handlers
3. **BaseEvent** - Base class for all events (from event_types.py)
4. **EventType** - Enum of all system events

### Design Philosophy

- **Loose Coupling**: Modules publish events without knowing who consumes them
- **Scalability**: Handlers can be added/removed dynamically
- **Non-Blocking**: Async support for background processing
- **Observable**: Complete metrics and history for monitoring
- **Safe**: Thread-safe with proper locking

## Core Features

### 1. Handler Registration

Register a handler to subscribe to specific event types:

```python
from event_bus import get_event_bus
from event_types import EventType

bus = get_event_bus()
bus.register_handler(EventType.USER_SPOKE, my_handler)
```

Features:
- Multiple handlers can subscribe to the same event
- Duplicate registrations are ignored
- Handlers are stored in a thread-safe dictionary

### 2. Event Publishing (Synchronous)

Publish events immediately to all registered handlers:

```python
from event_types import UserSpokeEvent

event = UserSpokeEvent(
    source="voice_input",
    user_id="user123",
    user_message="Hello Vennela!",
    mood="happy"
)

bus.publish(event)
```

Features:
- Calls all handlers concurrently using asyncio
- Errors in one handler don't affect others
- Comprehensive error logging
- Handler execution time tracked

### 3. Async Event Publishing

Queue events for background processing:

```python
# Queue the event (non-blocking)
task = bus.publish_async(event)

# Later, process the queue
processed = await bus.drain_queue()
```

Features:
- Non-blocking - returns immediately
- Events queued in bounded asyncio.Queue
- Process queue periodically in event loop

### 4. Event History

Track recent events:

```python
# Get last 10 events (most recent first)
recent = bus.get_event_history(limit=10)

# Clear history
bus.clear_history()
```

Features:
- Bounded deque (default 1000 events)
- Memory-efficient
- Useful for debugging and analysis

### 5. Statistics & Monitoring

#### Bus Statistics

```python
stats = bus.get_bus_stats()
print(f"Total events: {stats.total_events_published}")
print(f"Queue size: {stats.current_queue_size}")
print(f"Total handlers: {stats.total_handlers}")
print(f"Uptime: {stats.uptime_seconds}s")
```

#### Event Statistics

```python
event_stats = bus.get_event_stats()
# {'user_spoke': 42, 'mood_changed': 15, ...}
```

#### Handler Statistics

```python
handler_stats = bus.get_handler_stats()
for name, stats in handler_stats.items():
    print(f"{name}:")
    print(f"  Successful: {stats.successful_calls}")
    print(f"  Failed: {stats.failed_calls}")
    print(f"  Avg time: {stats.avg_execution_time}ms")
    print(f"  Last error: {stats.last_error}")
```

## Creating Custom Handlers

Implement the EventHandler abstract base class:

```python
from event_bus import EventHandler
from event_types import EventType, BaseEvent

class MyCustomHandler(EventHandler):
    @property
    def name(self) -> str:
        """Unique handler identifier."""
        return "my_custom_handler"
    
    @property
    def event_types(self) -> list:
        """Events this handler subscribes to."""
        return [EventType.USER_SPOKE, EventType.MOOD_CHANGED]
    
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle the event asynchronously.
        
        Exceptions are caught and logged automatically.
        """
        print(f"Handling {event.event_type.value}")
        
        # Do async work here
        await asyncio.sleep(0.1)
        
        # Update your system state
        self.process_event(event)
```

Register and use:

```python
handler = MyCustomHandler()
bus.register_handler(EventType.USER_SPOKE, handler)
```

## Thread Safety

The EventBus is fully thread-safe:

```python
# Safe to call from multiple threads
import threading

def publish_from_thread():
    event = UserSpokeEvent(...)
    bus.publish(event)  # Thread-safe!

threads = [
    threading.Thread(target=publish_from_thread)
    for _ in range(10)
]

for t in threads:
    t.start()

for t in threads:
    t.join()
```

Internal locking:
- `_lock`: Guards handler storage and statistics
- `_event_queue`: Thread-safe asyncio.Queue

## Exception Handling

Errors in handlers are gracefully handled:

```python
class BrokenHandler(EventHandler):
    async def handle(self, event: BaseEvent) -> None:
        raise ValueError("Something went wrong!")

bus.register_handler(EventType.USER_SPOKE, BrokenHandler())

# Publishing continues despite the error
bus.publish(UserSpokeEvent(...))  # Doesn't crash!

# Error is logged and recorded
stats = bus.get_handler_stats()
print(stats["broken_handler"].last_error)  # "Something went wrong!"
```

## Performance Considerations

### Event Queue Management

```python
# Check queue size
stats = bus.get_bus_stats()
print(f"Queue size: {stats.current_queue_size}")
print(f"Max size: {stats.max_queue_size}")

# If queue fills up, events are dropped with an error logged
# Increase max_queue_size if needed:
# bus = EventBus(max_queue_size=50000)
```

### History Management

```python
# Default history size: 1000 events
# Change when getting instance:
bus = get_event_bus(max_history=5000)

# Clear history to free memory
bus.clear_history()
```

### Handler Performance

```python
# Monitor slow handlers
for name, stats in bus.get_handler_stats().items():
    if stats.avg_execution_time > 1.0:  # > 1 second
        print(f"Slow handler: {name} ({stats.avg_execution_time}s avg)")
```

## Common Patterns

### Pattern 1: Event Publishing Pipeline

```python
# Voice input → Intent detection → Response generation
bus.register_handler(EventType.VOICE_DETECTED, voice_processor)
bus.register_handler(EventType.USER_SPOKE, intent_detector)
bus.register_handler(EventType.INTENT_DETECTED, response_generator)

# Trigger the chain
bus.publish(VoiceDetectedEvent(...))
```

### Pattern 2: Multi-Handler Aggregation

```python
# Multiple modules interested in memory events
bus.register_handler(EventType.MEMORY_CREATED, memory_indexer)
bus.register_handler(EventType.MEMORY_CREATED, memory_validator)
bus.register_handler(EventType.MEMORY_CREATED, memory_logger)

bus.publish(MemoryCreatedEvent(...))  # All three handle it
```

### Pattern 3: Error Recovery

```python
class ResilientHandler(EventHandler):
    async def handle(self, event: BaseEvent) -> None:
        try:
            await self.risky_operation()
        except TemporaryError:
            logger.warning("Temporary error, will retry")
        except PermanentError:
            logger.error("Permanent error, moving on")
            # Don't re-raise - prevent it from affecting other handlers
```

### Pattern 4: Background Processing

```python
# Publish immediately for critical handlers
bus.publish(UrgentEvent(...))

# Queue non-critical events for batch processing later
bus.publish_async(AnalyticsEvent(...))
bus.publish_async(LoggingEvent(...))

# In your event loop
async def process_background():
    count = await bus.drain_queue()
    logger.info(f"Processed {count} queued events")
```

## API Reference

### EventBus Methods

| Method | Description |
|--------|-------------|
| `register_handler(event_type, handler)` | Subscribe handler to event type |
| `unregister_handler(event_type, handler_name)` | Unsubscribe handler |
| `publish(event)` | Publish event synchronously |
| `publish_async(event)` | Queue event for async processing |
| `get_handlers(event_type)` | Get all handlers for event type |
| `get_handler_count(event_type)` | Count handlers for event type |
| `get_event_history(limit)` | Get recent events |
| `clear_history()` | Clear event history |
| `get_event_stats()` | Event count by type |
| `get_handler_stats()` | Performance metrics per handler |
| `get_bus_stats()` | Overall bus statistics |
| `reset_stats()` | Clear all statistics |

### EventHandler Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Unique handler identifier |
| `event_types` | List[EventType] | Event types to subscribe to |

### EventHandler Methods

| Method | Description |
|--------|-------------|
| `async handle(event)` | Handle an event |

## Error Codes & Logging

### Log Levels

- **DEBUG**: Handler registration/unregistration, event processing
- **INFO**: Bus initialization, statistics
- **WARNING**: Handler already registered, queue full
- **ERROR**: Handler execution errors, event processing errors

### Common Errors

```
ValueError: event_type must be EventType enum, got <class 'str'>
# → Pass EventType enum, not string

ValueError: handler cannot be None
# → Check that handler is instantiated

asyncio.QueueFull: Event queue full
# → Increase max_queue_size or drain queue more frequently

RuntimeError: No event loop in current thread
# → EventBus creates new loop if needed; ensure proper async context
```

## Testing

See `test_event_bus.py` for comprehensive examples:

```bash
python test_event_bus.py
```

Tests cover:
- Handler registration
- Event publishing
- Event history
- Statistics collection
- Error handling
- Thread safety (implicit)

## Integration Examples

### With Vennela A.I Modules

```python
# In your module initialization
from event_bus import get_event_bus
from event_types import EventType

class MyModule:
    def __init__(self):
        self.bus = get_event_bus()
        self.bus.register_handler(EventType.USER_SPOKE, self)
    
    async def handle(self, event):
        # Process the event
        result = self.process(event)
        
        # Publish result event
        self.bus.publish(ResultEvent(result))
```

## Future Enhancements

Potential improvements:

- Event filtering by handlers (e.g., subscribe to events with specific source)
- Persistent event store (database backend)
- Event replay capability
- Distributed event bus (multiple processes/machines)
- Event compression in history
- Handler priority/ordering
- Dead-letter queue for failed events

## Best Practices

1. ✅ Use unique, descriptive handler names
2. ✅ Keep handlers async-compatible
3. ✅ Log important events in handlers
4. ✅ Handle exceptions within handlers when appropriate
5. ✅ Monitor handler statistics regularly
6. ✅ Clear history periodically if memory is a concern
7. ✅ Use synchronous publish for critical paths
8. ✅ Use async publish for background work

## Troubleshooting

**Events not being handled:**
- Check that handler is registered: `bus.get_handlers(event_type)`
- Verify handler name is unique
- Check log for handler exceptions

**High memory usage:**
- Clear history: `bus.clear_history()`
- Reduce max_history size
- Monitor event_history size

**Slow event processing:**
- Check handler stats: `bus.get_handler_stats()`
- Profile slow handlers
- Consider using async publishing

**Queue filling up:**
- Drain queue more frequently
- Increase max_queue_size
- Reduce event publishing rate

## See Also

- `event_bus.py` - Source code
- `event_types.py` - Event definitions
- `test_event_bus.py` - Test suite and examples

---

**Author:** Vennela A.I Evolution  
**Version:** Phase B (Event Bus Architecture)  
**Last Updated:** 2024
