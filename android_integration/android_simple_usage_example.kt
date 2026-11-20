// Simple usage example - replace your current send button click
// In your Activity/Fragment where you have the send button:

class ChatActivity : AppCompatActivity() {
    private lateinit var repository: ChatRepository
    private val userId = "user_${System.currentTimeMillis()}" // Or from auth

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        // Initialize repository
        val apiService = RetrofitClient.getApiService()
        repository = ChatRepository(apiService)

        // Setup send button
        findViewById<Button>(R.id.sendButton).setOnClickListener {
            val message = findViewById<EditText>(R.id.messageInput).text.toString()
            if (message.isNotBlank()) {
                sendMessageToAI(message)
                findViewById<EditText>(R.id.messageInput).text.clear()
            }
        }
    }

    private fun sendMessageToAI(message: String) {
        // Show user message immediately
        addMessageToUI(message, "user")

        // Call API in background
        lifecycleScope.launch {
            repository.sendMessage(userId, message).collect { result ->
                when (result) {
                    is ApiResult.Loading -> {
                        // Show loading indicator
                        findViewById<ProgressBar>(R.id.loadingIndicator).visibility = View.VISIBLE
                    }
                    is ApiResult.Success -> {
                        // Hide loading, show AI response
                        findViewById<ProgressBar>(R.id.loadingIndicator).visibility = View.GONE
                        addMessageToUI(result.data.reply, "assistant")
                    }
                    is ApiResult.Error -> {
                        // Hide loading, show error
                        findViewById<ProgressBar>(R.id.loadingIndicator).visibility = View.GONE
                        Toast.makeText(this@ChatActivity, result.message, Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    private fun addMessageToUI(text: String, sender: String) {
        // Add to your chat UI (RecyclerView, ListView, etc.)
        // This is just an example - implement based on your UI
        val chatContainer = findViewById<LinearLayout>(R.id.chatContainer)
        val messageView = TextView(this).apply {
            this.text = if (sender == "user") "You: $text" else "AI: $text"
            setPadding(16, 8, 16, 8)
        }
        chatContainer.addView(messageView)

        // Scroll to bottom
        findViewById<ScrollView>(R.id.chatScrollView).fullScroll(View.FOCUS_DOWN)
    }
}</content>
<parameter name="filePath">d:\Vennela A.I\android_simple_usage_example.kt