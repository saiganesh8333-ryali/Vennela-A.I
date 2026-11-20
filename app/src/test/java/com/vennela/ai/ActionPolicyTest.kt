package com.vennela.ai

import android.content.Context
import com.vennela.ai.automation.ActionStatus
import com.vennela.ai.automation.ToolArguments
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.policy.ActionPolicy
import io.mockk.mockk
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ActionPolicyTest {

    private val actionPolicy = ActionPolicy()
    private val context: Context = mockk(relaxed = true)

    @Test
    fun `test battery status tool is safe and allowed`() {
        val toolCall = ToolCall(ActionTypes.GET_BATTERY_STATUS)
        val evaluation = actionPolicy.evaluate(toolCall, context)

        assertTrue(evaluation.isAllowed)
        assertEquals(ActionStatus.SUCCESS, evaluation.status)
    }

    @Test
    fun `test invalid alarm time is rejected by policy`() {
        val toolCall = ToolCall(
            tool = ActionTypes.SET_ALARM,
            arguments = ToolArguments(mapOf("hour" to 25, "minute" to 30))
        )
        val evaluation = actionPolicy.evaluate(toolCall, context)

        assertFalse(evaluation.isAllowed)
        assertEquals(ActionStatus.FAILED, evaluation.status)
        assertTrue(evaluation.reason?.contains("Invalid alarm time") == true)
    }

    @Test
    fun `test call contact without confirmation requires confirmation`() {
        val toolCall = ToolCall(
            tool = ActionTypes.CALL_CONTACT,
            arguments = ToolArguments(mapOf("name" to "Dad", "confirmed" to false))
        )
        val evaluation = actionPolicy.evaluate(toolCall, context)

        assertFalse(evaluation.isAllowed)
        assertTrue(evaluation.requiresConfirmation)
    }
}
