package com.vennela.ai.automation

import com.vennela.ai.AgentAction
import com.vennela.ai.ActionResult

/**
 * Status of action evaluation / execution in the Vennela Automation pipeline.
 */
enum class ActionStatus {
    SUCCESS,
    FAILED,
    PENDING_CONFIRMATION,
    CANCELLED,
    REQUIRES_PERMISSION,
    BLOCKED_BY_POLICY
}

/**
 * Represents structured tool arguments passed to an automation tool.
 */
data class ToolArguments(
    val parameters: Map<String, Any?> = emptyMap()
) {
    @Suppress("UNCHECKED_CAST")
    fun <T> get(key: String): T? = parameters[key] as? T
    fun getString(key: String, default: String = ""): String = (parameters[key] as? String) ?: default
    fun getBoolean(key: String, default: Boolean = false): Boolean = (parameters[key] as? Boolean) ?: default
    fun getInt(key: String, default: Int = 0): Int = (parameters[key] as? Number)?.toInt() ?: default
}

/**
 * Strongly-typed request from AI/Backend to execute an Android action/tool.
 */
data class ToolCall(
    val tool: String,
    val arguments: ToolArguments = ToolArguments(),
    val requestId: String? = null
) {
    /**
     * Helper conversion to backward-compatible AgentAction
     */
    fun toAgentAction(): AgentAction {
        return AgentAction(
            type = tool,
            parameters = arguments.parameters
        )
    }

    companion object {
        fun fromAgentAction(action: AgentAction, requestId: String? = null): ToolCall {
            return ToolCall(
                tool = action.type,
                arguments = ToolArguments(action.getMergedParameters()),
                requestId = requestId
            )
        }
    }
}

/**
 * Strongly-typed result returned after tool execution and verification.
 */
data class ToolResult(
    val success: Boolean,
    val tool: String,
    val status: ActionStatus = if (success) ActionStatus.SUCCESS else ActionStatus.FAILED,
    val message: String? = null,
    val data: Map<String, Any?>? = null,
    val error: String? = null,
    val verified: Boolean = false,
    val verificationDetails: String? = null
) {
    /**
     * Helper conversion to backward-compatible ActionResult
     */
    fun toActionResult(): ActionResult {
        val mergedData = mutableMapOf<String, Any?>()
        data?.let { mergedData.putAll(it) }
        mergedData["verified"] = verified
        verificationDetails?.let { mergedData["verificationDetails"] = it }

        return ActionResult(
            success = success,
            message = message ?: error ?: if (success) "Action executed successfully" else "Action failed",
            data = mergedData.ifEmpty { null },
            error = error
        )
    }

    companion object {
        fun fromActionResult(tool: String, result: ActionResult, verified: Boolean = false, verificationDetails: String? = null): ToolResult {
            return ToolResult(
                success = result.success,
                tool = tool,
                status = if (result.success) ActionStatus.SUCCESS else ActionStatus.FAILED,
                message = result.message,
                data = result.data,
                error = result.error,
                verified = verified,
                verificationDetails = verificationDetails
            )
        }
    }
}
