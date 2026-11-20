// VennelaApiService.kt - Retrofit API interface
import retrofit2.http.POST
import retrofit2.http.Body

interface VennelaApiService {
    @POST("/chat")
    suspend fun sendMessage(
        @Body request: ChatRequest
    ): ChatResponse
}</content>
<parameter name="filePath">d:\Vennela A.I\android_api_service.kt