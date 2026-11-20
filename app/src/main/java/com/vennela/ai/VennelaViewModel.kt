package com.vennela.ai

import android.app.Application
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.util.Log
import androidx.compose.runtime.mutableStateListOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.ktx.auth
import com.google.firebase.firestore.Query
import com.google.firebase.firestore.SetOptions
import com.google.firebase.firestore.ktx.firestore
import com.google.firebase.ktx.Firebase
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.*
import kotlin.random.Random

data class VennelaConversation(
    val id: String = "",
    val title: String = "New Conversation",
    val lastMessage: String = "",
    val updatedAt: Long = System.currentTimeMillis()
)

class VennelaViewModel(application: Application) : AndroidViewModel(application) {
    private val db = Firebase.firestore
    private val auth = Firebase.auth
    
    private var voiceManager: VennelaVoiceManager? = null
    private val agentExecutor = AgentExecutor(application)
    
    val messages = mutableStateListOf<ChatMessage>()
    val conversations = mutableStateListOf<VennelaConversation>()
    
    private val _isThinking = MutableStateFlow(false)
    val isThinking = _isThinking.asStateFlow()
    
    private val _isListening = MutableStateFlow(false)
    val isListening = _isListening.asStateFlow()
    
    private val _volumeLevel = MutableStateFlow(0f)
    val volumeLevel = _volumeLevel.asStateFlow()
    
    private val _currentConversationId = MutableStateFlow<String?>(null)
    val currentConversationId = _currentConversationId.asStateFlow()
    
    private val _isReasoningMode = MutableStateFlow(false)
    val isReasoningMode = _isReasoningMode.asStateFlow()

    private val _isLiveConversationActive = MutableStateFlow(false)
    val isLiveConversationActive = _isLiveConversationActive.asStateFlow()

    private val _vennelaState = MutableStateFlow(VennelaState.IDLE)
    val vennelaState = _vennelaState.asStateFlow()

    private val _speechAmplitude = MutableStateFlow(0f)
    val speechAmplitude = _speechAmplitude.asStateFlow()

    private val _personalityState = MutableStateFlow("Balanced")
    val personalityState = _personalityState.asStateFlow()

    private val _proactiveSuggestions = mutableStateListOf<String>()
    val proactiveSuggestions = _proactiveSuggestions

    private val _currentThoughts = MutableStateFlow<String?>(null)
    val currentThoughts = _currentThoughts.asStateFlow()

    private val _partialSpeech = MutableStateFlow("")
    val partialSpeech = _partialSpeech.asStateFlow()

    private var speechJob: Job? = null

    init {
        fetchConversations()
        setupVoiceManager()
    }

    private fun setupVoiceManager() {
        voiceManager = VennelaVoiceManager(getApplication(), object : VennelaVoiceManager.VoiceEventsListener {
            override fun onStateChanged(state: VennelaState) {
                _vennelaState.value = state
                _isListening.value = (state == VennelaState.LISTENING)
            }

            override fun onUserSpeechRecognized(text: String) {
                _partialSpeech.value = ""
                sendMessage(text)
            }

            override fun onPartialSpeech(text: String) {
                _partialSpeech.value = text
            }

            override fun onVolumeChanged(volume: Float) {
                _volumeLevel.value = volume
            }

            override fun onError(message: String) {
                Log.e("VennelaAI", "Voice Manager Error: $message")
            }
        })
    }

    fun fetchConversations() {
        val userId = auth.currentUser?.uid ?: "user_vennela_android"
        db.collection("users").document(userId).collection("conversations")
            .orderBy("updatedAt", Query.Direction.DESCENDING)
            .addSnapshotListener { snapshot, e ->
                if (e != null) return@addSnapshotListener
                if (snapshot != null) {
                    conversations.clear()
                    for (doc in snapshot.documents) {
                        conversations.add(
                            VennelaConversation(
                                id = doc.id,
                                title = doc.getString("title") ?: "New Conversation",
                                lastMessage = doc.getString("lastMessage") ?: "",
                                updatedAt = doc.getLong("updatedAt") ?: System.currentTimeMillis()
                            )
                        )
                    }
                }
            }
    }

    fun toggleReasoningMode() {
        _isReasoningMode.value = !_isReasoningMode.value
    }

    private var liveConversationManager: com.vennela.ai.live.conversation.LiveConversationManager? = null

    fun toggleLiveConversation() {
        _isLiveConversationActive.value = !_isLiveConversationActive.value
        if (_isLiveConversationActive.value) {
            _vennelaState.value = VennelaState.LISTENING
            if (liveConversationManager == null) {
                liveConversationManager = com.vennela.ai.live.conversation.LiveConversationManager(getApplication(), viewModelScope)
            }
            liveConversationManager?.startSession()
            voiceManager?.startListening()
        } else {
            _vennelaState.value = VennelaState.IDLE
            liveConversationManager?.stopSession()
            voiceManager?.stopSpeaking()
            voiceManager?.stopListening()
        }
    }

