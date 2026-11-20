package com.vennela.ai.live.realtime

import android.util.Base64
import android.util.Log
import com.google.gson.Gson
import com.vennela.ai.AgentConfig
import com.vennela.ai.SessionManager
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolResult
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

/**
 * Gemini Live Realtime Session implementation aligned with the Vennela Backend WebSocket protocol:
 * wss://vennela-a-i.onrender.com/ws/gemini/live
 */
class GeminiLiveRealtimeSession(
    private val userId: String = "user_vennela_android",
    private val sessionId: String = SessionManager.generateNewSessionId(),
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO)
) : RealtimeSession {

    private val gson = Gson()
    private var webSocket: WebSocket? = null
    private var listener: RealtimeSessionListener? = null
    private var currentState = RealtimeConnectionState.DISCONNECTED
    private var pingJob: Job? = null

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    override fun connect() {
        if (currentState == RealtimeConnectionState.CONNECTED || currentState == RealtimeConnectionState.CONNECTING) return

        updateState(RealtimeConnectionState.CONNECTING)
        val wsUrl = AgentConfig.getGeminiLiveWsUrl()

        val requestBuilder = Request.Builder()
            .url(wsUrl)
            .header("User-Agent", "VennelaAI-Android")

        val bearerHeader = AgentConfig.getBearerHeader()
        if (bearerHeader != null) {
            requestBuilder.header("Authorization", bearerHeader)
        }

        val request = requestBuilder.build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i("GeminiLiveSession", "WebSocket connected to $wsUrl")
                sendSessionStart()
                startPingTimer()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleIncomingFrame(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.w("GeminiLiveSession", "WebSocket closing: $code / $reason")
                stopPingTimer()
                updateState(RealtimeConnectionState.DISCONNECTED)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.w("GeminiLiveSession", "WebSocket closed: $code / $reason")
                stopPingTimer()
                updateState(RealtimeConnectionState.DISCONNECTED)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("GeminiLiveSession", "WebSocket failure: ${t.message}", t)
                stopPingTimer()
                updateState(RealtimeConnectionState.ERROR)
                listener?.onError(t.message ?: "WebSocket connection failure")
            }
        })
    }

    override fun disconnect() {
        stopPingTimer()
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
        updateState(RealtimeConnectionState.DISCONNECTED)
    }

    fun sendSessionStart() {
        val payload = mapOf(
            "type" to "session.start",
            "user_id" to userId,
            "session_id" to sessionId
        )
        sendJson(payload)
    }

    override fun sendAudioChunk(pcmChunk: ByteArray) {
        if (currentState != RealtimeConnectionState.CONNECTED) return
        val base64Audio = Base64.encodeToString(pcmChunk, Base64.NO_WRAP)
        val payload = mapOf(
            "type" to "audio",
            "data" to base64Audio
        )
        sendJson(payload)
    }

    override fun sendText(text: String) {
        if (currentState != RealtimeConnectionState.CONNECTED) return
        val payload = mapOf(
            "type" to "text",
            "text" to text
        )
        sendJson(payload)
    }

    override fun sendToolResult(toolResult: ToolResult) {
        if (currentState != RealtimeConnectionState.CONNECTED) return
        val payload = mutableMapOf<String, Any?>(
            "type" to "tool_result",
            "tool" to toolResult.tool,
            "success" to toolResult.success
        )
        toolResult.message?.let { payload["message"] = it }
        toolResult.data?.let { payload["data"] = it }
        toolResult.error?.let { payload["error"] = it }

        sendJson(payload)
    }

    fun sendPing() {
        sendJson(mapOf("type" to "ping"))
    }

    override fun interrupt() {
        if (currentState != RealtimeConnectionState.CONNECTED) return
        sendJson(mapOf("type" to "interrupt"))
    }

    override fun setListener(listener: RealtimeSessionListener?) {
        this.listener = listener
    }

    override fun getState(): RealtimeConnectionState = currentState

    fun handleIncomingFrame(text: String) {
        try {
            @Suppress("UNCHECKED_CAST")
            val map = gson.fromJson(text, Map::class.java) as? Map<String, Any?> ?: return

            when (map["type"]) {
                "session.ready" -> {
                    Log.i("GeminiLiveSession", "Session ready from backend")
                    updateState(RealtimeConnectionState.CONNECTED)
                }

                "audio" -> {
                    val base64Data = map["data"] as? String
                    if (base64Data != null) {
                        val pcm = Base64.decode(base64Data, Base64.DEFAULT)
                        listener?.onAudioResponseChunk(pcm)
                    }
                }

                "text" -> {
                    val chunk = map["text"] as? String
                    if (chunk != null) {
                        listener?.onTextResponseChunk(chunk)
                    }
                }

                "tool_call" -> {
                    val toolName = map["tool"] as? String
                        ?: map["name"] as? String
                        ?: return
                    @Suppress("UNCHECKED_CAST")
                    val argsMap = (map["arguments"] ?: map["args"]) as? Map<String, Any?> ?: emptyMap()
                    val reqId = map["request_id"] as? String ?: map["id"] as? String

                    val toolCall = ToolCall(toolName, com.vennela.ai.automation.ToolArguments(argsMap), reqId)
                    listener?.onToolCallReceived(toolCall)
                }

                "interrupted" -> {
                    Log.i("GeminiLiveSession", "Interruption frame received from backend")
                    listener?.onTextResponseChunk("[Interrupted]")
                }

                "pong" -> {
                    Log.d("GeminiLiveSession", "Pong received from backend")
                }

                "error" -> {
                    val errorMsg = map["message"] as? String ?: "Backend live session error"
                    Log.e("GeminiLiveSession", "Server error frame: $errorMsg")
                    listener?.onError(errorMsg)
                }

                else -> {
                    Log.d("GeminiLiveSession", "Unhandled server frame: ${map["type"]}")
                }
            }
        } catch (e: Exception) {
            Log.e("GeminiLiveSession", "Error parsing server frame: ${e.message}")
        }
    }

    private fun sendJson(map: Map<String, Any?>) {
        val json = gson.toJson(map)
        webSocket?.send(json)
    }

    private fun startPingTimer() {
        stopPingTimer()
        pingJob = scope.launch {
            while (isActive) {
                delay(15000L)
                if (currentState == RealtimeConnectionState.CONNECTED) {
                    sendPing()
                }
            }
        }
    }

    private fun stopPingTimer() {
        pingJob?.cancel()
        pingJob = null
    }

    private fun updateState(newState: RealtimeConnectionState) {
        currentState = newState
        listener?.onStateChanged(newState)
    }
}
