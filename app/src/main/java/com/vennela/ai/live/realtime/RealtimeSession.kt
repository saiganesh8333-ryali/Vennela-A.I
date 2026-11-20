package com.vennela.ai.live.realtime

import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolResult

enum class RealtimeConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    ERROR
}

interface RealtimeSessionListener {
    fun onStateChanged(state: RealtimeConnectionState)
    fun onAudioResponseChunk(pcmChunk: ByteArray)
    fun onTextResponseChunk(textChunk: String)
    fun onToolCallReceived(toolCall: ToolCall)
    fun onError(error: String)
}

/**
 * Modular interface for real-time multimodal AI session connections (e.g., Gemini Live API).
 */
interface RealtimeSession {
    fun connect()
    fun disconnect()
    fun sendAudioChunk(pcmChunk: ByteArray)
    fun sendText(text: String)
    fun sendToolResult(toolResult: ToolResult)
    fun interrupt()
    fun setListener(listener: RealtimeSessionListener?)
    fun getState(): RealtimeConnectionState
}