    private val _isVoiceModeActive = MutableStateFlow(false)
    val isVoiceModeActive = _isVoiceModeActive.asStateFlow()

    fun toggleVoiceMode() {
        _isVoiceModeActive.value = !_isVoiceModeActive.value
        if (_isVoiceModeActive.value) {
            _isLiveConversationActive.value = true
            _vennelaState.value = VennelaState.LISTENING
            if (liveConversationManager == null) {
                liveConversationManager = com.vennela.ai.live.conversation.LiveConversationManager(getApplication(), viewModelScope)
            }
            liveConversationManager?.startSession()
            voiceManager?.startListening()
        } else {
            _isLiveConversationActive.value = false
            _vennelaState.value = VennelaState.IDLE
            liveConversationManager?.stopSession()
            voiceManager?.stopSpeaking()
            voiceManager?.stopListening()
        }
    }

    fun startNewSession() {
        _currentConversationId.value = null
        messages.clear()
        _proactiveSuggestions.clear()
        _currentThoughts.value = null
        voiceManager?.stopSpeaking()
    }

    fun ensureCurrentSessionId(): String {
        val currentId = _currentConversationId.value
        val sessionId = SessionManager.formatSessionId(currentId)
        if (_currentConversationId.value != sessionId) {
            _currentConversationId.value = sessionId
        }
        return sessionId
    }

    fun loadConversation(id: String) {
        val formattedId = SessionManager.formatSessionId(id)
        _currentConversationId.value = formattedId
        messages.clear()
        val userId = auth.currentUser?.uid ?: "user_vennela_android"
        db.collection("users").document(userId)
            .collection("conversations").document(formattedId)
            .collection("messages")
            .orderBy("timestamp", Query.Direction.ASCENDING)
            .get()
            .addOnSuccessListener { result ->
                messages.clear()
                for (document in result) {
                    messages.add(
                        ChatMessage(
                            id = document.id,
                            role = document.getString("role") ?: "user",
                            content = document.getString("content") ?: "",
                            timestamp = document.getLong("timestamp") ?: System.currentTimeMillis()
                        )
                    )
                }
            }
    }

    fun sendMessage(text: String) {
        if (text.isBlank()) return

        val userId = auth.currentUser?.uid ?: "user_vennela_android"
        val conversationId = ensureCurrentSessionId()
        
        val convData = hashMapOf(
            "title" to text.take(30),
            "updatedAt" to System.currentTimeMillis(),
            "lastMessage" to text,
            "userId" to userId
        )
        db.collection("users").document(userId).collection("conversations")
            .document(conversationId).set(convData, SetOptions.merge())

        val timestamp = System.currentTimeMillis()
        messages.add(ChatMessage(role = "user", content = text, timestamp = timestamp))
        
        _isThinking.value = true
        _vennelaState.value = VennelaState.PROCESSING
        _currentThoughts.value = "Establishing neural link..."

        viewModelScope.launch {
            try {
                val volJob = launch {
                    while(_isThinking.value) {
                        _volumeLevel.value = 20f + (Random.nextFloat() * 60f)
                        delay(150)
                    }
                    _volumeLevel.value = 0f
                }

                val request = ChatRequest(
                    message = text,
                    user_id = "boss_001",
                    session_id = conversationId
                )

                Log.d("VennelaAI", "Sending request to core: $request")
                val retrofitResponse = RetrofitInstance.api.sendMessage(request)
                volJob.cancel()

                var finalReply = "Vennela neural core returned an empty response."
                var thoughts = "Processing complete."
                var personality = "Balanced"

                if (retrofitResponse.isSuccessful) {
                    val body = retrofitResponse.body()
                    Log.d("VennelaAI", "API Success. Body: $body")

                    if (body != null) {
                        finalReply = body.response ?: "Empty neural payload received."
                        thoughts = body.thoughts ?: thoughts
                        personality = body.personality_state ?: personality
                        
                        body.proactive_suggestions?.let { list ->
                            _proactiveSuggestions.clear()
                            _proactiveSuggestions.addAll(list.filterNotNull())
                        }

                        // Execute backend-driven automation if present
                        body.agent_action?.let { action ->
                            val result = agentExecutor.executeAction(action)
                            Log.d("VennelaAI", "Chat Automation Result: ${result.message}")
                            // Optionally add a system message or update the reply
                            messages.add(ChatMessage(role = "assistant", content = "[System Action: ${result.message}]"))
                        }
                    }
                } else {
                    val errorBody = retrofitResponse.errorBody()?.string()
                    Log.e("VennelaAI", "API Error ${retrofitResponse.code()}: $errorBody")
                    finalReply = "Vennela core error (${retrofitResponse.code()}). Details: $errorBody"
                }

                _personalityState.value = personality
                _currentThoughts.value = thoughts

                val replyTimestamp = System.currentTimeMillis()
                messages.add(ChatMessage(role = "assistant", content = finalReply, timestamp = replyTimestamp))
                
                if (_isLiveConversationActive.value) {
                    speakResponse(finalReply)
                } else {
                    _vennelaState.value = VennelaState.IDLE
                }
                
                // Persistence
                val currentId = _currentConversationId.value ?: conversationId
                db.collection("users").document(userId).collection("conversations")
                    .document(currentId).collection("messages").add(hashMapOf(
                        "role" to "user", "content" to text, "timestamp" to timestamp
                    ))
                db.collection("users").document(userId).collection("conversations")
                    .document(currentId).collection("messages").add(hashMapOf(
                        "role" to "assistant", "content" to finalReply, "timestamp" to replyTimestamp
                    ))
                db.collection("users").document(userId).collection("conversations")
                    .document(currentId).update("lastMessage", finalReply, "updatedAt", System.currentTimeMillis())

            } catch (e: Exception) {
                Log.e("VennelaAI", "Critical failure in communication pipeline", e)
                val errorMessage = when (e) {
                    is java.net.SocketTimeoutException -> 
                        "Connection timed out. Vennela is taking too long to respond."
                    is java.net.UnknownHostException ->
                        "Cannot reach Vennela server. Check your internet connection."
                    else -> 
                        "Vennela core error: ${e.message ?: "Unknown neural failure"}"
                }
                messages.add(ChatMessage(role = "assistant", content = errorMessage))
                if (_isLiveConversationActive.value) speakResponse(errorMessage)
            } finally {
                _isThinking.value = false
            }
        }
    }

