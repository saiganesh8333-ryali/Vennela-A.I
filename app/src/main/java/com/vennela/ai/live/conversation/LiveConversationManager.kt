package com.vennela.ai.live.conversation

import android.content.Context
import android.util.Log
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolResult
import com.vennela.ai.automation.ToolRouter
import com.vennela.ai.live.audio.AudioCaptureManager
import com.vennela.ai.live.audio.AudioPlaybackManager
import com.vennela.ai.live.realtime.GeminiLiveRealtimeSession
import com.vennela.ai.live.realtime.RealtimeConnectionState
import com.vennela.ai.live.realtime.RealtimeSession
import com.vennela.ai.live.realtime.RealtimeSessionListener
import com.vennela.ai.live.vad.BargeInController
import com.vennela.ai.live.vad.VoiceActivityDetector
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Orchestrator for Real-Time Live Conversation with AI:
 * Audio capture -> VAD -> RealtimeSession -> AI -> Playback & Live Tool Calls
 */
class LiveConversationManager(
    private val context: Context,
    private val scope: CoroutineScope,
    private val realtimeSession: RealtimeSession = GeminiLiveRealtimeSession()
) : RealtimeSessionListener {

    private val captureManager = AudioCaptureManager()
    private val playbackManager = AudioPlaybackManager()
    private val vad = VoiceActivityDetector()
    private val bargeInController = BargeInController(playbackManager, vad)
    private val toolRouter = ToolRouter(context)

    private var audioCaptureJob: Job? = null
    @Volatile
    private var isSessionActive = false

    init {
        realtimeSession.setListener(this)
        bargeInController.setOnBargeInListener {
            Log.i("LiveConversationManager", "User interrupted AI! Sending interrupt signal to RealtimeSession...")
            realtimeSession.interrupt()
        }
    }

    fun startSession() {
        if (isSessionActive) return
        isSessionActive = true

        playbackManager.start()
        realtimeSession.connect()

        captureManager.startCapture(scope)
        audioCaptureJob = scope.launch(Dispatchers.IO) {
            captureManager.audioFlow.collect { pcmChunk ->
                if (!isSessionActive) return@collect

                // Check for user interruption / barge in
                bargeInController.processMicrophoneChunk(pcmChunk)

                // Stream mic audio chunk to Realtime AI
                realtimeSession.sendAudioChunk(pcmChunk)
            }
        }

        Log.i("LiveConversationManager", "Live Conversation Session started")
    }

    fun stopSession() {
        isSessionActive = false
        audioCaptureJob?.cancel()
        audioCaptureJob = null

        captureManager.stopCapture()
        playbackManager.release()
        realtimeSession.disconnect()

        Log.i("LiveConversationManager", "Live Conversation Session stopped")
    }

    override fun onStateChanged(state: RealtimeConnectionState) {
        Log.d("LiveConversationManager", "Realtime connection state changed: $state")
    }

    override fun onAudioResponseChunk(pcmChunk: ByteArray) {
        if (!isSessionActive) return
        playbackManager.playChunk(pcmChunk)
    }

    override fun onTextResponseChunk(textChunk: String) {
        Log.d("LiveConversationManager", "AI text chunk: $textChunk")
    }

    override fun onToolCallReceived(toolCall: ToolCall) {
        Log.i("LiveConversationManager", "Live Tool Call received from AI: ${toolCall.tool}")
        scope.launch(Dispatchers.IO) {
            val result: ToolResult = toolRouter.routeAndExecute(toolCall)
            Log.i("LiveConversationManager", "Tool execution complete: success=${result.success}")
            realtimeSession.sendToolResult(result)
        }
    }

    override fun onError(error: String) {
        Log.e("LiveConversationManager", "Realtime session error: $error")
    }

    fun isSessionActive(): Boolean = isSessionActive
}
