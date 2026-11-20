package com.vennela.ai

import android.util.Base64
import android.util.Log
import com.google.gson.Gson
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.live.realtime.GeminiLiveRealtimeSession
import com.vennela.ai.live.realtime.RealtimeConnectionState
import com.vennela.ai.live.realtime.RealtimeSessionListener
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.unmockkAll
import io.mockk.verify
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class GeminiLiveRealtimeSessionTest {

    private val gson = Gson()
    private lateinit var session: GeminiLiveRealtimeSession
    private lateinit var listener: RealtimeSessionListener

    @Before
    fun setup() {
        mockkStatic(Log::class)
        mockkStatic(Base64::class)
        every { Log.i(any(), any()) } returns 0
        every { Log.d(any(), any()) } returns 0
        every { Log.w(any<String>(), any<String>()) } returns 0
        every { Log.e(any(), any()) } returns 0
        every { Base64.encodeToString(any(), any()) } returns "bGFzdF9hbGlnbmVkX3BjbQ=="
        every { Base64.decode(any<String>(), any()) } returns ByteArray(10) { 1 }

        session = GeminiLiveRealtimeSession(
            userId = "test_user_123",
            sessionId = "test_session_456"
        )
        listener = mockk(relaxed = true)
        session.setListener(listener)
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    @Test
    fun `test session ready frame updates connection state`() {
        val frame = gson.toJson(mapOf("type" to "session.ready"))
        session.handleIncomingFrame(frame)

        verify { listener.onStateChanged(RealtimeConnectionState.CONNECTED) }
    }

    @Test
    fun `test audio frame decoding and response listener dispatch`() {
        val frame = gson.toJson(mapOf("type" to "audio", "data" to "bGFzdF9hbGlnbmVkX3BjbQ=="))
        session.handleIncomingFrame(frame)

        verify { listener.onAudioResponseChunk(any()) }
    }

    @Test
    fun `test text frame response listener dispatch`() {
        val frame = gson.toJson(mapOf("type" to "text", "text" to "Hello Vennela"))
        session.handleIncomingFrame(frame)

        verify { listener.onTextResponseChunk("Hello Vennela") }
    }

    @Test
    fun `test tool call frame parsing and tool router dispatch`() {
        val frame = gson.toJson(
            mapOf(
                "type" to "tool_call",
                "tool" to "GET_BATTERY_STATUS",
                "request_id" to "req_999"
            )
        )
        session.handleIncomingFrame(frame)

        val toolCallSlot = io.mockk.slot<ToolCall>()
        verify { listener.onToolCallReceived(capture(toolCallSlot)) }
        assertEquals("GET_BATTERY_STATUS", toolCallSlot.captured.tool)
        assertEquals("req_999", toolCallSlot.captured.requestId)
    }

    @Test
    fun `test interrupted frame notifies text response`() {
        val frame = gson.toJson(mapOf("type" to "interrupted"))
        session.handleIncomingFrame(frame)

        verify { listener.onTextResponseChunk("[Interrupted]") }
    }

    @Test
    fun `test error frame notifies error listener`() {
        val frame = gson.toJson(mapOf("type" to "error", "message" to "Live engine overloaded"))
        session.handleIncomingFrame(frame)

        verify { listener.onError("Live engine overloaded") }
    }
}
