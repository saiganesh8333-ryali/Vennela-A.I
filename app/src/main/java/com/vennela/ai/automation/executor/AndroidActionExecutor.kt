package com.vennela.ai.automation.executor

import android.content.Context
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.provider.AlarmClock
import android.provider.ContactsContract
import android.provider.MediaStore
import android.util.Log
import com.vennela.ai.ActionTypes
import com.vennela.ai.AppLauncherTool
import com.vennela.ai.BatteryTool
import com.vennela.ai.FlashlightTool
import com.vennela.ai.TimeTool
import com.vennela.ai.automation.ActionStatus
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.ToolResult

/**
 * Native Android Executor executing platform actions through Intents, Android APIs, and Contacts Provider.
 */
class AndroidActionExecutor(private val context: Context) {

    private val batteryTool = BatteryTool()
    private val timeTool = TimeTool()
    private val flashlightTool = FlashlightTool()
    private val appLauncherTool = AppLauncherTool()

    suspend fun execute(toolCall: ToolCall): ToolResult {
        val tool = toolCall.tool
        val args = toolCall.arguments

        Log.d("AndroidActionExecutor", "Executing native action: $tool")

        return try {
            when (tool) {
                ActionTypes.GET_BATTERY_STATUS -> {
                    val result = batteryTool.execute(context, args.parameters)
                    ToolResult.fromActionResult(tool, result)
                }

                ActionTypes.GET_DEVICE_TIME -> {
                    val result = timeTool.execute(context, args.parameters)
                    ToolResult.fromActionResult(tool, result)
                }

                ActionTypes.TOGGLE_FLASHLIGHT -> {
                    val result = flashlightTool.execute(context, args.parameters)
                    ToolResult.fromActionResult(tool, result)
                }

                ActionTypes.OPEN_APP -> {
                    val result = appLauncherTool.execute(context, args.parameters)
                    ToolResult.fromActionResult(tool, result)
                }

                ActionTypes.OPEN_URL -> {
                    openUrl(args.getString("url"))
                }

                ActionTypes.CALL_CONTACT -> {
                    callContact(
                        name = args.getString("name").ifBlank { args.getString("contact_name") },
                        confirmed = args.getBoolean("confirmed")
                    )
                }

                ActionTypes.SEND_MESSAGE -> {
                    sendMessage(
                        recipient = args.getString("recipient").ifBlank { args.getString("name") },
                        message = args.getString("message").ifBlank { args.getString("text") }
                    )
                }

                ActionTypes.SET_ALARM -> {
                    setAlarm(
                        hour = args.getInt("hour"),
                        minute = args.getInt("minute"),
                        message = args.getString("message", "Vennela Alarm")
                    )
                }

                ActionTypes.OPEN_CAMERA -> {
                    openCamera()
                }

                ActionTypes.SEARCH_AND_PLAY_MEDIA -> {
                    searchAndPlayMedia(
                        query = args.getString("query"),
                        preferredApp = args.getString("preferredApp", "auto")
                    )
                }

                else -> ToolResult(
                    success = false,
                    tool = tool,
                    status = ActionStatus.FAILED,
                    error = "Unsupported tool: $tool"
                )
            }
        } catch (e: Exception) {
            Log.e("AndroidActionExecutor", "Execution exception for $tool: ${e.message}", e)
            ToolResult(
                success = false,
                tool = tool,
                status = ActionStatus.FAILED,
                error = e.message ?: "Execution error"
            )
        }
    }

