package com.vennela.ai

import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionService
import android.speech.SpeechRecognizer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Custom Recognition Service using Whisper.cpp instead of Google STT
 */
class VennelaRecognitionService : RecognitionService() {
    
    private val serviceScope = CoroutineScope(Dispatchers.Main + Job())
    private lateinit var whisper: WhisperEngine

    override fun onCreate() {
        super.onCreate()
        whisper = WhisperEngine(this)
    }

    override fun onStartListening(intent: Intent?, listener: Callback?) {
        listener?.readyForSpeech(Bundle())
        
        serviceScope.launch {
            // Simulated transcription from our custom engine
            val result = whisper.transcribe(shortArrayOf()) 
            
            val bundle = Bundle().apply {
                putStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION, arrayListOf(result))
            }
            listener?.results(bundle)
        }
    }

    override fun onCancel(listener: Callback?) {}

    override fun onStopListening(listener: Callback?) {}
}
