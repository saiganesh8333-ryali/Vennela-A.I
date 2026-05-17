// ChatViewModel.kt - ViewModel for UI state management
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.collect

data class ChatMessage(
    val id: String = java.util.UUID.randomUUID().toString(),
    val text: String,
    val sender: String,  // "user" or "assistant"
    val timestamp: Long = System.currentTimeMillis(),
    val provider: String? = null,
    val latencyMs: Int? = null,
    val error: String? = null
)

class ChatViewModel(
    private val repository: ChatRepository,
    private val userId: String
) : ViewModel() {

    private val _messages = MutableLiveData<List<ChatMessage>>(emptyList())
    val messages: LiveData<List<ChatMessage>> = _messages

    private val _isLoading = MutableLiveData<Boolean>(false)
    val isLoading: LiveData<Boolean> = _isLoading

    private val _error = MutableLiveData<String?>(null)
    val error: LiveData<String?> = _error

    fun sendMessage(text: String) {
        if (text.isBlank()) return

        // Add user message to UI immediately
        val userMsg = ChatMessage(text = text, sender = "user")
        _messages.value = (_messages.value ?: emptyList()) + userMsg

        // Fetch AI response
        viewModelScope.launch {
            repository.sendMessage(userId, text).collect { result ->
                when (result) {
                    is ApiResult.Loading -> {
                        _isLoading.value = true
                        _error.value = null
                    }
                    is ApiResult.Success -> {
                        _isLoading.value = false
                        val assistantMsg = ChatMessage(
                            text = result.data.reply,
                            sender = "assistant",
                            provider = result.data.provider,
                            latencyMs = result.data.latencyMs
                        )
                        _messages.value = (_messages.value ?: emptyList()) + assistantMsg
                    }
                    is ApiResult.Error -> {
                        _isLoading.value = false
                        _error.value = result.message
                        // Show error message to user
                        val errorMsg = ChatMessage(
                            text = "Error: ${result.message}",
                            sender = "system"
                        )
                        _messages.value = (_messages.value ?: emptyList()) + errorMsg
                    }
                }
            }
        }
    }

    fun clearError() {
        _error.value = null
    }
}</content>
<parameter name="filePath">d:\Vennela A.I\android_chat_viewmodel.kt