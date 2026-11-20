package com.vennela.ai.live.vad

import android.util.Log
import com.vennela.ai.live.audio.AudioPlaybackManager

/**
 * Controller detecting user interruptions (barge-in) while AI voice response is playing.
 * Instantly stops playback and signals the conversation session.
 */
class BargeInController(
    private val playbackManager: AudioPlaybackManager,
    private val vad: VoiceActivityDetector = VoiceActivityDetector()
) {

    private var onBargeInListener: (() -> Unit)? = null

    fun setOnBargeInListener(listener: () -> Unit) {
        this.onBargeInListener = listener
    }

    /**
     * Process an incoming microphone audio chunk.
     * Returns true if a barge-in interruption occurred.
     */
    fun processMicrophoneChunk(pcmChunk: ByteArray): Boolean {
        if (!playbackManager.isPlaying()) return false

        if (vad.isSpeech(pcmChunk)) {
            Log.i("BargeInController", "User speech detected during AI playback! Triggering barge-in...")
            playbackManager.stopAndFlush()
            onBargeInListener?.invoke()
            return true
        }

        return false
    }
}
