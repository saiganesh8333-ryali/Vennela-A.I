package com.vennela.ai.live.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch

/**
 * Captures microphone audio using AudioRecord and exposes a PCM byte stream.
 */
class AudioCaptureManager(
    private val sampleRate: Int = 16000,
    private val channelConfig: Int = AudioFormat.CHANNEL_IN_MONO,
    private val audioFormat: Int = AudioFormat.ENCODING_PCM_16BIT
) {

    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    @Volatile
    private var isRecording = false

    private val _audioFlow = MutableSharedFlow<ByteArray>(extraBufferCapacity = 64)
    val audioFlow: SharedFlow<ByteArray> = _audioFlow.asSharedFlow()

    private val minBufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)

    @SuppressLint("MissingPermission")
    fun startCapture(scope: CoroutineScope) {
        if (isRecording) return

        try {
            val bufferSize = minBufferSize.coerceAtLeast(2048)
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                channelConfig,
                audioFormat,
                bufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                Log.e("AudioCaptureManager", "AudioRecord failed to initialize")
                return
            }

            audioRecord?.startRecording()
            isRecording = true
            Log.i("AudioCaptureManager", "Audio recording started")

            recordingJob = scope.launch(Dispatchers.IO) {
                val buffer = ByteArray(1024)
                while (isRecording) {
                    val bytesRead = audioRecord?.read(buffer, 0, buffer.size) ?: -1
                    if (bytesRead > 0) {
                        val chunk = buffer.copyOf(bytesRead)
                        _audioFlow.emit(chunk)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("AudioCaptureManager", "Error starting audio recording: ${e.message}", e)
            stopCapture()
        }
    }

    fun stopCapture() {
        isRecording = false
        recordingJob?.cancel()
        recordingJob = null

        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            Log.w("AudioCaptureManager", "Error stopping AudioRecord: ${e.message}")
        } finally {
            audioRecord = null
        }
        Log.i("AudioCaptureManager", "Audio recording stopped")
    }

    fun isRecording(): Boolean = isRecording
}
