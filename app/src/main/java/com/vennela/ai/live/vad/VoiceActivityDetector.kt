package com.vennela.ai.live.vad

import kotlin.math.sqrt

/**
 * Real-time Voice Activity Detector (VAD) calculating RMS energy levels on raw 16-bit PCM audio chunks.
 */
class VoiceActivityDetector(
    private var energyThresholdDb: Double = 42.0
) {

    /**
     * Evaluates whether a raw 16-bit PCM byte array contains speech above the energy threshold.
     */
    fun isSpeech(pcmChunk: ByteArray): Boolean {
        val rmsDb = calculateRmsDb(pcmChunk)
        return rmsDb >= energyThresholdDb
    }

    /**
     * Calculates the RMS energy of 16-bit PCM audio in decibels.
     */
    fun calculateRmsDb(pcmChunk: ByteArray): Double {
        if (pcmChunk.size < 2) return 0.0

        var sumSquares = 0.0
        val sampleCount = pcmChunk.size / 2

        for (i in 0 until sampleCount) {
            val sample = (pcmChunk[i * 2].toInt() and 0xFF) or (pcmChunk[i * 2 + 1].toInt() shl 8)
            val shortSample = sample.toShort()
            sumSquares += shortSample * shortSample
        }

        val rms = sqrt(sumSquares / sampleCount)
        if (rms <= 0.00001) return 0.0

        return 20.0 * kotlin.math.log10(rms)
    }

    fun setThreshold(thresholdDb: Double) {
        this.energyThresholdDb = thresholdDb
    }
}
