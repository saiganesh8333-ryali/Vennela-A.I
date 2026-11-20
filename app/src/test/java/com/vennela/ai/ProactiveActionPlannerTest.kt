package com.vennela.ai

import android.content.Context
import com.vennela.ai.automation.planner.ProactiveActionPlanner
import io.mockk.mockk
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ProactiveActionPlannerTest {

    private val context: Context = mockk(relaxed = true)
    private val planner = ProactiveActionPlanner(context)

    @Test
    fun `test boredom context suggests chess app`() {
        val candidate = planner.planProactiveCandidate("I am so bored today")
        assertNotNull(candidate)
        assertEquals(ActionTypes.OPEN_APP, candidate?.tool)
        assertEquals("Chess", candidate?.arguments?.getString("package_name"))
    }

    @Test
    fun `test pspk songs context suggests spotify media search`() {
        val candidate = planner.planProactiveCandidate("Vennela, PSPK songs play cheyyi")
        assertNotNull(candidate)
        assertEquals(ActionTypes.SEARCH_AND_PLAY_MEDIA, candidate?.tool)
        assertEquals("PSPK songs", candidate?.arguments?.getString("query"))
        assertEquals("spotify", candidate?.arguments?.getString("preferredApp"))
    }

    @Test
    fun `test unknown context produces no candidate`() {
        val candidate = planner.planProactiveCandidate("What is the capital of France?")
        assertNull(candidate)
    }
}
