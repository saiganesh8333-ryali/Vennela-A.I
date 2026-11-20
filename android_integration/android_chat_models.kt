// ChatModels.kt - Data classes for API requests/responses
import com.google.gson.annotations.SerializedName

/**
 * Request body for /chat endpoint
 */
data class ChatRequest(
    @SerializedName("user_id")
    val userId: String,
    @SerializedName("message")
    val message: String
)

/**
 * Response from /chat endpoint
 */
data class ChatResponse(
    @SerializedName("reply")
    val reply: String,
    @SerializedName("provider")
    val provider: String,
    @SerializedName("relevant_memory")
    val relevantMemory: String? = null,
    @SerializedName("memory_summary")
    val memorySummary: String? = null,
    @SerializedName("latency_ms")
    val latencyMs: Int? = null,
    @SerializedName("error")
    val error: String? = null
)</content>
<parameter name="filePath">d:\Vennela A.I\android_chat_models.kt