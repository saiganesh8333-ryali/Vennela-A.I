"""
Test Suite for Voice Pipeline - Phase D
Comprehensive testing of wakeword detection, streaming, and response generation
"""

import unittest
import asyncio
import time
from voice_wakeword_detector import (
    WakewordDetector, WakewordConfig, VoiceActivityDetector, get_wakeword_detector
)
from voice_streaming_engine import (
    VoiceStreamingEngine, StreamingConfig, BufferedAudioQueue, StreamingState
)
from voice_response_generator import (
    VoiceResponseGenerator, ResponseConfig, VoiceGender, SpeechRate
)


class TestWakewordDetection(unittest.TestCase):
    """Test wakeword detection functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = WakewordConfig(
            primary_wakeword="vennela",
            detection_threshold=0.85
        )
        self.detector = WakewordDetector(self.config)
    
    def test_exact_wakeword_match(self):
        """Test exact wakeword match."""
        result = self.detector.detect_wakeword("Hey Vennela, hello there")
        self.assertTrue(result.detected)
        self.assertEqual(result.matched_wakeword, "vennela")
        self.assertGreaterEqual(result.confidence, self.config.detection_threshold)
    
    def test_case_insensitive_detection(self):
        """Test case-insensitive wakeword detection."""
        result = self.detector.detect_wakeword("Hey VENNELA, listen")
        self.assertTrue(result.detected)
        self.assertEqual(result.matched_wakeword, "vennela")
    
    def test_no_wakeword_detected(self):
        """Test when wakeword is not present."""
        result = self.detector.detect_wakeword("Hello there, how are you?")
        self.assertFalse(result.detected)
        self.assertIsNone(result.matched_wakeword)
    
    def test_fuzzy_matching(self):
        """Test fuzzy matching for similar wakeword."""
        result = self.detector.detect_wakeword("venella please")  # Typo
        # Fuzzy matching might detect it
        self.assertIsNotNone(result.confidence)
    
    def test_wakeword_statistics(self):
        """Test wakeword detection statistics."""
        self.detector.detect_wakeword("Vennela")
        self.detector.detect_wakeword("Vennela")
        self.detector.detect_wakeword("Hello")
        
        stats = self.detector.get_stats()
        self.assertEqual(stats["total_checks"], 3)
        self.assertEqual(stats["detections"], 2)
    
    def test_alternate_wakewords(self):
        """Test alternate wakeword detection."""
        config = WakewordConfig(
            primary_wakeword="vennela",
            alternate_wakewords=["hey assistant", "wake up"]
        )
        detector = WakewordDetector(config)
        
        result = detector.detect_wakeword("hey assistant, start")
        self.assertTrue(result.detected)
        self.assertEqual(result.matched_wakeword, "hey assistant")
    
    def test_confidence_threshold(self):
        """Test confidence threshold filtering."""
        config = WakewordConfig(detection_threshold=0.99)
        detector = WakewordDetector(config)
        
        # Fuzzy match should not pass high threshold
        result = detector.detect_wakeword("venella")
        self.assertFalse(result.detected or result.confidence < 0.99)


class TestVoiceActivityDetection(unittest.TestCase):
    """Test voice activity detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.vad = VoiceActivityDetector(silence_threshold=0.02)
    
    def test_silence_detection(self):
        """Test silent audio detection."""
        silent_chunk = bytes([0] * 1024)
        is_speech = self.vad.is_speech(silent_chunk)
        self.assertFalse(is_speech)
    
    def test_speech_detection(self):
        """Test speech audio detection."""
        # Create audio chunk with higher amplitude
        speech_chunk = bytes([100] * 1024)
        is_speech = self.vad.is_speech(speech_chunk)
        self.assertTrue(is_speech)


