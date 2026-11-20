package com.vennela.ai

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraManager
import android.os.BatteryManager
import com.vennela.ai.automation.ToolArguments
import com.vennela.ai.automation.ToolCall
import com.vennela.ai.automation.executor.AndroidActionExecutor
import java.text.SimpleDateFormat
import java.util.*

/**
 * Base interface for all Android Agent tools.
 */
interface BaseTool {
    val actionType: String
    suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult
}

/**
 * Registry to manage and resolve available tools.
 */
class ToolRegistry(private val context: Context) {
    private val tools = mutableMapOf<String, BaseTool>()

    init {
        registerTool(BatteryTool())
        registerTool(TimeTool())
        registerTool(FlashlightTool())
        registerTool(AppLauncherTool())
        registerTool(UrlTool(context))
        registerTool(CallContactTool(context))
        registerTool(SendMessageTool(context))
        registerTool(SetAlarmTool(context))
        registerTool(OpenCameraTool(context))
        registerTool(SearchAndPlayMediaTool(context))
    }

    fun registerTool(tool: BaseTool) {
        tools[tool.actionType] = tool
    }

    fun getTool(type: String): BaseTool? = tools[type]

    fun getAvailableActions(): List<String> = tools.keys.toList()
}

/**
 * Tool to retrieve current battery level and charging status.
 */
class BatteryTool : BaseTool {
    override val actionType = ActionTypes.GET_BATTERY_STATUS

    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        return try {
            val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            val level = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            val isCharging = batteryManager.isCharging
            
            ActionResult(
                success = true,
                message = "Battery is at $level% and is ${if (isCharging) "charging" else "not charging"}.",
                data = mapOf("level" to level, "isCharging" to isCharging)
            )
        } catch (e: Exception) {
            ActionResult(success = false, message = "Failed to get battery status", error = e.message)
        }
    }
}

/**
 * Tool to retrieve the current system time.
 */
class TimeTool : BaseTool {
    override val actionType = ActionTypes.GET_DEVICE_TIME

    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val sdf = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        val currentTime = sdf.format(Date())
        return ActionResult(
            success = true,
            message = "The current device time is $currentTime.",
            data = mapOf("time" to currentTime)
        )
    }
}

/**
 * Tool to toggle the device flashlight (torch).
 */
class FlashlightTool : BaseTool {
    override val actionType = ActionTypes.TOGGLE_FLASHLIGHT

    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        return try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraId = cameraManager.cameraIdList.firstOrNull() ?: return ActionResult(
                success = false, message = "No camera flash available on this device."
            )
            
            val enable = parameters["enable"] as? Boolean ?: true
            cameraManager.setTorchMode(cameraId, enable)
            
            ActionResult(
                success = true,
                message = "Flashlight turned ${if (enable) "on" else "off"}."
            )
        } catch (e: Exception) {
            ActionResult(success = false, message = "Flashlight control failed", error = e.message)
        }
    }
}

/**
 * Tool to launch an external application by package name or display name.
 */
class AppLauncherTool : BaseTool {
    override val actionType = ActionTypes.OPEN_APP

    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val appIdentifier = parameters["package_name"] as? String
            ?: return ActionResult(success = false, message = "Missing required parameter: package_name")

        return try {
            val packageManager = context.packageManager
            
            var launchIntent = packageManager.getLaunchIntentForPackage(appIdentifier)
            var resolvedPackage = appIdentifier

            if (launchIntent == null) {
                val mainIntent = Intent(Intent.ACTION_MAIN, null).addCategory(Intent.CATEGORY_LAUNCHER)
                val resolvedApps = packageManager.queryIntentActivities(mainIntent, 0)
                
                val matchedApp = resolvedApps.find { 
                    it.loadLabel(packageManager).toString().equals(appIdentifier, ignoreCase = true) 
                }
                
                matchedApp?.let {
                    resolvedPackage = it.activityInfo.packageName
                    launchIntent = packageManager.getLaunchIntentForPackage(resolvedPackage)
                }
            }
            
            if (launchIntent != null) {
                launchIntent!!.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(launchIntent)
                ActionResult(
                    success = true, 
                    message = "Launched application: $resolvedPackage",
                    data = mapOf("package_name" to resolvedPackage)
                )
            } else {
                ActionResult(
                    success = false, 
                    message = "Application not found or not launchable: $appIdentifier. " +
                            "Verify the app name or package ID is correct.",
                    error = "APP_NOT_FOUND"
                )
            }
        } catch (e: Exception) {
            ActionResult(success = false, message = "Failed to launch $appIdentifier", error = e.message)
        }
    }
}

class UrlTool(context: Context) : BaseTool {
    private val executor = AndroidActionExecutor(context)
    override val actionType = ActionTypes.OPEN_URL
    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val call = ToolCall(actionType, ToolArguments(parameters))
        return executor.execute(call).toActionResult()
    }
}

class CallContactTool(context: Context) : BaseTool {
    private val executor = AndroidActionExecutor(context)
    override val actionType = ActionTypes.CALL_CONTACT
    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val call = ToolCall(actionType, ToolArguments(parameters))
        return executor.execute(call).toActionResult()
    }
}

class SendMessageTool(context: Context) : BaseTool {
    private val executor = AndroidActionExecutor(context)
    override val actionType = ActionTypes.SEND_MESSAGE
    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val call = ToolCall(actionType, ToolArguments(parameters))
        return executor.execute(call).toActionResult()
    }
}

class SetAlarmTool(context: Context) : BaseTool {
    private val executor = AndroidActionExecutor(context)
    override val actionType = ActionTypes.SET_ALARM
    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val call = ToolCall(actionType, ToolArguments(parameters))
        return executor.execute(call).toActionResult()
    }
}

class OpenCameraTool(context: Context) : BaseTool {
    private val executor = AndroidActionExecutor(context)
    override val actionType = ActionTypes.OPEN_CAMERA
    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val call = ToolCall(actionType, ToolArguments(parameters))
        return executor.execute(call).toActionResult()
    }
}

class SearchAndPlayMediaTool(context: Context) : BaseTool {
    private val executor = AndroidActionExecutor(context)
    override val actionType = ActionTypes.SEARCH_AND_PLAY_MEDIA
    override suspend fun execute(context: Context, parameters: Map<String, Any?>): ActionResult {
        val call = ToolCall(actionType, ToolArguments(parameters))
        return executor.execute(call).toActionResult()
    }
}
