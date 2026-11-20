package com.vennela.ai

import java.util.UUID

/**
 * Manages client-side session ID generation and formatting for Vennela AI chat sessions.
 */
object SessionManager {
    private const val SESSION_PREFIX = "android_"

    /**
     * Formats an existing ID to ensure it has the required "android_" prefix,
     * or generates a new session ID if the provided ID is null or blank.
     */
    fun formatSessionId(id: String?): String {
        if (id.isNullOrBlank()) {
            return generateNewSessionId()
        }
        return if (id.startsWith(SESSION_PREFIX)) id else "$SESSION_PREFIX$id"
    }

    /**
     * Generates a new stable session ID with the "android_" prefix.
     */
    fun generateNewSessionId(): String {
        return "$SESSION_PREFIX${UUID.randomUUID()}"
    }
}
