"""
Voice Response Generator - Phase D
Text-to-speech and response generation for voice output
"""

import asyncio
import logging
import time
import hashlib
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class VoiceGender(Enum):
    """Available voice genders."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class SpeechRate(Enum):
    """Speech rate options."""
    SLOW = 0.7
    NORMAL = 1.0
    FAST = 1.3


@dataclass
class ResponseConfig:
    """Configuration for voice response generation."""
    voice_gender: VoiceGender = VoiceGender.FEMALE
    speech_rate: float = 1.0
    pitch: float = 1.0
    volume: float = 0.8
    max_response_length: int = 2000  # characters
    cache_ttl_minutes: int = 5
    enable_emotion_in_voice: bool = True


@dataclass
class GeneratedResponse:
    """Result from response generation."""
    audio_bytes: Optional[bytes] = None
    text: str = ""
    duration_ms: float = 0.0
    generation_time_ms: float = 0.0
    was_cached: bool = False
    voice_config: Optional[ResponseConfig] = None


class ResponseCacheManager:
    """Manages TTS response caching."""
    
    def __init__(self, ttl_minutes: int = 5, max_cache_size: int = 1000):
        """Initialize cache manager.
        
        Args:
            ttl_minutes: Cache time-to-live in minutes
            max_cache_size: Maximum number of cached responses
        """
        self.ttl_minutes = ttl_minutes
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, Tuple[bytes, datetime]] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_size_bytes": 0,
        }
    
    def _get_cache_key(self, text: str, config: ResponseConfig) -> str:
        """Generate cache key for response.
        
        Args:
            text: Response text
            config: Response configuration
            
        Returns:
            Cache key hash
        """
        key_str = f"{text}:{config.voice_gender.value}:{config.speech_rate}:{config.pitch}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, text: str, config: ResponseConfig) -> Optional[bytes]:
        """Get cached audio bytes.
        
        Args:
            text: Response text
            config: Response configuration
            
        Returns:
            Cached audio bytes or None
        """
        key = self._get_cache_key(text, config)
        
        if key in self.cache:
            audio_bytes, cached_time = self.cache[key]
            age_minutes = (datetime.now() - cached_time).total_seconds() / 60
            
            if age_minutes < self.ttl_minutes:
                self.stats["hits"] += 1
                logger.debug(f"Cache hit for response (age: {age_minutes:.1f}min)")
                return audio_bytes
            else:
                # Expired
                del self.cache[key]
        
        self.stats["misses"] += 1
        return None
    
    def set(self, text: str, config: ResponseConfig, audio_bytes: bytes) -> bool:
        """Cache audio bytes.
        
        Args:
            text: Response text
            config: Response configuration
            audio_bytes: Generated audio
            
        Returns:
            True if cached successfully
        """
        if len(self.cache) >= self.max_cache_size:
            logger.warning(f"Cache full, evicting oldest entry")
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        key = self._get_cache_key(text, config)
        self.cache[key] = (audio_bytes, datetime.now())
        self.stats["total_size_bytes"] += len(audio_bytes)
        logger.debug(f"Cached response ({len(audio_bytes)} bytes)")
        return True
    
    def clear(self) -> None:
        """Clear all cached responses."""
        self.cache.clear()
        self.stats["total_size_bytes"] = 0
        logger.info("Response cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        hit_rate = 0.0
        total = self.stats["hits"] + self.stats["misses"]
        if total > 0:
            hit_rate = self.stats["hits"] / total
        
        return {
            **self.stats,
            "cached_responses": len(self.cache),
            "max_size": self.max_cache_size,
            "hit_rate": hit_rate,
        }


class VoiceResponseGenerator:
    """Main voice response generation engine."""
    
    def __init__(self, config: Optional[ResponseConfig] = None):
        """Initialize response generator.
        
        Args:
            config: ResponseConfig with voice settings
        """
        self.config = config or ResponseConfig()
        self.cache = ResponseCacheManager(
            ttl_minutes=self.config.cache_ttl_minutes,
            max_cache_size=1000
        )
        self.stats = {
            "total_generations": 0,
            "cached_generations": 0,
            "failed_generations": 0,
            "avg_generation_time_ms": 0.0,
            "total_bytes_generated": 0,
        }
        logger.info(f"Voice response generator initialized: {self.config.voice_gender.value} voice")
    
    def generate_speech(self, text: str, emotion: Optional[str] = None) -> GeneratedResponse:
        """Generate speech from text.
        
        Args:
            text: Text to convert to speech
            emotion: Optional emotion context (happy, sad, neutral, etc.)
            
        Returns:
            GeneratedResponse with audio and metadata
        """
        start_time = time.time()
        
        # Validate input
        if not text or len(text) == 0:
            logger.warning("Empty text provided to generate_speech")
            return GeneratedResponse(text=text)
        
        if len(text) > self.config.max_response_length:
            logger.warning(f"Text truncated from {len(text)} to {self.config.max_response_length} chars")
            text = text[:self.config.max_response_length]
        
        # Check cache
        cached_audio = self.cache.get(text, self.config)
        if cached_audio:
            generation_time = (time.time() - start_time) * 1000
            self.stats["cached_generations"] += 1
            return GeneratedResponse(
                audio_bytes=cached_audio,
                text=text,
                duration_ms=len(cached_audio) / (self.config.sample_rate * 2),  # Estimate
                generation_time_ms=generation_time,
                was_cached=True,
                voice_config=self.config,
            )
        
        # Generate new speech
        try:
            audio_bytes = self._synthesize_speech(text, emotion)
            generation_time = (time.time() - start_time) * 1000
            
            # Cache result
            self.cache.set(text, self.config, audio_bytes)
            
            # Update stats
            self.stats["total_generations"] += 1
            self.stats["total_bytes_generated"] += len(audio_bytes)
            duration_ms = len(audio_bytes) / (self.config.sample_rate * 2)
            
            return GeneratedResponse(
                audio_bytes=audio_bytes,
                text=text,
                duration_ms=duration_ms,
                generation_time_ms=generation_time,
                was_cached=False,
                voice_config=self.config,
            )
        
        except Exception as e:
            logger.error(f"Failed to generate speech: {e}")
            self.stats["failed_generations"] += 1
            return GeneratedResponse(text=text)
    
    def _synthesize_speech(self, text: str, emotion: Optional[str] = None) -> bytes:
        """Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            emotion: Optional emotion context
            
        Returns:
            Audio bytes (mock implementation)
        """
        # Mock TTS implementation - in production, would call Gemini Live or similar
        # For now, return simulated audio data
        
        # Estimate duration based on text length and speech rate
        words = len(text.split())
        words_per_second = 150 / self.config.speech_rate  # Average speaking pace
        duration_seconds = max(0.5, words / words_per_second)
        
        # Generate mock audio data
        sample_count = int(duration_seconds * 16000)
        audio_bytes = bytes([0] * (sample_count * 2))  # 16-bit samples
        
        logger.debug(f"Generated mock speech: {len(audio_bytes)} bytes, {duration_seconds:.2f}s")
        return audio_bytes
    
    def update_config(self, config: ResponseConfig) -> None:
        """Update voice configuration.
        
        Args:
            config: New ResponseConfig
        """
        self.config = config
        logger.info(f"Voice config updated: {config.voice_gender.value} voice")
    
    def get_voice_config(self) -> ResponseConfig:
        """Get current voice configuration."""
        return self.config
    
    def get_stats(self) -> dict:
        """Get generation statistics."""
        return self.stats.copy()
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    @property
    def sample_rate(self) -> int:
        """Get audio sample rate."""
        return 16000


_response_generator_instance: Optional[VoiceResponseGenerator] = None


def get_response_generator(config: Optional[ResponseConfig] = None) -> VoiceResponseGenerator:
    """Get singleton response generator instance.
    
    Args:
        config: Optional config for initialization
        
    Returns:
        VoiceResponseGenerator singleton instance
    """
    global _response_generator_instance
    if _response_generator_instance is None:
        _response_generator_instance = VoiceResponseGenerator(config)
    return _response_generator_instance
