package com.vennela.ai.automation.accessibility

import android.accessibilityservice.AccessibilityService
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.vennela.ai.automation.ActionStatus
import com.vennela.ai.automation.ToolResult

/**
 * Dedicated Vennela Accessibility Service for Android device UI interaction.
 * Provides safe, reusable primitives for UI automation.
 */
class VennelaAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i("VennelaAccessibility", "Accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Event monitoring if needed
    }

    override fun onInterrupt() {
        Log.w("VennelaAccessibility", "Accessibility service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        if (instance == this) {
            instance = null
        }
    }

    /**
     * Reads and dumps the active accessibility tree into a simplified textual hierarchy.
     */
    fun dumpUiTree(): String {
        val rootNode = rootInActiveWindow ?: return "UI Tree unavailable (root node null)"
        val sb = StringBuilder()
        buildTreeText(rootNode, sb, 0)
        return sb.toString()
    }

    private fun buildTreeText(node: AccessibilityNodeInfo, sb: StringBuilder, depth: Int) {
        val indent = "  ".repeat(depth)
        val text = node.text?.toString()
        val contentDesc = node.contentDescription?.toString()
        val viewId = node.viewIdResourceName
        val clickable = node.isClickable

        if (!text.isNull_or_blank() || !contentDesc.isNull_or_blank() || !viewId.isNull_or_blank()) {
            sb.append(indent)
                .append("[")
                .append(node.className ?: "View")
                .append("]")
            if (!viewId.isNull_or_blank()) sb.append(" id=").append(viewId)
            if (!text.isNull_or_blank()) sb.append(" text=\"").append(text).append("\"")
            if (!contentDesc.isNull_or_blank()) sb.append(" desc=\"").append(contentDesc).append("\"")
            if (clickable) sb.append(" (clickable)")
            sb.append("\n")
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            buildTreeText(child, sb, depth + 1)
        }
    }

    private fun String?.isNull_or_blank(): Boolean = this == null || this.isBlank()

    /**
     * Finds nodes matching text, content description, or view ID.
     */
    fun findNode(target: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        return searchNode(root, target.lowercase())
    }

    private fun searchNode(node: AccessibilityNodeInfo, target: String): AccessibilityNodeInfo? {
        val text = node.text?.toString()?.lowercase()
        val desc = node.contentDescription?.toString()?.lowercase()
        val id = node.viewIdResourceName?.lowercase()

        if (text?.contains(target) == true || desc?.contains(target) == true || id?.contains(target) == true) {
            return node
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val found = searchNode(child, target)
            if (found != null) return found
        }
        return null
    }

    /**
     * Clicks an element matching target query.
     */
    fun clickElement(target: String): ToolResult {
        val node = findNode(target) ?: return ToolResult(
            success = false,
            tool = "ACCESSIBILITY_CLICK",
            status = ActionStatus.FAILED,
            error = "Element not found: $target"
        )

        var clickableNode: AccessibilityNodeInfo? = node
        while (clickableNode != null && !clickableNode.isClickable) {
            clickableNode = clickableNode.parent
        }

        val targetNode = clickableNode ?: node
        val performed = targetNode.performAction(AccessibilityNodeInfo.ACTION_CLICK)

        return ToolResult(
            success = performed,
            tool = "ACCESSIBILITY_CLICK",
            status = if (performed) ActionStatus.SUCCESS else ActionStatus.FAILED,
            message = if (performed) "Clicked '$target'" else "Failed to click '$target'",
            data = mapOf("target" to target)
        )
    }

    /**
     * Types text into a focusable text field matching target query or focused element.
     */
    fun typeText(target: String?, textToType: String): ToolResult {
        val root = rootInActiveWindow ?: return ToolResult(
            success = false, tool = "ACCESSIBILITY_TYPE", error = "Active window unavailable"
        )

        val targetNode = if (!target.isNullOrBlank()) {
            findNode(target)
        } else {
            root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        } ?: return ToolResult(
            success = false, tool = "ACCESSIBILITY_TYPE", error = "Input target node not found"
        )

        val arguments = Bundle()
        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, textToType)
        val performed = targetNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)

        return ToolResult(
            success = performed,
            tool = "ACCESSIBILITY_TYPE",
            status = if (performed) ActionStatus.SUCCESS else ActionStatus.FAILED,
            message = if (performed) "Typed into element" else "Failed to set text",
            data = mapOf("typedText" to textToType)
        )
    }

    /**
     * Scrolls forward or backward in active window.
     */
    fun scroll(forward: Boolean = true): ToolResult {
        val root = rootInActiveWindow ?: return ToolResult(
            success = false, tool = "ACCESSIBILITY_SCROLL", error = "Active window unavailable"
        )

        val scrollableNode = findScrollableNode(root) ?: return ToolResult(
            success = false, tool = "ACCESSIBILITY_SCROLL", error = "No scrollable element found"
        )

        val action = if (forward) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        val performed = scrollableNode.performAction(action)

        return ToolResult(
            success = performed,
            tool = "ACCESSIBILITY_SCROLL",
            status = if (performed) ActionStatus.SUCCESS else ActionStatus.FAILED,
            message = if (performed) "Scrolled ${if (forward) "forward" else "backward"}" else "Scroll action failed"
        )
    }

    private fun findScrollableNode(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isScrollable) return node
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val found = findScrollableNode(child)
            if (found != null) return found
        }
        return null
    }

    /**
     * Performs global Back navigation.
     */
    fun goBack(): ToolResult {
        val performed = performGlobalAction(GLOBAL_ACTION_BACK)
        return ToolResult(
            success = performed,
            tool = "ACCESSIBILITY_GO_BACK",
            status = if (performed) ActionStatus.SUCCESS else ActionStatus.FAILED,
            message = if (performed) "Navigated BACK" else "Failed BACK navigation"
        )
    }

    /**
     * Performs global Home navigation.
     */
    fun goHome(): ToolResult {
        val performed = performGlobalAction(GLOBAL_ACTION_HOME)
        return ToolResult(
            success = performed,
            tool = "ACCESSIBILITY_GO_HOME",
            status = if (performed) ActionStatus.SUCCESS else ActionStatus.FAILED,
            message = if (performed) "Navigated HOME" else "Failed HOME navigation"
        )
    }

    /**
     * Checks if an element matching query exists in active window.
     */
    fun elementExists(target: String): Boolean {
        return findNode(target) != null
    }

    companion object {
        @Volatile
        var instance: VennelaAccessibilityService? = null
            private set

        val isServiceEnabled: Boolean get() = instance != null
    }
}
