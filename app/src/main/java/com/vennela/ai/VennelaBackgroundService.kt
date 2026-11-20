package com.vennela.ai

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.unit.IntOffset
import com.google.firebase.auth.ktx.auth
import com.google.firebase.ktx.Firebase
import androidx.core.app.NotificationCompat
import androidx.lifecycle.*
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.*
import kotlin.math.roundToInt

import com.vennela.ai.security.SecureTokenManager

class VennelaBackgroundService : LifecycleService(), SavedStateRegistryOwner, ViewModelStoreOwner {

    private lateinit var windowManager: WindowManager
    private var overlayView: ComposeView? = null
    private var voiceManager: VennelaVoiceManager? = null
    private lateinit var agentExecutor: AgentExecutor
    private var wsClient: AgentWebSocketClient? = null
    private var sessionId = SessionManager.generateNewSessionId()
    
    private val isSpeaking = mutableStateOf(false)
    private val isListening = mutableStateOf(false)
    private val volumeLevel = mutableFloatStateOf(0f)
    private val vennelaState = mutableStateOf(VennelaState.IDLE)
    
    private val savedStateRegistryController = SavedStateRegistryController.create(this)
    private val _viewModelStore = ViewModelStore()

    override val savedStateRegistry: SavedStateRegistry get() = savedStateRegistryController.savedStateRegistry
    override val viewModelStore: ViewModelStore get() = _viewModelStore

    override fun onCreate() {
        super.onCreate()
        savedStateRegistryController.performRestore(null)
        SecureTokenManager.init(applicationContext)
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        agentExecutor = AgentExecutor(this)
        
        wsClient = AgentWebSocketClient(this, agentExecutor, lifecycleScope)
        wsClient?.connect()

        setupVoiceManager()
        startForegroundService()
    }

    private fun setupVoiceManager() {
        voiceManager = VennelaVoiceManager(this, object : VennelaVoiceManager.VoiceEventsListener {
            override fun onStateChanged(state: VennelaState) {
                vennelaState.value = state
                isListening.value = (state == VennelaState.LISTENING)
                isSpeaking.value = (state == VennelaState.SPEAKING)
                if (state != VennelaState.IDLE) showOverlay()
            }

            override fun onUserSpeechRecognized(text: String) {
                processUserQuery(text)
            }

            override fun onPartialSpeech(text: String) {}

            override fun onVolumeChanged(volume: Float) {
                volumeLevel.floatValue = volume
            }

            override fun onError(message: String) {
                Log.e("VennelaAI", "Service Voice Error: $message")
            }
        })
    }

    private fun startForegroundService() {
        val channelId = "VennelaVoiceChannel"
        val channel = NotificationChannel(channelId, "Vennela AI Core", NotificationManager.IMPORTANCE_LOW)
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)

