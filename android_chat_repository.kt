// ChatRepository.kt - Repository with error handling
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import retrofit2.HttpException
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(
        val code: Int,
        val message: String,
        val throwable: Throwable? = null
    ) : ApiResult<Nothing>()
    object Loading : ApiResult<Nothing>()
}

class ChatRepository(
    private val apiService: VennelaApiService
) {
    fun sendMessage(userId: String, message: String): Flow<ApiResult<ChatResponse>> = flow {
        emit(ApiResult.Loading)

        try {
            // Validate inputs
            if (userId.isBlank() || message.isBlank()) {
                emit(ApiResult.Error(
                    code = 400,
                    message = "User ID and message cannot be empty"
                ))
                return@flow
            }

            if (message.length > 5000) {
                emit(ApiResult.Error(
                    code = 400,
                    message = "Message exceeds maximum length of 5000 characters"
                ))
                return@flow
            }

            val request = ChatRequest(userId, message)
            val response = apiService.sendMessage(request)

            // Check for API-level errors in response
            if (response.error != null) {
                emit(ApiResult.Error(
                    code = 500,
                    message = response.error
                ))
                return@flow
            }

            emit(ApiResult.Success(response))

        } catch (e: HttpException) {
            val errorMessage = parseHttpError(e)
            emit(ApiResult.Error(
                code = e.code(),
                message = errorMessage,
                throwable = e
            ))
        } catch (e: ConnectException) {
            emit(ApiResult.Error(
                code = 0,
                message = "Network connection failed. Check your internet.",
                throwable = e
            ))
        } catch (e: UnknownHostException) {
            emit(ApiResult.Error(
                code = 0,
                message = "Cannot reach server. Check backend URL and network.",
                throwable = e
            ))
        } catch (e: SocketTimeoutException) {
            emit(ApiResult.Error(
                code = 0,
                message = "Request timed out. Server may be slow or offline.",
                throwable = e
            ))
        } catch (e: IOException) {
            emit(ApiResult.Error(
                code = 0,
                message = "Network error: ${e.message}",
                throwable = e
            ))
        } catch (e: Exception) {
            emit(ApiResult.Error(
                code = -1,
                message = "Unexpected error: ${e.message}",
                throwable = e
            ))
        }
    }.flowOn(Dispatchers.IO)

    private fun parseHttpError(e: HttpException): String {
        return when (e.code()) {
            400 -> "Invalid request format. Check user_id and message."
            401 -> "Unauthorized. Authentication required."
            403 -> "Forbidden. Permission denied."
            429 -> "Too many requests. Please wait before sending more messages."
            500 -> "Server error. Please try again later."
            503 -> "Service unavailable. Server is down."
            else -> "HTTP Error ${e.code()}: ${e.message()}"
        }
    }
}</content>
<parameter name="filePath">d:\Vennela A.I\android_chat_repository.kt