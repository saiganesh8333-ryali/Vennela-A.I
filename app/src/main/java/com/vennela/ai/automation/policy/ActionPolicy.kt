package com.vennela.ai.automation.policy

import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import com.vennela.ai.ActionTypes
import com.vennela.ai.automation.ActionStatus
import com.vennela.ai.automation.ToolCall

/**
 * Result of evaluating an action against safety and permission policies.
 */
data class PolicyEvaluation(
    val isAllowed: Boolean,
    val status: ActionStatus,
    val reason: String? = null,
    val requiredPermission: String? = null,
    val requiresConfirmation: Boolean = false
)

/**
 * Enforces safety boundaries and user confirmation policies for automation tools.
 */
class ActionPolicy {

    /**
     * Evaluates whether a tool call can be safely executed or requires permission / confirmation.
     */
    fun evaluate(toolCall: ToolCall, context: Context): PolicyEvaluation {
        val tool = toolCall.tool
        val args = toolCall.arguments

        return when (tool) {
            ActionTypes.GET_BATTERY_STATUS, ActionTypes.GET_DEVICE_TIME, ActionTypes.OPEN_APP,
            ActionTypes.TOGGLE_FLASHLIGHT, ActionTypes.OPEN_CAMERA, ActionTypes.OPEN_URL,
            ActionTypes.SEARCH_AND_PLAY_MEDIA -> {
                PolicyEvaluation(isAllowed = true, status = ActionStatus.SUCCESS)
            }

            ActionTypes.SET_ALARM -> {
                // Alarms create state on device, auto-allowed if arguments are valid
                val hour = args.getInt("hour", -1)
                val minute = args.getInt("minute", -1)
                if (hour !in 0..23 || minute !in 0..59) {
                    PolicyEvaluation(
                        isAllowed = false,
                        status = ActionStatus.FAILED,
                        reason = "Invalid alarm time. Hour must be 0-23, minute 0-59."
                    )
                } else {
                    PolicyEvaluation(isAllowed = true, status = ActionStatus.SUCCESS)
                }
            }

            ActionTypes.CALL_CONTACT -> {
                val confirmed = args.getBoolean("confirmed", false)
                if (!confirmed) {
                    PolicyEvaluation(
                        isAllowed = false,
                        status = ActionStatus.PENDING_CONFIRMATION,
                        reason = "Direct phone call requires explicit confirmation",
                        requiresConfirmation = true
                    )
                } else {
                    val hasContactsPermission = isPermissionGranted(context, android.Manifest.permission.READ_CONTACTS)
                    val hasCallPermission = isPermissionGranted(context, android.Manifest.permission.CALL_PHONE)

                    if (!hasContactsPermission) {
                        PolicyEvaluation(
                            isAllowed = false,
                            status = ActionStatus.REQUIRES_PERMISSION,
                            reason = "READ_CONTACTS permission is required to resolve contact name",
                            requiredPermission = android.Manifest.permission.READ_CONTACTS
                        )
                    } else if (!hasCallPermission) {
                        PolicyEvaluation(
                            isAllowed = true,
                            status = ActionStatus.SUCCESS,
                            reason = "CALL_PHONE permission not granted, falling back to dialer intent"
                        )
                    } else {
                        PolicyEvaluation(isAllowed = true, status = ActionStatus.SUCCESS)
                    }
                }
            }

            ActionTypes.SEND_MESSAGE -> {
                val confirmed = args.getBoolean("confirmed", false)
                if (!confirmed) {
                    PolicyEvaluation(
                        isAllowed = false,
                        status = ActionStatus.PENDING_CONFIRMATION,
                        reason = "Sending SMS message requires user confirmation",
                        requiresConfirmation = true
                    )
                } else {
                    val hasPermission = isPermissionGranted(context, android.Manifest.permission.SEND_SMS)
                    if (!hasPermission) {
                        PolicyEvaluation(
                            isAllowed = false,
                            status = ActionStatus.REQUIRES_PERMISSION,
                            reason = "SEND_SMS permission is required",
                            requiredPermission = android.Manifest.permission.SEND_SMS
                        )
                    } else {
                        PolicyEvaluation(isAllowed = true, status = ActionStatus.SUCCESS)
                    }
                }
            }

            else -> {
                // Unknown tools are blocked by policy
                PolicyEvaluation(
                    isAllowed = false,
                    status = ActionStatus.BLOCKED_BY_POLICY,
                    reason = "Tool '$tool' is not registered or supported by policy engine"
                )
            }
        }
    }

    private fun isPermissionGranted(context: Context, permission: String): Boolean {
        return try {
            ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
        } catch (e: Throwable) {
            false
        }
    }
}
