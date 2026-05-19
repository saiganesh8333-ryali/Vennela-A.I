"""
Voice Wakeword Detection Module - Phase D
Lightweight offline wakeword detection for Vennela A.I
"""

import re
import math
import asyncio
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class WakewordState(Enum):
    """States for wakeword detection."""
    LISTENING = "listening"
    DETECTED = "detected"
    PROCESSING = "processing"
    IDLE = "idle"


@dataclass
class WakewordConfig:
    """Configuration for wakeword detection."""
    primary_wakeword: str = "vennela"
    alternate_wakewords: List[str] = field(default_factory=list)
    detection_threshold: float = 0.85
    sensitivity: float = 0.9
    min_audio_duration_ms: int = 300
    max_false_positive_rate: float = 0.05


@dataclass
class WakewordDetectionResult:
    """Result from wakeword detection."""
    detected: bool
    confidence: float
    matched_wakeword: Optional[str] = None
    detection_time_ms: float = 0.0
    audio_snippet_duration_ms: float = 0.0


class WakewordDetector:
    """Main wakeword detector using keyword spotting."""
    
    def __init__(self, config: Optional[WakewordConfig] = None):
        """Initialize wakeword detector.
        
        Args:
            config: WakewordConfig with detection parameters
        """
        self.config = config or WakewordConfig()
        self.state = WakewordState.IDLE
        self.detection_stats = {
            "total_checks": 0,
            "detections": 0,
            "false_positives": 0,
            "avg_confidence": 0.0,
        }
        logger.info(f"Wakeword detector initialized with primary: {self.config.primary_wakeword}")
    
    def detect_wakeword(self, audio_text: str, confidence_scores: Optional[dict] = None) -> WakewordDetectionResult:
        """Detect wakeword in audio transcription.
        
        Args:
            audio_text: Transcribed text from audio
            confidence_scores: Optional confidence scores per word
            
        Returns:
            WakewordDetectionResult with detection status and confidence
        """
        self.detection_stats["total_checks"] += 1
        
        # Normalize input
        normalized_text = audio_text.lower().strip()
        
        # Check primary wakeword
        confidence = self._calculate_confidence(
            normalized_text,
            self.config.primary_wakeword,
            confidence_scores
        )
        
        if confidence >= self.config.detection_threshold:
            self.detection_stats["detections"] += 1
            logger.info(f"Wakeword detected: {self.config.primary_wakeword} (confidence: {confidence:.2f})")
            return WakewordDetectionResult(
                detected=True,
                confidence=confidence,
                matched_wakeword=self.config.primary_wakeword
            )
        
        # Check alternate wakewords
        for alt_wakeword in self.config.alternate_wakewords:
            alt_confidence = self._calculate_confidence(
                normalized_text,
                alt_wakeword,
                confidence_scores
            )
            
            if alt_confidence >= self.config.detection_threshold:
                self.detection_stats["detections"] += 1
                logger.info(f"Alternate wakeword detected: {alt_wakeword} (confidence: {alt_confidence:.2f})")
                return WakewordDetectionResult(
                    detected=True,
                    confidence=alt_confidence,
                    matched_wakeword=alt_wakeword
                )
        
        logger.debug(f"No wakeword detected. Max confidence: {max(confidence, 0.0):.2f}")
        return WakewordDetectionResult(detected=False, confidence=max(confidence, 0.0))
    
    def _calculate_confidence(
        self,
        text: str,
        wakeword: str,
        confidence_scores: Optional[dict] = None
    ) -> float:
        """Calculate confidence score for wakeword match.
        
        Args:
            text: Normalized text to search
            wakeword: Wakeword to detect
            confidence_scores: Optional per-word confidence scores
            
        Returns:
            Confidence score 0-1
        """
        # Exact match
        if wakeword in text:
            base_confidence = 0.95
        # Partial match (first 3+ chars)
        elif len(wakeword) >= 3 and text.startswith(wakeword[:3]):
            base_confidence = 0.70
        # Fuzzy match (Levenshtein-like)
        else:
            base_confidence = self._fuzzy_match(text, wakeword)
        
        # Apply sensitivity adjustment
        adjusted = base_confidence * self.config.sensitivity
        
        # Apply confidence scores if provided
        if confidence_scores:
            adjusted *= self._aggregate_word_confidence(text, wakeword, confidence_scores)
        
        return min(adjusted, 1.0)
    
    def _fuzzy_match(self, text: str, wakeword: str) -> float:
        """Calculate fuzzy match confidence."""
        words = text.split()
        max_similarity = 0.0
        
        for word in words:
            similarity = self._levenshtein_similarity(word, wakeword)
            max_similarity = max(max_similarity, similarity)
        
        return max_similarity * 0.6  # Reduce confidence for fuzzy matches
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity (0-1)."""
        if len(s1) == 0 or len(s2) == 0:
            return 0.0
        
        distance = self._levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return 1.0 - (distance / max_len)
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _aggregate_word_confidence(self, text: str, wakeword: str, scores: dict) -> float:
        """Aggregate confidence from word-level scores."""
        words = text.split()
        wakeword_words = wakeword.split()
        
        total_confidence = 0.0
        match_count = 0
        
        for word in wakeword_words:
            if word in scores:
                total_confidence += scores[word]
                match_count += 1
        
        if match_count == 0:
            return 0.5
        
        return total_confidence / match_count
    
    def get_state(self) -> WakewordState:
        """Get current detector state."""
        return self.state
    
    def get_stats(self) -> dict:
        """Get detection statistics."""
        total = self.detection_stats["total_checks"]
        if total > 0:
            false_pos_rate = self.detection_stats["false_positives"] / total
            avg_conf = self.detection_stats["detections"] / total if total > 0 else 0
            self.detection_stats["avg_confidence"] = avg_conf
        
        return self.detection_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset detection statistics."""
        self.detection_stats = {
            "total_checks": 0,
            "detections": 0,
            "false_positives": 0,
            "avg_confidence": 0.0,
        }
        logger.info("Detection statistics reset")


