package com.vennela.ai

import android.content.Context
import android.util.Log
import io.mockk.*
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class AgentExecutorTest {

    private lateinit var context: Context
    private lateinit var executor: AgentExecutor

    @Before
    fun setup() {
        mockkStatic(Log::class)
        mockkConstructor(android.content.Intent::class)
        every { anyConstructed<android.content.Intent>().addCategory(any()) } returns mockk(relaxed = true)

        every { Log.d(any(), any()) } returns 0
        every { Log.e(any(), any()) } returns 0
        every { Log.e(any(), any(), any()) } returns 0
        
        context = mockk(relaxed = true)
        executor = AgentExecutor(context)
    }

    @After
    fun tearDown() {
        unmockkStatic(Log::class)
        unmockkAll()
    }

    @Test
    fun `test tool registration and capability lookup`() {
        val capabilities = executor.getCapabilities()
        assertTrue(capabilities.contains(ActionTypes.GET_BATTERY_STATUS))
        assertTrue(capabilities.contains(ActionTypes.GET_DEVICE_TIME))
        assertTrue(capabilities.contains(ActionTypes.TOGGLE_FLASHLIGHT))
        assertTrue(capabilities.contains(ActionTypes.OPEN_APP))
    }

    @Test
    fun `test unsupported action returns failure`() = runTest {
        val action = AgentAction(type = "UNKNOWN_ACTION")
        val result = executor.executeAction(action)
        
        assertFalse(result.success)
        assertEquals("VALIDATION_ERROR", result.error)
    }

    @Test
    fun `test open app package name launch success`() = runTest {
        val packageName = "com.android.chrome"
        every { context.packageManager.getLaunchIntentForPackage(packageName) } returns mockk(relaxed = true)
        
        val action = AgentAction(
            type = ActionTypes.OPEN_APP,
            parameters = mapOf("package_name" to packageName)
        )
        val result = executor.executeAction(action)
        
        assertTrue(result.success)
        assertEquals("Launched application: $packageName", result.message)
    }

    @Test
    fun `test open app display name launch success`() = runTest {
        val displayName = "Chrome"
        val packageName = "com.android.chrome"
        val packageManager = context.packageManager
        
        every { packageManager.getLaunchIntentForPackage(displayName) } returns null
        
        val resolveInfo = mockk<android.content.pm.ResolveInfo>()
        every { resolveInfo.loadLabel(packageManager) } returns displayName
        resolveInfo.activityInfo = mockk {
            this.packageName = packageName
        }
        
        every { packageManager.queryIntentActivities(any(), 0) } returns listOf(resolveInfo)
        every { packageManager.getLaunchIntentForPackage(packageName) } returns mockk(relaxed = true)

        val action = AgentAction(
            type = ActionTypes.OPEN_APP,
            parameters = mapOf("package_name" to displayName)
        )
        val result = executor.executeAction(action)
        
        assertTrue(result.success)
        assertEquals("Launched application: $packageName", result.message)
    }

    @Test
    fun `test open app case-insensitive display name match`() = runTest {
        val inputName = "chrome"
        val actualName = "Chrome"
        val packageName = "com.android.chrome"
        val packageManager = context.packageManager
        
        every { packageManager.getLaunchIntentForPackage(inputName) } returns null
        
        val resolveInfo = mockk<android.content.pm.ResolveInfo>()
        every { resolveInfo.loadLabel(packageManager) } returns actualName
        resolveInfo.activityInfo = mockk {
            this.packageName = packageName
        }
        
        every { packageManager.queryIntentActivities(any(), 0) } returns listOf(resolveInfo)
        every { packageManager.getLaunchIntentForPackage(packageName) } returns mockk(relaxed = true)

        val action = AgentAction(
            type = ActionTypes.OPEN_APP,
            parameters = mapOf("package_name" to inputName)
        )
        val result = executor.executeAction(action)
        
        assertTrue(result.success)
        assertEquals("Launched application: $packageName", result.message)
    }

    @Test
    fun `test open app unknown app name failure`() = runTest {
        val appName = "UnknownApp123"
        val packageManager = context.packageManager
        
        every { packageManager.getLaunchIntentForPackage(appName) } returns null
        every { packageManager.queryIntentActivities(any(), 0) } returns emptyList()

        val action = AgentAction(
            type = ActionTypes.OPEN_APP,
            parameters = mapOf("package_name" to appName)
        )
        val result = executor.executeAction(action)
        
        assertFalse(result.success)
        assertEquals("APP_NOT_FOUND", result.error)
    }

    @Test
    fun `test open app empty input validation`() = runTest {
        val action = AgentAction(
            type = ActionTypes.OPEN_APP,
            parameters = mapOf("package_name" to "")
        )
        val result = executor.executeAction(action)
        
        assertFalse(result.success)
        assertTrue(result.message.contains("cannot be empty"))
    }

    @Test
    fun `test open app missing parameter`() = runTest {
        val action = AgentAction(type = ActionTypes.OPEN_APP)
        val result = executor.executeAction(action)
        
        assertFalse(result.success)
        assertTrue(result.message.contains("Missing required parameter"))
    }

    @Test
    fun `test tool execution failure handling`() = runTest {
        // Mocking CameraManager to throw for FlashlightTool
        every { context.getSystemService(android.content.Context.CAMERA_SERVICE) } throws RuntimeException("Service down")
        
        val action = AgentAction(type = ActionTypes.TOGGLE_FLASHLIGHT)
        val result = executor.executeAction(action)
        
        assertFalse(result.success)
        assertEquals("Service down", result.error)
    }

    @Test
    fun `test action validation directly`() {
        val validAction = AgentAction(ActionTypes.OPEN_APP, mapOf("package_name" to "Settings"))
        val (isValid, _) = validAction.validate()
        assertTrue(isValid)

        val invalidAction = AgentAction(ActionTypes.OPEN_APP, mapOf("package_name" to ""))
        val (isValid2, error) = invalidAction.validate()
        assertFalse(isValid2)
        assertEquals("Parameter package_name/target cannot be empty", error)
    }
}
