package com.vennela.ai

import android.content.Context
import android.provider.Settings
import android.util.Log
import io.mockk.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import okhttp3.*
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AgentWebSocketClientTest {

    private lateinit var context: Context
    private lateinit var agentExecutor: AgentExecutor
    private lateinit var wsClient: AgentWebSocketClient
    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    @Before
    fun setup() {
        mockkStatic(Log::class)
        mockkStatic(Settings.Secure::class)
        
        every { Log.d(any(), any()) } returns 0
        every { Log.i(any(), any()) } returns 0
        every { Log.w(any<String>(), any<String>()) } returns 0
        every { Log.e(any(), any()) } returns 0
        every { Log.e(any(), any(), any()) } returns 0
        
        context = mockk(relaxed = true)
        every { Settings.Secure.getString(any(), any()) } returns "test-device-id"
        
        agentExecutor = mockk(relaxed = true)
        every { agentExecutor.getCapabilities() } returns listOf("OPEN_APP", "GET_BATTERY_STATUS")
        
        wsClient = AgentWebSocketClient(context, agentExecutor, testScope)
    }

    @After
    fun tearDown() {
        unmockkAll()
    }


    @Test
    fun `test initial state is disconnected`() {
        assertEquals(AgentWebSocketClient.ConnectionState.DISCONNECTED, wsClient.state)
    }

    @Test
    fun `test getOrCreateAgentId uses SharedPreferences`() {
        val prefs = mockk<android.content.SharedPreferences>(relaxed = true)
        every { context.getSharedPreferences("agent_prefs", Context.MODE_PRIVATE) } returns prefs
        every { prefs.getString("agent_id", null) } returns "existing-agent-id"
        
        // We can't easily test private method call, but we can verify it doesn't crash 
        // and uses the context to get prefs.
        val client = AgentWebSocketClient(context, agentExecutor, testScope)
        verify { context.getSharedPreferences("agent_prefs", Context.MODE_PRIVATE) }
    }
}
