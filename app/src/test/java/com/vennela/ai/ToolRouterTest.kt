package com.vennela.ai

import android.content.Context
import android.os.BatteryManager
import android.util.Log
import com.vennela.ai.automation.ActionStatus
import com.vennela.ai.automation.ToolArguments
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolRouter
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.unmockkAll
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ToolRouterTest {

    private lateinit var context: Context
    private lateinit var toolRouter: ToolRouter

    @Before
    fun setup() {
        mockkStatic(Log::class)
        every { Log.d(any(), any()) } returns 0
        every { Log.w(any<String>(), any<String>()) } returns 0
        every { Log.e(any(), any()) } returns 0
        every { Log.i(any(), any()) } returns 0

        context = mockk(relaxed = true)
        toolRouter = ToolRouter(context)
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    @Test
    fun `test battery tool routing and verification`() = runTest {
        val batteryManager = mockk<BatteryManager>()
        every { context.getSystemService(Context.BATTERY_SERVICE) } returns batteryManager
        every { batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) } returns 85
        every { batteryManager.isCharging } returns true

        val toolCall = ToolCall(ActionTypes.GET_BATTERY_STATUS)
        val result = toolRouter.routeAndExecute(toolCall)

        assertTrue(result.success)
        assertEquals(ActionTypes.GET_BATTERY_STATUS, result.tool)
        assertTrue(result.verified)
        assertEquals(85, result.data?.get("level"))
    }

    @Test
    fun `test time tool routing and verification`() = runTest {
        val toolCall = ToolCall(ActionTypes.GET_DEVICE_TIME)
        val result = toolRouter.routeAndExecute(toolCall)

        assertTrue(result.success)
        assertEquals(ActionTypes.GET_DEVICE_TIME, result.tool)
        assertTrue(result.verified)
        assertTrue(result.message?.contains("current device time") == true)
    }

    @Test
    fun `test send message without confirmation requires confirmation policy`() = runTest {
        val toolCall = ToolCall(
            tool = ActionTypes.SEND_MESSAGE,
            arguments = ToolArguments(mapOf("recipient" to "Dad", "message" to "Hello", "confirmed" to false))
        )
        val result = toolRouter.routeAndExecute(toolCall)

        assertFalse(result.success)
        assertEquals(ActionStatus.PENDING_CONFIRMATION, result.status)
        assertTrue(result.error?.contains("requires user confirmation") == true)
    }

    @Test
    fun `test unknown tool is blocked by policy`() = runTest {
        val toolCall = ToolCall(tool = "UNKNOWN_TOOL_XYZ")
        val result = toolRouter.routeAndExecute(toolCall)

        assertFalse(result.success)
        assertEquals(ActionStatus.BLOCKED_BY_POLICY, result.status)
    }
}
