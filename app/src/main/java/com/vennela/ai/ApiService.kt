package com.vennela.ai

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Streaming

data class ChatRequest(
    val message: String,
    val user_id: String,
    val session_id: String
)

data class ChatResponse(
    val response: String? = null,
    val thoughts: String? = null,
    val personality_state: String? = null,
    val agent_action: AgentAction? = null,
    val proactive_suggestions: List<String?>? = null
)

interface ApiService {

    @POST("chat")
    suspend fun sendMessage(
        @Body request: ChatRequest
    ): Response<ChatResponse>

    @Streaming
    @POST("chat/stream")
    suspend fun sendMessageStream(
        @Body request: ChatRequest
    ): Response<ResponseBody>
}
