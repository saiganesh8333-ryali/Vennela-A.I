package com.vennela.ai

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Log
import com.google.gson.Gson
import kotlinx.coroutines.*
import okhttp3.*
import java.util.concurrent.TimeUnit
import java.util.UUID

/**
 * Android Agent WebSocket Transport Layer.
 * Handles communication between the Android Agent and the Vennela Backend.
 */
class AgentWebSocketClient(
    private val context: Context,
    private val agentExecutor: AgentExecutor,
    private val scope: CoroutineScope
) {
    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private var isConnected = false
    private var isRegistered = false
    
    private val agentId = getOrCreateAgentId()
    private val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)

    private var reconnectJob: Job? = null
    private var reconnectDelay = 5000L

    enum class ConnectionState {
        DISCONNECTED, CONNECTING, CONNECTED, REGISTERED, RECONNECTING
    }

    private var _state = ConnectionState.DISCONNECTED
    val state: ConnectionState get() = _state

    fun connect() {
        if (_state == ConnectionState.CONNECTED || _state == ConnectionState.REGISTERED) return
        
        val activeToken = AgentConfig.runtimeAgentToken
        if (activeToken.isBlank()) {
            Log.w("AgentWsClient", "Skipping connection: Agent token is not configured.")
            _state = ConnectionState.DISCONNECTED
            return
        }

        _state = ConnectionState.CONNECTING
        val wsUrl = AgentConfig.getWsUrl(agentId)
        Log.d("AgentWsClient", "Connecting to: $wsUrl")
        Log.d("AgentWsClient", "Authentication configured: true")

        val request = Request.Builder()
            .url(wsUrl)
            .header("User-Agent", "VennelaAI-Enterprise")
            .header("X-Vennela-Core", "v2.5")
            .header("Origin", "https://vennela-a-i.onrender.com")
            .header("Authorization", "Bearer $activeToken")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i("AgentWsClient", "WebSocket Connected")
                _state = ConnectionState.CONNECTED
                reconnectDelay = 5000L
                registerAgent()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d("AgentWsClient", "Received message: $text")
                handleMessage(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.w("AgentWsClient", "WebSocket Closing: $code / $reason")
                _state = ConnectionState.DISCONNECTED
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.w("AgentWsClient", "WebSocket Closed: $code / $reason")
                _state = ConnectionState.DISCONNECTED
                isRegistered = false
                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("AgentWsClient", "WebSocket Failure: ${t.message}", t)
                _state = ConnectionState.DISCONNECTED
                isRegistered = false
                scheduleReconnect()
            }
        })
    }

    private fun registerAgent() {
        val registerMsg = AgentWsMessage(
            type = WsMessageTypes.REGISTER,
            agent_id = agentId,
            device_id = deviceId,
            platform = "android",
            capabilities = agentExecutor.getCapabilities(),
            token = AgentConfig.runtimeAgentToken
        )
        send(registerMsg)
    }

    private fun handleMessage(text: String) {
        try {
            val message = gson.fromJson(text, AgentWsMessage::class.java)
            when (message.type) {
                WsMessageTypes.REGISTERED -> {
                    Log.i("AgentWsClient", "Agent Registered Successfully: ${message.status}")
                    _state = ConnectionState.REGISTERED
                    isRegistered = true
                }
                WsMessageTypes.EXECUTE -> {
                    message.action?.let { action ->
                        val requestId = message.request_id
                        if (requestId != null) {
                            executeAndReport(requestId, action)
                        } else {
                            Log.e("AgentWsClient", "Execute message missing request_id")
                        }
                    }
                }
                WsMessageTypes.PING -> {
                    send(AgentWsMessage(type = WsMessageTypes.PONG, timestamp = message.timestamp))
                }
                WsMessageTypes.CANCEL -> {
                    Log.w("AgentWsClient", "Cancellation requested for request_id: ${message.request_id}")
                    // Mapping to existing architecture if supported. Current AgentExecutor doesn't support cancel yet.
                }
                else -> {
                    Log.d("AgentWsClient", "Unhandled message type: ${message.type}")
                }
            }
        } catch (e: Exception) {
            Log.e("AgentWsClient", "Error parsing message: ${e.message}")
        }
    }

    private fun executeAndReport(requestId: String, action: AgentAction) {
        scope.launch {
            try {
                val result = agentExecutor.executeAction(action)
                val resultMsg = AgentWsMessage(
                    type = WsMessageTypes.RESULT,
                    request_id = requestId,
                    status = if (result.success) "success" else "failed",
                    result = result
                )
                send(resultMsg)
            } catch (e: Exception) {
                val errorMsg = AgentWsMessage(
                    type = WsMessageTypes.RESULT,
                    request_id = requestId,
                    status = "failed",
                    error = AgentWsError("EXECUTION_ERROR", e.message ?: "Unknown error")
                )
                send(errorMsg)
            }
        }
    }

    private fun send(message: AgentWsMessage) {
        val json = gson.toJson(message)
        webSocket?.send(json)
    }

    private fun scheduleReconnect() {
        if (reconnectJob?.isActive == true) return
        
        reconnectJob = scope.launch {
            _state = ConnectionState.RECONNECTING
            delay(reconnectDelay)
            Log.i("AgentWsClient", "Attempting to reconnect...")
            reconnectDelay = (reconnectDelay * 2).coerceAtMost(60000L) // Exponential backoff
            connect()
        }
    }

    fun disconnect() {
        webSocket?.close(1000, "App closed")
        webSocket = null
        reconnectJob?.cancel()
        _state = ConnectionState.DISCONNECTED
        isRegistered = false
    }

    private fun getOrCreateAgentId(): String {
        val prefs = context.getSharedPreferences("agent_prefs", Context.MODE_PRIVATE)
        var id = prefs.getString("agent_id", null)
        if (id == null) {
            id = "agent_${UUID.randomUUID().toString().take(8)}"
            prefs.edit().putString("agent_id", id).apply()
        }
        return id
    }
}
