package com.vennela.ai.automation.planner

import android.content.Context
import com.vennela.ai.ActionTypes
import com.vennela.ai.automation.ToolArguments
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolResult
import com.vennela.ai.automation.ToolRouter

/**
 * Placeholder Proactive Action Planner that evaluates user intent / conversation context
 * and proposes proactive action candidates safely through the ToolRouter and ActionPolicy.
 */
class ProactiveActionPlanner(private val context: Context) {

    private val toolRouter = ToolRouter(context)

    /**
     * Analyzes conversation context text and returns a proactive tool call candidate if appropriate.
     */
    fun planProactiveCandidate(conversationContextText: String): ToolCall? {
        val lower = conversationContextText.lowercase()

        return when {
            lower.contains("bored") || lower.contains("play a game") -> {
                ToolCall(
                    tool = ActionTypes.OPEN_APP,
                    arguments = ToolArguments(mapOf("package_name" to "Chess"))
                )
            }
            lower.contains("latest news") || lower.contains("news play") -> {
                ToolCall(
                    tool = ActionTypes.SEARCH_AND_PLAY_MEDIA,
                    arguments = ToolArguments(mapOf("query" to "latest news", "preferredApp" to "youtube"))
                )
            }
            lower.contains("pspk songs") -> {
                ToolCall(
                    tool = ActionTypes.SEARCH_AND_PLAY_MEDIA,
                    arguments = ToolArguments(mapOf("query" to "PSPK songs", "preferredApp" to "spotify"))
                )
            }
            else -> null
        }
    }

    /**
     * Executes a planned candidate safely via ToolRouter.
     */
    suspend fun executeProactiveCandidate(candidate: ToolCall): ToolResult {
        return toolRouter.routeAndExecute(candidate)
    }
}
