// 🔥 CORRECT Retrofit setup for your backend
// VennelaApiService.kt - MUST be exactly like this

import retrofit2.http.POST
import retrofit2.http.Body

interface VennelaApiService {
    // ✅ CORRECT: POST method, no leading slash
    @POST("chat")
    suspend fun sendMessage(
        @Body request: ChatRequest
    ): ChatResponse
}</content>
<parameter name="filePath">d:\Vennela A.I\android_correct_api_service.kt