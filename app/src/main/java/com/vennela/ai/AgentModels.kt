package com.vennela.ai

/**
 * Represents a request for the Android Agent to perform a specific task.
 * Designed to be extensible for future actions.
 */
data class AgentAction(
    val type: String,
    val parameters: Map<String, Any?> = emptyMap(),
    // Added for compatibility with some backend formats
    val target: String? = null
) {
    /**
     * Validates that required parameters are present and have the correct type.
     * Returns a pair of (isValid, errorMessage).
     */
    fun validate(): Pair<Boolean, String?> {
        return when (type) {
            ActionTypes.OPEN_APP -> {
                val pkg = parameters["package_name"] ?: target
                if (pkg == null) return false to "Missing required parameter: package_name or target"
                if (pkg !is String) return false to "Parameter package_name/target must be a string"
                if (pkg.isBlank()) return false to "Parameter package_name/target cannot be empty"
                true to null
            }
            ActionTypes.TOGGLE_FLASHLIGHT -> {
                val enable = parameters["enable"]
                if (enable != null && enable !is Boolean) return false to "Parameter enable must be a boolean"
                true to null
            }
            ActionTypes.OPEN_URL -> {
                val url = parameters["url"] ?: target
                if (url == null || url !is String || url.isBlank()) return false to "Missing required parameter: url"
                true to null
            }
            ActionTypes.CALL_CONTACT -> {
                val name = parameters["name"] ?: parameters["contact_name"] ?: target
                if (name == null || name !is String || name.isBlank()) return false to "Missing required parameter: name"
                true to null
            }
            ActionTypes.SEND_MESSAGE -> {
                val name = parameters["recipient"] ?: parameters["name"] ?: target
                val message = parameters["message"] ?: parameters["text"]
                if (name == null || name !is String || name.isBlank()) return false to "Missing required parameter: recipient"
                if (message == null || message !is String || message.isBlank()) return false to "Missing required parameter: message"
                true to null
            }
            ActionTypes.SET_ALARM -> {
                val hour = parameters["hour"]
                val minute = parameters["minute"]
                if (hour == null || minute == null) return false to "Missing required parameters: hour and minute"
                true to null
            }
            ActionTypes.SEARCH_AND_PLAY_MEDIA -> {
                val query = parameters["query"] ?: target
                if (query == null || query !is String || query.isBlank()) return false to "Missing required parameter: query"
                true to null
            }
            ActionTypes.GET_BATTERY_STATUS, ActionTypes.GET_DEVICE_TIME, ActionTypes.OPEN_CAMERA -> {
                true to null
            }
            else -> false to "Unsupported action type: $type"
        }
    }

    /**
     * Merged parameters for tool execution.
     */
    fun getMergedParameters(): Map<String, Any?> {
        val merged = parameters.toMutableMap()
        if (target != null && !merged.containsKey("package_name")) {
            merged["package_name"] = target
        }
        return merged
    }
}

/**
 * Represents the outcome of an agent action.
 */
data class ActionResult(
    val success: Boolean,
    val message: String,
    val data: Map<String, Any?>? = null,
    val error: String? = null
)

/**
 * Constants for supported action types to ensure consistency.
 */
object ActionTypes {
    const val GET_BATTERY_STATUS = "GET_BATTERY_STATUS"
    const val GET_DEVICE_TIME = "GET_DEVICE_TIME"
    const val TOGGLE_FLASHLIGHT = "TOGGLE_FLASHLIGHT"
    const val OPEN_APP = "OPEN_APP"
    const val OPEN_URL = "OPEN_URL"
    const val CALL_CONTACT = "CALL_CONTACT"
    const val SEND_MESSAGE = "SEND_MESSAGE"
    const val SET_ALARM = "SET_ALARM"
    const val OPEN_CAMERA = "OPEN_CAMERA"
    const val SEARCH_AND_PLAY_MEDIA = "SEARCH_AND_PLAY_MEDIA"
}

/**
 * WebSocket Transport Models for Vennela Backend Communication.
 */
data class AgentWsMessage(
    val type: String,
    val version: String = "1.0",
    val agent_id: String? = null,
    val device_id: String? = null,
    val platform: String? = null,
    val capabilities: List<String>? = null,
    val token: String? = null,
    val status: String? = null,
    val request_id: String? = null,
    val action: AgentAction? = null,
    val result: ActionResult? = null,
    val error: AgentWsError? = null,
    val timestamp: Long? = null
)

data class AgentWsError(
    val code: String,
    val message: String
)

object WsMessageTypes {
    const val REGISTER = "register"
    const val REGISTERED = "registered"
    const val EXECUTE = "execute"
    const val RESULT = "result"
    const val CANCEL = "cancel"
    const val PING = "ping"
    const val PONG = "pong"
}