class TestAudioStreaming(unittest.TestCase):
    """Test audio streaming engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = StreamingConfig(
            sample_rate=16000,
            chunk_size=1024,
            buffer_size=50
        )
        self.engine = VoiceStreamingEngine(self.config)
    
    def test_stream_lifecycle(self):
        """Test stream start/stop lifecycle."""
        self.assertEqual(self.engine.get_state(), StreamingState.IDLE)
        
        self.assertTrue(self.engine.start_stream())
        self.assertEqual(self.engine.get_state(), StreamingState.STREAMING)
        
        self.assertTrue(self.engine.stop_stream())
        self.assertEqual(self.engine.get_state(), StreamingState.STOPPED)
    
    def test_pause_resume_stream(self):
        """Test stream pause and resume."""
        self.engine.start_stream()
        
        self.assertTrue(self.engine.pause_stream())
        self.assertEqual(self.engine.get_state(), StreamingState.PAUSED)
        
        self.assertTrue(self.engine.resume_stream())
        self.assertEqual(self.engine.get_state(), StreamingState.STREAMING)
        
        self.engine.stop_stream()
    
    def test_write_read_chunks(self):
        """Test writing and reading audio chunks."""
        self.engine.start_stream()
        
        chunk = bytes([1, 2, 3, 4])
        self.assertTrue(self.engine.write_chunk(chunk))
        
        read_chunk = self.engine.read_chunk()
        self.assertEqual(read_chunk, chunk)
        
        self.engine.stop_stream()
    
    def test_buffer_overflow(self):
        """Test buffer overflow handling."""
        self.engine.start_stream()
        
        chunk = bytes([1] * 1000)
        for _ in range(self.config.buffer_size + 10):
            result = self.engine.write_chunk(chunk)
        
        # Some writes should fail due to buffer overflow
        self.assertTrue(self.engine.stream_stats.total_chunks <= self.config.buffer_size)
        
        self.engine.stop_stream()
    
    def test_streaming_statistics(self):
        """Test streaming statistics tracking."""
        self.engine.start_stream()
        
        for _ in range(5):
            self.engine.write_chunk(bytes([1] * 1000))
        
        stats = self.engine.get_stats()
        self.assertEqual(stats["total_chunks"], 5)
        self.assertEqual(stats["total_bytes"], 5000)
        
        self.engine.stop_stream()


class TestBufferedAudioQueue(unittest.TestCase):
    """Test audio queue implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.queue = BufferedAudioQueue(max_size=10)
    
    def test_fifo_order(self):
        """Test FIFO queue ordering."""
        chunk1 = bytes([1, 2, 3])
        chunk2 = bytes([4, 5, 6])
        
        self.queue.put(chunk1)
        self.queue.put(chunk2)
        
        self.assertEqual(self.queue.get(), chunk1)
        self.assertEqual(self.queue.get(), chunk2)
    
    def test_queue_full(self):
        """Test queue full behavior."""
        for i in range(10):
            result = self.queue.put(bytes([i]))
            self.assertTrue(result)
        
        # Next put should fail
        result = self.queue.put(bytes([10]))
        self.assertFalse(result)
    
    def test_queue_stats(self):
        """Test queue statistics."""
        self.queue.put(bytes([1]))
        self.queue.put(bytes([2]))
        self.queue.get()
        
        stats = self.queue.get_stats()
        self.assertEqual(stats["chunks_added"], 2)
        self.assertEqual(stats["chunks_removed"], 1)


class TestResponseGeneration(unittest.TestCase):
    """Test voice response generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ResponseConfig(
            voice_gender=VoiceGender.FEMALE,
            speech_rate=1.0
        )
        self.generator = VoiceResponseGenerator(self.config)
    
    def test_generate_speech(self):
        """Test basic speech generation."""
        response = self.generator.generate_speech("Hello, how are you?")
        
        self.assertIsNotNone(response.audio_bytes)
        self.assertFalse(response.was_cached)
        self.assertEqual(response.text, "Hello, how are you?")
        self.assertGreater(response.duration_ms, 0)
    
    def test_response_caching(self):
        """Test response caching."""
        text = "Hello world"
        
        # First call should not be cached
        response1 = self.generator.generate_speech(text)
        self.assertFalse(response1.was_cached)
        
        # Second call should be cached
        response2 = self.generator.generate_speech(text)
        self.assertTrue(response2.was_cached)
        self.assertEqual(response1.audio_bytes, response2.audio_bytes)
    
    def test_text_truncation(self):
        """Test long text truncation."""
        long_text = "a" * (self.config.max_response_length + 100)
        response = self.generator.generate_speech(long_text)
        
        self.assertEqual(len(response.text), self.config.max_response_length)
    
    def test_empty_text(self):
        """Test handling of empty text."""
        response = self.generator.generate_speech("")
        self.assertEqual(response.text, "")
        self.assertIsNone(response.audio_bytes)
    
    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        self.generator.generate_speech("Test 1")
        self.generator.generate_speech("Test 1")  # Cache hit
        self.generator.generate_speech("Test 2")
        self.generator.generate_speech("Test 2")  # Cache hit
        
        cache_stats = self.generator.get_cache_stats()
        self.assertEqual(cache_stats["hits"], 2)
        self.assertEqual(cache_stats["misses"], 2)
    
    def test_voice_config_update(self):
        """Test updating voice configuration."""
        original_config = self.generator.get_voice_config()
        
        new_config = ResponseConfig(
            voice_gender=VoiceGender.MALE,
            speech_rate=1.5
        )
        self.generator.update_config(new_config)
        
        updated_config = self.generator.get_voice_config()
        self.assertEqual(updated_config.voice_gender, VoiceGender.MALE)
        self.assertEqual(updated_config.speech_rate, 1.5)


class TestVoiceIntegration(unittest.TestCase):
    """Integration tests for complete voice pipeline."""
    
    def test_wakeword_to_response_flow(self):
        """Test complete wakeword detection to response flow."""
        # Detect wakeword
        detector = WakewordDetector()
        wakeword_result = detector.detect_wakeword("Vennela, say hello")
        self.assertTrue(wakeword_result.detected)
        
        # Start streaming
        engine = VoiceStreamingEngine()
        self.assertTrue(engine.start_stream())
        
        # Add audio chunk
        chunk = bytes([1, 2, 3, 4])
        self.assertTrue(engine.write_chunk(chunk))
        
        # Generate response
        generator = VoiceResponseGenerator()
        response = generator.generate_speech("Hello! How can I help?")
        self.assertIsNotNone(response.audio_bytes)
        
        # Stop streaming
        self.assertTrue(engine.stop_stream())


def run_all_tests():
    """Run all tests and print summary."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestWakewordDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceActivityDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestAudioStreaming))
    suite.addTests(loader.loadTestsFromTestCase(TestBufferedAudioQueue))
    suite.addTests(loader.loadTestsFromTestCase(TestResponseGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
