package com.vennela.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SecureTokenManagerTest {

    @Before
    fun setUp() {
        AgentConfig.runtimeAgentToken = ""
    }

    @Test
    fun `inspect androidx security crypto classes`() {
        try {
            val prefKeySchemeClass = Class.forName("androidx.security.crypto.EncryptedSharedPreferences\$PrefKeyEncryptionScheme")
            println("PrefKeyEncryptionScheme enum constants:")
            prefKeySchemeClass.enumConstants?.forEach { println(" - $it") }

            val masterKeysClass = Class.forName("androidx.security.crypto.MasterKeys")
            println("MasterKeys fields:")
            masterKeysClass.fields.forEach { println(" - ${it.name}") }
        } catch (t: Throwable) {
            println("Inspection failed: ${t.message}")
        }
    }

    @Test
    fun `test AgentConfig token trimming and formatting`() {
        AgentConfig.updateToken("  test-secret-token-123  ")
        assertEquals("test-secret-token-123", AgentConfig.runtimeAgentToken)
        assertEquals("test-secret-token-123", AgentConfig.AGENT_TOKEN)
        assertEquals("Bearer test-secret-token-123", AgentConfig.getBearerHeader())
        assertTrue(AgentConfig.hasValidToken())
    }

    @Test
    fun `test AgentConfig empty token returns null bearer header`() {
        AgentConfig.updateToken("   ")
        assertEquals("", AgentConfig.runtimeAgentToken)
        assertFalse(AgentConfig.hasValidToken())
        assertNull(AgentConfig.getBearerHeader())
    }

    @Test
    fun `test backend endpoint URLs remain secured over HTTPS and WSS`() {
        assertEquals("vennela-a-i.onrender.com", AgentConfig.BACKEND_BASE_URL)
        assertEquals("https://vennela-a-i.onrender.com/", AgentConfig.BACKEND_REST_BASE_URL)
        assertEquals("wss://vennela-a-i.onrender.com/ws/gemini/live", AgentConfig.getGeminiLiveWsUrl())
        assertEquals("wss://vennela-a-i.onrender.com/ws/agents/agent_123", AgentConfig.getWsUrl("agent_123"))
    }
}