    private fun openUrl(urlInput: String): ToolResult {
        if (urlInput.isBlank()) {
            return ToolResult(
                success = false, tool = ActionTypes.OPEN_URL, error = "URL cannot be blank"
            )
        }

        var formattedUrl = urlInput.trim()
        if (!formattedUrl.startsWith("http://") && !formattedUrl.startsWith("https://")) {
            formattedUrl = "https://$formattedUrl"
        }

        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(formattedUrl)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(intent)
            ToolResult(
                success = true,
                tool = ActionTypes.OPEN_URL,
                message = "Opened URL: $formattedUrl",
                data = mapOf("url" to formattedUrl)
            )
        } catch (e: Exception) {
            ToolResult(
                success = false, tool = ActionTypes.OPEN_URL, error = "Failed to open URL: ${e.message}"
            )
        }
    }

    private fun callContact(name: String, confirmed: Boolean): ToolResult {
        if (name.isBlank()) {
            return ToolResult(success = false, tool = ActionTypes.CALL_CONTACT, error = "Contact name required")
        }

        val phoneNumber = resolvePhoneNumber(name)
            ?: return ToolResult(
                success = false,
                tool = ActionTypes.CALL_CONTACT,
                error = "Contact '$name' not found in device contacts API"
            )

        val intentAction = if (confirmed) Intent.ACTION_CALL else Intent.ACTION_DIAL
        val intent = Intent(intentAction, Uri.parse("tel:$phoneNumber")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(intent)
            ToolResult(
                success = true,
                tool = ActionTypes.CALL_CONTACT,
                message = if (confirmed) "Calling $name ($phoneNumber)" else "Opened dialer for $name ($phoneNumber)",
                data = mapOf("contact" to name, "phone" to phoneNumber)
            )
        } catch (e: Exception) {
            ToolResult(success = false, tool = ActionTypes.CALL_CONTACT, error = e.message)
        }
    }

    private fun sendMessage(recipient: String, message: String): ToolResult {
        if (recipient.isBlank()) {
            return ToolResult(success = false, tool = ActionTypes.SEND_MESSAGE, error = "Recipient required")
        }

        val phoneNumber = resolvePhoneNumber(recipient) ?: recipient

        val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:$phoneNumber")).apply {
            putExtra("sms_body", message)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(intent)
            ToolResult(
                success = true,
                tool = ActionTypes.SEND_MESSAGE,
                message = "Opened messaging for $recipient with text: $message",
                data = mapOf("recipient" to recipient, "message" to message)
            )
        } catch (e: Exception) {
            ToolResult(success = false, tool = ActionTypes.SEND_MESSAGE, error = e.message)
        }
    }

    private fun setAlarm(hour: Int, minute: Int, message: String): ToolResult {
        val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
            putExtra(AlarmClock.EXTRA_HOUR, hour)
            putExtra(AlarmClock.EXTRA_MINUTES, minute)
            putExtra(AlarmClock.EXTRA_MESSAGE, message)
            putExtra(AlarmClock.EXTRA_SKIP_UI, false)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(intent)
            val formattedTime = String.format("%02d:%02d", hour, minute)
            ToolResult(
                success = true,
                tool = ActionTypes.SET_ALARM,
                message = "Alarm set for $formattedTime ($message)",
                data = mapOf("hour" to hour, "minute" to minute, "message" to message)
            )
        } catch (e: Exception) {
            ToolResult(success = false, tool = ActionTypes.SET_ALARM, error = e.message)
        }
    }

    private fun openCamera(): ToolResult {
        val intent = Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(intent)
            ToolResult(
                success = true,
                tool = ActionTypes.OPEN_CAMERA,
                message = "Opened camera application"
            )
        } catch (e: Exception) {
            ToolResult(success = false, tool = ActionTypes.OPEN_CAMERA, error = e.message)
        }
    }

    private fun searchAndPlayMedia(query: String, preferredApp: String): ToolResult {
        if (query.isBlank()) {
            return ToolResult(
                success = false, tool = ActionTypes.SEARCH_AND_PLAY_MEDIA, error = "Query cannot be blank"
            )
        }

        val app = preferredApp.lowercase()
        val intent: Intent = when {
            app.contains("youtube") -> {
                Intent(Intent.ACTION_SEARCH).apply {
                    setPackage("com.google.android.youtube")
                    putExtra("query", query)
                }
            }
            app.contains("spotify") -> {
                Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
                    setPackage("com.spotify.music")
                    putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
                    putExtra(MediaStore.EXTRA_MEDIA_TITLE, query)
                    putExtra(SearchManagerKey, query)
                }
            }
            else -> {
                Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
                    putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
                    putExtra(MediaStore.EXTRA_MEDIA_TITLE, query)
                    putExtra(SearchManagerKey, query)
                }
            }
        }

        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

        return try {
            context.startActivity(intent)
            ToolResult(
                success = true,
                tool = ActionTypes.SEARCH_AND_PLAY_MEDIA,
                message = "Searching and playing media: '$query' on ${if (app.isBlank() || app == "auto") "default media player" else app}",
                data = mapOf("query" to query, "preferredApp" to preferredApp)
            )
        } catch (e: Exception) {
            // Fallback to web search uri intent if native app search is unavailable
            val webUri = Uri.parse("https://www.youtube.com/results?search_query=" + Uri.encode(query))
            val fallbackIntent = Intent(Intent.ACTION_VIEW, webUri).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            return try {
                context.startActivity(fallbackIntent)
                ToolResult(
                    success = true,
                    tool = ActionTypes.SEARCH_AND_PLAY_MEDIA,
                    message = "Opened web media search for '$query'",
                    data = mapOf("query" to query, "fallback" to true)
                )
            } catch (fallbackEx: Exception) {
                ToolResult(
                    success = false,
                    tool = ActionTypes.SEARCH_AND_PLAY_MEDIA,
                    error = "Failed to launch media play: ${fallbackEx.message}"
                )
            }
        }
    }

    private fun resolvePhoneNumber(contactName: String): String? {
        val resolver = context.contentResolver
        val cursor: Cursor? = resolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME),
            "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?",
            arrayOf("%$contactName%"),
            null
        )

        cursor?.use {
            if (it.moveToFirst()) {
                val numIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
                if (numIdx != -1) {
                    return it.getString(numIdx)
                }
            }
        }
        return null
    }

    companion object {
        private const val SearchManagerKey = "query"
    }
}
