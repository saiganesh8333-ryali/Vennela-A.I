package com.vennela.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionManagerTest {

    @Test
    fun `test generateNewSessionId has android_ prefix and unique value`() {
        val sessionId1 = SessionManager.generateNewSessionId()
        val sessionId2 = SessionManager.generateNewSessionId()

        assertTrue(sessionId1.startsWith("android_"))
        assertTrue(sessionId2.startsWith("android_"))
        assertNotEquals(sessionId1, sessionId2)
    }

    @Test
    fun `test formatSessionId generates new session ID when null or blank`() {
        val nullResult = SessionManager.formatSessionId(null)
        val emptyResult = SessionManager.formatSessionId("")
        val blankResult = SessionManager.formatSessionId("   ")

        assertTrue(nullResult.startsWith("android_"))
        assertTrue(emptyResult.startsWith("android_"))
        assertTrue(blankResult.startsWith("android_"))
    }

    @Test
    fun `test formatSessionId prepends android_ prefix if missing`() {
        val rawId = "custom-uuid-1234"
        val formatted = SessionManager.formatSessionId(rawId)

        assertEquals("android_custom-uuid-1234", formatted)
    }

    @Test
    fun `test formatSessionId preserves existing android_ prefix`() {
        val existingId = "android_stable-session-id"
        val formatted = SessionManager.formatSessionId(existingId)

        assertEquals("android_stable-session-id", formatted)
    }

    @Test
    fun `test chat requests reuse same session_id within same conversation`() {
        var currentSessionId: String? = null

        // Start session / First message
        val firstSessionId = SessionManager.formatSessionId(currentSessionId)
        currentSessionId = firstSessionId

        val request1 = ChatRequest(
            message = "hello Vennela",
            user_id = "boss_001",
            session_id = firstSessionId
        )

        // Second message in same conversation
        val secondSessionId = SessionManager.formatSessionId(currentSessionId)
        val request2 = ChatRequest(
            message = "what can you do?",
            user_id = "boss_001",
            session_id = secondSessionId
        )

        // Retry of message in same conversation
        val retrySessionId = SessionManager.formatSessionId(currentSessionId)
        val requestRetry = ChatRequest(
            message = "what can you do?",
            user_id = "boss_001",
            session_id = retrySessionId
        )

        assertEquals(request1.session_id, request2.session_id)
        assertEquals(request1.session_id, requestRetry.session_id)
        assertTrue(request1.session_id.startsWith("android_"))

        // User starts a new conversation explicitly
        currentSessionId = null
        val newSessionId = SessionManager.formatSessionId(currentSessionId)
        val requestNewConv = ChatRequest(
            message = "new session start",
            user_id = "boss_001",
            session_id = newSessionId
        )

        assertNotEquals(request1.session_id, requestNewConv.session_id)
        assertTrue(requestNewConv.session_id.startsWith("android_"))
    }

    @Test
    fun `test streaming requests contain same session_id`() {
        val conversationId = SessionManager.generateNewSessionId()

        val chatRequest = ChatRequest(
            message = "standard request",
            user_id = "boss_001",
            session_id = conversationId
        )

        val streamRequest = ChatRequest(
            message = "streaming request",
            user_id = "boss_001",
            session_id = conversationId
        )

        assertEquals(chatRequest.session_id, streamRequest.session_id)
        assertTrue(streamRequest.session_id.startsWith("android_"))
    }
}
