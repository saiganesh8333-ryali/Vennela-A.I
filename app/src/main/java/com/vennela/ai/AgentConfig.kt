package com.vennela.ai

/**
 * Configuration for the Vennela Android Agent.
 * Preserves MARK-II security standards: zero hardcoded production tokens in Git.
 */
object AgentConfig {
    /**
     * The base URL for the Vennela Backend.
     */
    const val BACKEND_BASE_URL = "vennela-a-i.onrender.com"
    
    /**
     * HTTP Base URL for REST endpoints.
     */
    const val BACKEND_REST_BASE_URL = "https://$BACKEND_BASE_URL/"

    /**
     * Deployed Vennela Gemini Live backend WebSocket endpoint.
     */
    const val GEMINI_LIVE_WS_ENDPOINT = "/ws/gemini/live"

    /**
     * Default Agent WebSocket endpoint path.
     */
    const val WS_ENDPOINT = "/ws/agents/"

    /**
     * Dynamically populated Agent authentication token.
     * Single source of truth for REST and WebSocket authentication.
     */
    @Volatile
    var runtimeAgentToken: String = BuildConfig.VENNELA_AGENT_TOKEN
        get() = field.trim()
        set(value) {
            field = value.trim()
        }

    /**
     * Backward-compatible accessor for agent token.
     */
    val AGENT_TOKEN: String
        get() = runtimeAgentToken

    /**
     * Returns true if a valid non-blank token is present.
     */
    fun hasValidToken(): Boolean {
        return runtimeAgentToken.isNotBlank()
    }

    /**
     * Returns the formatted Authorization header value (e.g. "Bearer <token>"),
     * or null if the token is empty/blank.
     */
    fun getBearerHeader(): String? {
        val token = runtimeAgentToken
        return if (token.isNotBlank()) "Bearer $token" else null
    }

    /**
     * Updates the runtime agent token.
     */
    fun updateToken(newToken: String) {
        runtimeAgentToken = newToken
    }

    /**
     * Returns the backend WebSocket URL for Gemini Live session.
     */
    fun getGeminiLiveWsUrl(): String {
        return "wss://$BACKEND_BASE_URL$GEMINI_LIVE_WS_ENDPOINT"
    }

    /**
     * Returns the full WebSocket URL for a given agent ID.
     */
    fun getWsUrl(agentId: String): String {
        return "wss://$BACKEND_BASE_URL$WS_ENDPOINT$agentId"
    }
}
