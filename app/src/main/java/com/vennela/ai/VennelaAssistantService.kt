package com.vennela.ai

import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession

class VennelaAssistantService : VoiceInteractionService() {
    override fun onReady() {
        super.onReady()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == Intent.ACTION_ASSIST) {
            showSession(Bundle(), VoiceInteractionSession.SHOW_WITH_ASSIST)
        }
        return super.onStartCommand(intent, flags, startId)
    }
}