class VoiceActivityDetector:
    """Detect voice activity in audio."""
    
    def __init__(self, silence_threshold: float = 0.02, min_speech_duration_ms: int = 200):
        """Initialize VAD.
        
        Args:
            silence_threshold: Audio amplitude threshold for silence
            min_speech_duration_ms: Minimum speech segment duration
        """
        self.silence_threshold = silence_threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.is_speaking = False
        self.speech_start_time = None
    
    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """Detect if audio chunk contains speech.
        
        Args:
            audio_chunk: Raw audio data
            sample_rate: Sample rate in Hz
            
        Returns:
            True if speech detected, False otherwise
        """
        # Calculate RMS amplitude
        amplitude = self._calculate_amplitude(audio_chunk)
        return amplitude > self.silence_threshold
    
    def _calculate_amplitude(self, audio_chunk: bytes) -> float:
        """Calculate RMS amplitude of audio chunk."""
        if not audio_chunk or len(audio_chunk) < 2:
            return 0.0
        
        # Convert bytes to samples
        samples = []
        for i in range(0, len(audio_chunk) - 1, 2):
            sample = int.from_bytes(audio_chunk[i:i+2], 'little', signed=True)
            samples.append(sample)
        
        if not samples:
            return 0.0
        
        # Calculate RMS
        sum_squares = sum(s * s for s in samples)
        rms = math.sqrt(sum_squares / len(samples))
        
        # Normalize to 0-1
        max_amplitude = 32768
        return rms / max_amplitude


_wakeword_detector_instance: Optional[WakewordDetector] = None


def get_wakeword_detector(config: Optional[WakewordConfig] = None) -> WakewordDetector:
    """Get singleton wakeword detector instance.
    
    Args:
        config: Optional config for initialization
        
    Returns:
        WakewordDetector singleton instance
    """
    global _wakeword_detector_instance
    if _wakeword_detector_instance is None:
        _wakeword_detector_instance = WakewordDetector(config)
    return _wakeword_detector_instance