        val notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("Vennela AI Active")
            .setContentText("Listening for commands...")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(1001, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(1001, notification)
        }
    }

    private fun startListening() {
        if (!Settings.canDrawOverlays(this)) return
        voiceManager?.startListening()
    }

    private fun processUserQuery(query: String) {
        lifecycleScope.launch {
            // Check for local automation commands first (Phase 1)
            if (handleLocalAutomation(query)) return@launch

            try {
                val request = ChatRequest(
                    message = query,
                    user_id = "boss_001",
                    session_id = sessionId
                )
                
                val retrofitResponse = RetrofitInstance.api.sendMessage(request)
                
                var finalReply = "Vennela neural core returned an empty response."
                
                if (retrofitResponse.isSuccessful) {
                    val body = retrofitResponse.body()
                    if (body != null) {
                        finalReply = body.response ?: "Empty response received."
                        
                        // Execute backend-driven automation if present
                        body.agent_action?.let { action ->
                            val result = agentExecutor.executeAction(action)
                            Log.d("VennelaAI", "Automation Result: ${result.message}")
                            // Optionally speak the result if the main response is empty
                            if (finalReply.isEmpty() || finalReply.contains("empty", ignoreCase = true)) {
                                finalReply = result.message
                            }
                        }
                    }
                } else {
                    val errorBody = retrofitResponse.errorBody()?.string()
                    finalReply = "Core system failure: $errorBody"
                }
                
                speakResponse(finalReply)
            } catch (e: Exception) {
                val errorMsg = e.message ?: "Internal system error"
                speakResponse("Neural core failure: $errorMsg. Reconnecting...")
            }
        }
    }

    /**
     * Attempts to handle specific automation commands locally (Phase 1).
     * Returns true if the command was handled, false otherwise.
     */
    private suspend fun handleLocalAutomation(query: String): Boolean {
        val lowerQuery = query.lowercase(Locale.getDefault())
        
        // "Vennela, what time is it?"
        if (lowerQuery.contains("what time") || lowerQuery.contains("current time")) {
            val result = agentExecutor.executeAction(AgentAction(ActionTypes.GET_DEVICE_TIME))
            speakResponse(result.message)
            return true
        }

        // "Vennela, battery status?"
        if (lowerQuery.contains("battery") && (lowerQuery.contains("status") || lowerQuery.contains("level") || lowerQuery.contains("percent"))) {
            val result = agentExecutor.executeAction(AgentAction(ActionTypes.GET_BATTERY_STATUS))
            speakResponse(result.message)
            return true
        }

        // "Vennela, flashlight on/off?"
        if (lowerQuery.contains("flashlight") || lowerQuery.contains("torch")) {
            val enable = !lowerQuery.contains("off")
            val result = agentExecutor.executeAction(
                AgentAction(ActionTypes.TOGGLE_FLASHLIGHT, mapOf("enable" to enable))
            )
            speakResponse(result.message)
            return true
        }

        return false
    }

    private fun speakResponse(text: String) {
        voiceManager?.speak(text)
    }

    private fun showOverlay() {
        if (!Settings.canDrawOverlays(this)) return

        lifecycleScope.launch {
            if (overlayView != null) return@launch
            
            try {
                val params = WindowManager.LayoutParams(
                    WindowManager.LayoutParams.WRAP_CONTENT,
                    WindowManager.LayoutParams.WRAP_CONTENT,
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                    PixelFormat.TRANSLUCENT
                ).apply {
                    gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
                    y = 100
                }

                overlayView = ComposeView(this@VennelaBackgroundService).apply {
                    setViewTreeLifecycleOwner(this@VennelaBackgroundService)
                    setViewTreeSavedStateRegistryOwner(this@VennelaBackgroundService)
                    setViewTreeViewModelStoreOwner(this@VennelaBackgroundService)
                    setContent {
                        DraggableVennelaOrb(params)
                    }
                }

                windowManager.addView(overlayView, params)
            } catch (e: Exception) {
                overlayView = null
            }
        }
    }

    @Composable
    private fun DraggableVennelaOrb(params: WindowManager.LayoutParams) {
        val state by vennelaState
        val vol by volumeLevel
        
        Box(
            modifier = Modifier
                .pointerInput(Unit) {
                    detectDragGestures { change, dragAmount ->
                        change.consume()
                        params.x += dragAmount.x.roundToInt()
                        params.y += dragAmount.y.roundToInt()
                        windowManager.updateViewLayout(overlayView, params)
                    }
                }
        ) {
            VennelaOrb(
                state = state,
                audioAmplitude = if (state == VennelaState.LISTENING) vol / 10f else 0f,
                speechAmplitude = if (state == VennelaState.SPEAKING) vol / 10f else 0f
            )
        }
    }

    private fun hideOverlay() {
        lifecycleScope.launch {
            overlayView?.let {
                if (it.isAttachedToWindow) windowManager.removeView(it)
                overlayView = null
            }
        }
    }

    private fun startNewVoiceSession() {
        sessionId = SessionManager.generateNewSessionId()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        if (intent?.action == "START_VOICE_SESSION") {
            startNewVoiceSession()
            startListening()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        wsClient?.disconnect()
        voiceManager?.destroy()
        _viewModelStore.clear()
        hideOverlay()
    }

    override fun onBind(intent: Intent): IBinder? {
        super.onBind(intent)
        return null
    }
}
