package com.vennela.ai

import android.content.Context
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolResult
import com.vennela.ai.automation.verifier.ActionVerifier
import io.mockk.mockk
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ActionVerifierTest {

    private val verifier = ActionVerifier()
    private val context: Context = mockk(relaxed = true)

    @Test
    fun `test battery telemetry verification success`() {
        val toolCall = ToolCall(ActionTypes.GET_BATTERY_STATUS)
        val result = ToolResult(
            success = true,
            tool = ActionTypes.GET_BATTERY_STATUS,
            data = mapOf("level" to 90, "isCharging" to false)
        )

        val verification = verifier.verify(toolCall, result, context)
        assertTrue(verification.verified)
        assertTrue(verification.details.contains("Level 90%"))
    }

    @Test
    fun `test failed action skips verification`() {
        val toolCall = ToolCall(ActionTypes.OPEN_APP)
        val result = ToolResult(
            success = false,
            tool = ActionTypes.OPEN_APP,
            error = "APP_NOT_FOUND"
        )

        val verification = verifier.verify(toolCall, result, context)
        assertFalse(verification.verified)
        assertTrue(verification.details.contains("skipping verification"))
    }
}
