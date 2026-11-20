package com.vennela.ai.security

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.vennela.ai.AgentConfig
import com.vennela.ai.BuildConfig

/**
 * Secure Token Manager for Vennela AI Android Companion App.
 * Manages VENNELA_AGENT_TOKEN storage via Android Keystore backed EncryptedSharedPreferences (with safe SharedPreferences fallback).
 * Supports token persistence, loading, rotation, and synchronization with AgentConfig.
 */
object SecureTokenManager {

    private const val TAG = "SecureTokenManager"
    private const val PREF_FILE_NAME = "secure_agent_prefs"
    private const val KEY_AGENT_TOKEN = "vennela_agent_token"

    private var sharedPreferences: SharedPreferences? = null

    /**
     * Initializes the SecureTokenManager and populates AgentConfig.runtimeAgentToken.
     */
    @Synchronized
    fun init(context: Context) {
        val prefs = getPreferences(context)
        val storedToken = prefs.getString(KEY_AGENT_TOKEN, null)?.trim().orEmpty()

        if (storedToken.isNotBlank()) {
            AgentConfig.runtimeAgentToken = storedToken
            Log.i(TAG, "Initialized AgentConfig with persistent secure token.")
        } else if (BuildConfig.VENNELA_AGENT_TOKEN.isNotBlank()) {
            val buildConfigToken = BuildConfig.VENNELA_AGENT_TOKEN.trim()
            AgentConfig.runtimeAgentToken = buildConfigToken
            saveToken(context, buildConfigToken)
            Log.i(TAG, "Initialized AgentConfig from BuildConfig token and saved to secure storage.")
        } else {
            AgentConfig.runtimeAgentToken = ""
            Log.w(TAG, "No agent token found in secure storage or BuildConfig.")
        }
    }

    /**
     * Saves or updates the agent token in secure storage and syncs AgentConfig.
     */
    @Synchronized
    fun saveToken(context: Context, token: String) {
        val trimmedToken = token.trim()
        val prefs = getPreferences(context)
        prefs.edit().putString(KEY_AGENT_TOKEN, trimmedToken).apply()
        AgentConfig.runtimeAgentToken = trimmedToken
        Log.i(TAG, "Agent token updated in secure storage.")
    }

    /**
     * Retrieves the current token from secure storage.
     */
    @Synchronized
    fun getToken(context: Context): String {
        val prefs = getPreferences(context)
        val token = prefs.getString(KEY_AGENT_TOKEN, null)?.trim().orEmpty()
        return token.ifBlank { AgentConfig.runtimeAgentToken }
    }

    /**
     * Clears the agent token from secure storage and AgentConfig.
     */
    @Synchronized
    fun clearToken(context: Context) {
        val prefs = getPreferences(context)
        prefs.edit().remove(KEY_AGENT_TOKEN).apply()
        AgentConfig.runtimeAgentToken = ""
        Log.i(TAG, "Agent token cleared.")
    }

    private fun getPreferences(context: Context): SharedPreferences {
        sharedPreferences?.let { return it }

        val prefs = try {
            createEncryptedPreferences(context)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize EncryptedSharedPreferences, falling back to private SharedPreferences.", e)
            context.applicationContext.getSharedPreferences(PREF_FILE_NAME, Context.MODE_PRIVATE)
        }

        sharedPreferences = prefs
        return prefs
    }

    private fun createEncryptedPreferences(context: Context): SharedPreferences {
        val appContext = context.applicationContext
        val masterKeysClass = Class.forName("androidx.security.crypto.MasterKeys")
        val defaultSpecField = masterKeysClass.getField("AES256_DEFAULT_KEY_SPEC")
        val defaultSpec = defaultSpecField.get(null) as String

        val getOrCreateMethod = masterKeysClass.getMethod("getOrCreate", String::class.java)
        val masterKeyAlias = getOrCreateMethod.invoke(null, defaultSpec) as String

        val prefKeySchemeClass = Class.forName("androidx.security.crypto.EncryptedSharedPreferences\$PrefKeyEncryptionScheme")
        val prefKeyScheme = prefKeySchemeClass.getField("AES256_SKEY_RAW").get(null)

        val prefValueSchemeClass = Class.forName("androidx.security.crypto.EncryptedSharedPreferences\$PrefValueEncryptionScheme")
        val prefValueScheme = prefValueSchemeClass.getField("AES256_GCM").get(null)

        val encryptedPrefsClass = Class.forName("androidx.security.crypto.EncryptedSharedPreferences")
        val createMethod = encryptedPrefsClass.getMethod(
            "create",
            String::class.java,
            String::class.java,
            Context::class.java,
            prefKeySchemeClass,
            prefValueSchemeClass
        )

        return createMethod.invoke(null, PREF_FILE_NAME, masterKeyAlias, appContext, prefKeyScheme, prefValueScheme) as SharedPreferences
    }
}
