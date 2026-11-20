package com.vennela.ai

import android.content.Context
import android.util.Log

/**
 * The core execution engine for the Vennela Android Agent.
 * Responsible for validating and routing actions to the appropriate tools.
 */
class AgentExecutor(private val context: Context) {
    
    private val toolRegistry = ToolRegistry(context)

    /**
     * Executes the given action and returns the result.
     */
    suspend fun executeAction(action: AgentAction): ActionResult {
        Log.d("AgentExecutor", "Received action request: ${action.type}")

        // 1. Validation step
        val (isValid, errorMessage) = action.validate()
        if (!isValid) {
            Log.e("AgentExecutor", "Validation failed: $errorMessage")
            return ActionResult(
                success = false,
                message = errorMessage ?: "Invalid action parameters",
                error = "VALIDATION_ERROR"
            )
        }

        // 2. Resolve Tool
        val tool = toolRegistry.getTool(action.type)
        if (tool == null) {
            val errorMsg = "Unsupported action type: ${action.type}"
            Log.e("AgentExecutor", errorMsg)
            return ActionResult(
                success = false,
                message = errorMsg,
                error = "ACTION_NOT_FOUND"
            )
        }

        // 3. Execute with safety boundaries
        return try {
            tool.execute(context, action.getMergedParameters())
        } catch (e: Exception) {
            val failureMsg = "Critical tool execution failure: ${e.message}"
            Log.e("AgentExecutor", failureMsg, e)
            ActionResult(
                success = false,
                message = "An internal error occurred while performing the action.",
                error = e.javaClass.simpleName
            )
        }
    }

    /**
     * Returns a list of all currently supported actions by the agent.
     */
    fun getCapabilities(): List<String> {
        return toolRegistry.getAvailableActions()
    }
}
