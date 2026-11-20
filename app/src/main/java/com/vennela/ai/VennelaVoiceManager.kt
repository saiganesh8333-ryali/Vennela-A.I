package com.vennela.ai

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.util.Log
import java.util.*

/**
 * Robust manager for Speech-To-Text and Text-To-Speech integration.
 * Handles premium voice selection, reliable STT lifecycle, and Barge-in behavior.
 */
class VennelaVoiceManager(
    private val context: Context,
    private val listener: VoiceEventsListener
) : TextToSpeech.OnInitListener {

    interface VoiceEventsListener {
        fun onStateChanged(state: VennelaState)
        fun onUserSpeechRecognized(text: String)
        fun onPartialSpeech(text: String)
        fun onVolumeChanged(volume: Float)
        fun onError(message: String)
    }

    private var tts: TextToSpeech? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var isTtsInitialized = false
    private var isListening = false
    private var isSpeaking = false

    private val mainHandler = Handler(Looper.getMainLooper())
    private var restartListenerDelay: Long = 1000

    init {
        tts = TextToSpeech(context, this)
        initRecognizer()
    }

    private fun initRecognizer() {
        mainHandler.post {
            if (speechRecognizer != null) {
                speechRecognizer?.destroy()
            }
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
            speechRecognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    Log.d("VennelaVoice", "STT: Ready for speech")
                    listener.onStateChanged(VennelaState.LISTENING)
                }

                override fun onBeginningOfSpeech() {
                    Log.d("VennelaVoice", "STT: User started speaking")
                    // Barge-in: If user starts speaking while TTS is active, stop TTS
                    if (isSpeaking) {
                        stopSpeaking()
                    }
                }

                override fun onRmsChanged(rmsdB: Float) {
                    listener.onVolumeChanged(rmsdB)
                }

                override fun onBufferReceived(buffer: ByteArray?) {}

                override fun onEndOfSpeech() {
                    Log.d("VennelaVoice", "STT: End of speech")
                    isListening = false
                }

                override fun onError(error: Int) {
                    isListening = false
                    val message = when (error) {
                        SpeechRecognizer.ERROR_NO_MATCH -> "No speech match found"
                        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Speech timeout"
                        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognizer busy"
                        SpeechRecognizer.ERROR_NETWORK -> "Network error"
                        else -> "STT Error code: $error"
                    }
                    Log.e("VennelaVoice", "STT Error: $message")
                    
                    // Controlled restart for temporary errors
                    if (error != SpeechRecognizer.ERROR_RECOGNIZER_BUSY) {
                        mainHandler.postDelayed({ 
                            if (!isSpeaking) startListening() 
                        }, restartListenerDelay)
                    }
                }

                override fun onResults(results: Bundle?) {
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        val text = matches[0]
                        Log.d("VennelaVoice", "STT Result: $text")
                        listener.onUserSpeechRecognized(text)
                    } else {
                        startListening()
                    }
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        listener.onPartialSpeech(matches[0])
                    }
                }

                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isTtsInitialized = true
            setupPremiumVoice()
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    isSpeaking = true
                    mainHandler.post { listener.onStateChanged(VennelaState.SPEAKING) }
                }

                override fun onDone(utteranceId: String?) {
                    isSpeaking = false
                    mainHandler.post { 
                        listener.onStateChanged(VennelaState.LISTENING)
                        startListening() 
                    }
                }

                override fun onError(utteranceId: String?) {
                    isSpeaking = false
                    mainHandler.post { startListening() }
                }
            })
        } else {
            listener.onError("TTS Initialization failed")
        }
    }

    private fun setupPremiumVoice() {
        val voices = tts?.voices
        if (voices.isNullOrEmpty()) {
            Log.w("VennelaVoice", "No TTS voices found on device")
            tts?.language = Locale.US
            return
        }

        // Diagnostic log of available voices (without sensitive data)
        Log.d("VennelaVoice", "Scanning available voices...")
        
        // Strategy: Look for "natural", "premium", "google", "female" in English
        val bestVoice = voices.filter { voice ->
            val name = voice.name.lowercase()
            val locale = voice.locale
            val isEnglish = locale.language.startsWith("en")
            
            // Heuristic for high quality female voices
            val isFemale = name.contains("female") || 
                           name.contains("a-") || 
                           name.contains("f-") || 
                           name.contains("network") ||
                           name.contains("premium")

            isEnglish && isFemale
        }.maxByOrNull { it.quality } ?: voices.firstOrNull { it.locale.language.startsWith("en") }

        bestVoice?.let {
            Log.d("VennelaVoice", "Selected Premium Voice: ${it.name} (Quality: ${it.quality})")
            tts?.voice = it
        }

        // Futuring Tuning for natural female assistant
        tts?.setPitch(1.02f)
        tts?.setSpeechRate(0.96f)
    }

    fun startListening() {
        if (isSpeaking) return
        
        mainHandler.post {
            try {
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                }
                speechRecognizer?.startListening(intent)
                isListening = true
            } catch (e: Exception) {
                Log.e("VennelaVoice", "Failed to start listening", e)
                initRecognizer() // Recreate on failure
            }
        }
    }

    fun speak(text: String) {
        if (!isTtsInitialized) return
        
        stopListening()
        
        val params = Bundle().apply {
            putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, "VennelaSpeech")
        }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, params, "VennelaSpeech")
    }

    fun stopSpeaking() {
        tts?.stop()
        isSpeaking = false
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
        isListening = false
    }

    fun destroy() {
        tts?.shutdown()
        speechRecognizer?.destroy()
        mainHandler.removeCallbacksAndMessages(null)
    }
}
