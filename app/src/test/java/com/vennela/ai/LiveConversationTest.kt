package com.vennela.ai

import android.util.Log
import com.vennela.ai.live.audio.AudioPlaybackManager
import com.vennela.ai.live.vad.BargeInController
import com.vennela.ai.live.vad.VoiceActivityDetector
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.unmockkAll
import io.mockk.verify
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LiveConversationTest {

    @Before
    fun setup() {
        mockkStatic(Log::class)
        every { Log.i(any(), any()) } returns 0
        every { Log.d(any(), any()) } returns 0
        every { Log.w(any<String>(), any<String>()) } returns 0
        every { Log.e(any(), any()) } returns 0
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    @Test
    fun `test voice activity detector RMS calculation on silence vs loud PCM`() {
        val vad = VoiceActivityDetector(energyThresholdDb = 30.0)

        val silencePcm = ByteArray(100) { 0 }
        assertFalse(vad.isSpeech(silencePcm))

        // Create loud 16-bit PCM wave samples
        val loudPcm = ByteArray(200)
        for (i in 0 until 100) {
            val sampleShort: Short = 25000
            loudPcm[i * 2] = (sampleShort.toInt() and 0xFF).toByte()
            loudPcm[i * 2 + 1] = ((sampleShort.toInt() shr 8) and 0xFF).toByte()
        }
        assertTrue(vad.isSpeech(loudPcm))
    }

    @Test
    fun `test barge in controller stops playback when user speaks during AI playback`() {
        val playbackManager = mockk<AudioPlaybackManager>(relaxed = true)
        val vad = mockk<VoiceActivityDetector>()

        every { playbackManager.isPlaying() } returns true
        every { vad.isSpeech(any()) } returns true

        val controller = BargeInController(playbackManager, vad)
        var interrupted = false
        controller.setOnBargeInListener { interrupted = true }

        val result = controller.processMicrophoneChunk(ByteArray(50))

        assertTrue(result)
        assertTrue(interrupted)
        verify { playbackManager.stopAndFlush() }
    }
}
