package com.vennela.ai.live.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log

/**
 * Low-latency audio stream playback manager using AudioTrack for AI speech synthesis streaming.
 */
class AudioPlaybackManager(
    private val sampleRate: Int = 24000,
    private val channelConfig: Int = AudioFormat.CHANNEL_OUT_MONO,
    private val audioFormat: Int = AudioFormat.ENCODING_PCM_16BIT
) {

    private var audioTrack: AudioTrack? = null
    @Volatile
    private var isPlaying = false

    private val minBufferSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, audioFormat)

    @Synchronized
    fun start() {
        if (audioTrack != null) return

        try {
            val bufferSize = minBufferSize.coerceAtLeast(4096)
            audioTrack = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(audioFormat)
                        .setSampleRate(sampleRate)
                        .setChannelMask(channelConfig)
                        .build()
                )
                .setBufferSizeInBytes(bufferSize)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()

            audioTrack?.play()
            isPlaying = true
            Log.i("AudioPlaybackManager", "AudioTrack initialized and playing")
        } catch (e: Exception) {
            Log.e("AudioPlaybackManager", "Failed to initialize AudioTrack: ${e.message}", e)
        }
    }

    fun playChunk(pcmChunk: ByteArray) {
        if (audioTrack == null || !isPlaying) {
            start()
        }

        try {
            audioTrack?.write(pcmChunk, 0, pcmChunk.size)
        } catch (e: Exception) {
            Log.e("AudioPlaybackManager", "Error writing chunk to AudioTrack: ${e.message}")
        }
    }

    /**
     * Instantly stops playback and flushes buffered audio frames (e.g. on user barge-in).
     */
    @Synchronized
    fun stopAndFlush() {
        try {
            audioTrack?.pause()
            audioTrack?.flush()
        } catch (e: Exception) {
            Log.w("AudioPlaybackManager", "Error flushing AudioTrack: ${e.message}")
        }
        isPlaying = false
    }

    @Synchronized
    fun release() {
        stopAndFlush()
        try {
            audioTrack?.stop()
            audioTrack?.release()
        } catch (e: Exception) {
            Log.w("AudioPlaybackManager", "Error releasing AudioTrack: ${e.message}")
        } finally {
            audioTrack = null
        }
    }

    fun isPlaying(): Boolean = isPlaying
}
