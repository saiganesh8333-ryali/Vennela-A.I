"""
Voice Streaming Engine - Phase D
Audio streaming and buffering for real-time voice interaction
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Deque
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class StreamingState(Enum):
    """States for audio streaming."""
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class StreamingConfig:
    """Configuration for audio streaming."""
    sample_rate: int = 16000  # Hz
    chunk_size: int = 1024  # samples
    channels: int = 1  # mono
    buffer_size: int = 100  # max chunks
    timeout_seconds: float = 30.0
    auto_stop_silence_duration_ms: int = 2000


@dataclass
class StreamStats:
    """Statistics for audio stream."""
    total_chunks: int = 0
    total_bytes: int = 0
    uptime_seconds: float = 0.0
    buffer_level: int = 0
    max_buffer_level: int = 0
    chunks_per_second: float = 0.0


class BufferedAudioQueue:
    """Thread-safe audio buffer using deque."""
    
    def __init__(self, max_size: int = 100):
        """Initialize audio queue.
        
        Args:
            max_size: Maximum number of chunks to buffer
        """
        self.max_size = max_size
        self.queue: Deque[bytes] = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.event = asyncio.Event()
        self.stats = {
            "chunks_added": 0,
            "chunks_removed": 0,
            "overflow_events": 0,
        }
    
    def put(self, chunk: bytes) -> bool:
        """Add audio chunk to queue.
        
        Args:
            chunk: Audio data bytes
            
        Returns:
            True if added, False if queue full
        """
        with self.lock:
            if len(self.queue) >= self.max_size:
                self.stats["overflow_events"] += 1
                logger.warning(f"Audio queue overflow (capacity: {self.max_size})")
                return False
            
            self.queue.append(chunk)
            self.stats["chunks_added"] += 1
            return True
    
    def get(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Get audio chunk from queue.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Audio chunk or None if queue empty
        """
        with self.lock:
            if self.queue:
                chunk = self.queue.popleft()
                self.stats["chunks_removed"] += 1
                return chunk
        return None
    
    def get_all(self) -> list:
        """Get all chunks and clear queue.
        
        Returns:
            List of all buffered chunks
        """
        with self.lock:
            chunks = list(self.queue)
            self.queue.clear()
            return chunks
    
    def size(self) -> int:
        """Get current queue size."""
        with self.lock:
            return len(self.queue)
    
    def clear(self) -> None:
        """Clear all buffered chunks."""
        with self.lock:
            self.queue.clear()
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self.lock:
            return {
                **self.stats,
                "current_size": len(self.queue),
                "max_size": self.max_size,
            }


class VoiceStreamingEngine:
    """Main voice streaming engine."""
    
    def __init__(self, config: Optional[StreamingConfig] = None):
        """Initialize streaming engine.
        
        Args:
            config: StreamingConfig with streaming parameters
        """
        self.config = config or StreamingConfig()
        self.state = StreamingState.IDLE
        self.buffer = BufferedAudioQueue(self.config.buffer_size)
        self.lock = threading.RLock()
        
        self.start_time: Optional[float] = None
        self.stream_stats = StreamStats()
        self.last_chunk_time: Optional[float] = None
        
        logger.info(f"Voice streaming engine initialized: {self.config.sample_rate}Hz, {self.config.chunk_size} samples/chunk")
    
    def start_stream(self) -> bool:
        """Start audio streaming.
        
        Returns:
            True if started successfully
        """
        with self.lock:
            if self.state != StreamingState.IDLE:
                logger.warning(f"Cannot start stream: already in {self.state.value} state")
                return False
            
            self.state = StreamingState.STREAMING
            self.start_time = time.time()
            self.buffer.clear()
            self.stream_stats = StreamStats()
            logger.info("Audio stream started")
            return True
    
    def stop_stream(self) -> bool:
        """Stop audio streaming.
        
        Returns:
            True if stopped successfully
        """
        with self.lock:
            if self.state == StreamingState.STOPPED:
                logger.warning("Stream already stopped")
                return False
            
            self.state = StreamingState.STOPPED
            logger.info(f"Audio stream stopped. Stats: {self.stream_stats}")
            return True
    
    def pause_stream(self) -> bool:
        """Pause audio streaming.
        
        Returns:
            True if paused successfully
        """
        with self.lock:
            if self.state != StreamingState.STREAMING:
                logger.warning(f"Cannot pause: stream in {self.state.value} state")
                return False
            
            self.state = StreamingState.PAUSED
            logger.info("Audio stream paused")
            return True
    
    def resume_stream(self) -> bool:
        """Resume paused audio stream.
        
        Returns:
            True if resumed successfully
        """
        with self.lock:
            if self.state != StreamingState.PAUSED:
                logger.warning(f"Cannot resume: stream in {self.state.value} state")
                return False
            
            self.state = StreamingState.STREAMING
            logger.info("Audio stream resumed")
            return True
    
    def read_chunk(self) -> Optional[bytes]:
        """Read next audio chunk from buffer.
        
        Returns:
            Audio chunk or None if buffer empty
        """
        if self.state not in (StreamingState.STREAMING, StreamingState.PAUSED):
            return None
        
        chunk = self.buffer.get()
        if chunk:
            self.last_chunk_time = time.time()
            return chunk
        
        return None
    
    def write_chunk(self, chunk: bytes) -> bool:
        """Write audio chunk to buffer.
        
        Args:
            chunk: Audio data to buffer
            
        Returns:
            True if successfully buffered
        """
        if self.state != StreamingState.STREAMING:
            logger.debug(f"Not buffering chunk: stream in {self.state.value} state")
            return False
        
        success = self.buffer.put(chunk)
        if success:
            with self.lock:
                self.stream_stats.total_chunks += 1
                self.stream_stats.total_bytes += len(chunk)
                self.stream_stats.buffer_level = self.buffer.size()
                self.stream_stats.max_buffer_level = max(
                    self.stream_stats.max_buffer_level,
                    self.stream_stats.buffer_level
                )
        
        return success
    
    def get_buffer_level(self) -> int:
        """Get current buffer fill level."""
        return self.buffer.size()
    
    def get_state(self) -> StreamingState:
        """Get current streaming state."""
        with self.lock:
            return self.state
    
    def get_stats(self) -> dict:
        """Get comprehensive streaming statistics."""
        with self.lock:
            uptime = 0.0
            if self.start_time:
                uptime = time.time() - self.start_time
            
            return {
                "state": self.state.value,
                "total_chunks": self.stream_stats.total_chunks,
                "total_bytes": self.stream_stats.total_bytes,
                "uptime_seconds": uptime,
                "buffer_level": self.buffer.size(),
                "max_buffer_level": self.stream_stats.max_buffer_level,
                "buffer_stats": self.buffer.get_stats(),
            }


_streaming_engine_instance: Optional[VoiceStreamingEngine] = None


def get_streaming_engine(config: Optional[StreamingConfig] = None) -> VoiceStreamingEngine:
    """Get singleton streaming engine instance.
    
    Args:
        config: Optional config for initialization
        
    Returns:
        VoiceStreamingEngine singleton instance
    """
    global _streaming_engine_instance
    if _streaming_engine_instance is None:
        _streaming_engine_instance = VoiceStreamingEngine(config)
    return _streaming_engine_instance