    fun sendMessageStream(text: String, onChunk: (String) -> Unit = {}) {
        if (text.isBlank()) return

        val userId = auth.currentUser?.uid ?: "user_vennela_android"
        val conversationId = ensureCurrentSessionId()

        val convData = hashMapOf(
            "title" to text.take(30),
            "updatedAt" to System.currentTimeMillis(),
            "lastMessage" to text,
            "userId" to userId
        )
        db.collection("users").document(userId).collection("conversations")
            .document(conversationId).set(convData, SetOptions.merge())

        val timestamp = System.currentTimeMillis()
        messages.add(ChatMessage(role = "user", content = text, timestamp = timestamp))

        _isThinking.value = true
        _vennelaState.value = VennelaState.PROCESSING

        viewModelScope.launch {
            try {
                val request = ChatRequest(
                    message = text,
                    user_id = "boss_001",
                    session_id = conversationId
                )

                Log.d("VennelaAI", "Sending stream request to core: $request")
                val retrofitResponse = RetrofitInstance.api.sendMessageStream(request)

                if (retrofitResponse.isSuccessful) {
                    val bodyText = retrofitResponse.body()?.string() ?: ""
                    val replyTimestamp = System.currentTimeMillis()
                    messages.add(ChatMessage(role = "assistant", content = bodyText, timestamp = replyTimestamp))
                    onChunk(bodyText)
                } else {
                    val errorBody = retrofitResponse.errorBody()?.string()
                    messages.add(ChatMessage(role = "assistant", content = "Stream error: $errorBody"))
                }
            } catch (e: Exception) {
                Log.e("VennelaAI", "Stream request failure", e)
                messages.add(ChatMessage(role = "assistant", content = "Stream error: ${e.message}"))
            } finally {
                _isThinking.value = false
                _vennelaState.value = VennelaState.IDLE
            }
        }
    }

    private fun speakResponse(text: String) {
        voiceManager?.stopSpeaking()
        
        speechJob = viewModelScope.launch {
            _vennelaState.value = VennelaState.SPEAKING
            voiceManager?.speak(text)
            
            // Simulation of amplitude pulses during speech for Orb reaction
            while (_vennelaState.value == VennelaState.SPEAKING) {
                _speechAmplitude.value = 0.2f + (Random.nextFloat() * 0.6f)
                delay(100)
            }
            _speechAmplitude.value = 0f
        }
    }

    override fun onCleared() {
        super.onCleared()
        liveConversationManager?.stopSession()
        voiceManager?.destroy()
        speechJob?.cancel()
    }

    fun updateListeningState(isTyping: Boolean) {
        _isListening.value = isTyping
        if (_isLiveConversationActive.value) {
            _vennelaState.value = if (isTyping) VennelaState.LISTENING else VennelaState.IDLE
        }
    }
}
