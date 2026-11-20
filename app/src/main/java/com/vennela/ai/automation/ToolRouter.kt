package com.vennela.ai.automation

import android.content.Context
import android.util.Log
import com.vennela.ai.automation.accessibility.VennelaAccessibilityService
import com.vennela.ai.automation.executor.AndroidActionExecutor
import com.vennela.ai.automation.policy.ActionPolicy
import com.vennela.ai.automation.verifier.ActionVerifier

/**
 * Central Router in the Vennela Automation pipeline orchestrating:
 * ToolCall -> ActionPolicy -> Executor/Accessibility -> ActionVerifier -> ToolResult
 */
class ToolRouter(private val context: Context) {

    private val actionPolicy = ActionPolicy()
    private val nativeExecutor = AndroidActionExecutor(context)
    private val verifier = ActionVerifier()

    suspend fun routeAndExecute(toolCall: ToolCall): ToolResult {
        Log.d("ToolRouter", "Routing tool call: ${toolCall.tool}")

        // 1. Evaluate Action Policy
        val evaluation = actionPolicy.evaluate(toolCall, context)
        if (!evaluation.isAllowed) {
            Log.w("ToolRouter", "Action policy rejected tool ${toolCall.tool}: ${evaluation.reason}")
            return ToolResult(
                success = false,
                tool = toolCall.tool,
                status = evaluation.status,
                message = evaluation.reason,
                error = evaluation.reason ?: "Blocked by Action Policy"
            )
        }

        // 2. Execute Action (Native Executor or Accessibility Service fallback)
        val rawResult: ToolResult = if (toolCall.tool.startsWith("ACCESSIBILITY_")) {
            val service = VennelaAccessibilityService.instance
            if (service == null) {
                ToolResult(
                    success = false,
                    tool = toolCall.tool,
                    status = ActionStatus.FAILED,
                    error = "Vennela Accessibility Service is not enabled. Please enable it in Android Settings."
                )
            } else {
                executeAccessibilityTool(service, toolCall)
            }
        } else {
            nativeExecutor.execute(toolCall)
        }

        // 3. Post-execution Verification
        val verification = verifier.verify(toolCall, rawResult, context)

        // 4. Return Final Verified Tool Result
        return rawResult.copy(
            verified = verification.verified,
            verificationDetails = verification.details
        )
    }

    private fun executeAccessibilityTool(
        service: VennelaAccessibilityService,
        toolCall: ToolCall
    ): ToolResult {
        val args = toolCall.arguments
        return when (toolCall.tool) {
            "ACCESSIBILITY_CLICK" -> service.clickElement(args.getString("target"))
            "ACCESSIBILITY_TYPE" -> service.typeText(args.getString("target"), args.getString("text"))
            "ACCESSIBILITY_SCROLL" -> service.scroll(forward = args.getBoolean("forward", true))
            "ACCESSIBILITY_GO_BACK" -> service.goBack()
            "ACCESSIBILITY_GO_HOME" -> service.goHome()
            else -> ToolResult(
                success = false, tool = toolCall.tool, error = "Unknown accessibility tool"
            )
        }
    }
}
