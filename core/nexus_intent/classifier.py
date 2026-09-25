"""
NEXUS Intent Classifier and Structured Action Dispatcher for Vennela AI.
Extracts and validates temporal, task, and reminder intents before execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.reminders.models import Reminder, ReminderStatus
from core.reminders.service import ReminderManager
from core.tasks.models import Task, TaskPriority, TaskStatus
from core.tasks.service import TaskManager
from core.temporal.context import TemporalContext


class NexusIntent(str, Enum):
    TIME_QUERY = "TIME_QUERY"
    DATE_QUERY = "DATE_QUERY"
    TASK_CREATE = "TASK_CREATE"
    TASK_LIST = "TASK_LIST"
    TASK_UPDATE = "TASK_UPDATE"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_CANCEL = "TASK_CANCEL"
    REMINDER_CREATE = "REMINDER_CREATE"
    REMINDER_LIST = "REMINDER_LIST"
    REMINDER_CANCEL = "REMINDER_CANCEL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class NexusIntentResult:
    intent: NexusIntent
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_query: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.intent != NexusIntent.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "raw_query": self.raw_query,
        }


class NexusIntentClassifier:
    """
    Deterministic intent classifier for temporal queries, tasks, and reminders.
    """

    def __init__(self, temporal_context: Optional[TemporalContext] = None) -> None:
        self.temporal = temporal_context or TemporalContext()

    def classify(self, text: str) -> NexusIntentResult:
        if not text or not text.strip():
            return NexusIntentResult(NexusIntent.UNKNOWN, 0.0, {}, text)

        raw = text.strip()
        cleaned = raw.lower()

        # Clean leading invocations e.g. "vennela, ", "hey vennela, ", "please "
        cleaned = re.sub(r"^(?:(?:hey|hi|hello)\s+)?vennela[,\s]*", "", cleaned).strip()
        cleaned = re.sub(r"^please\s+", "", cleaned).strip()

        # 1. TIME_QUERY
        # e.g., "what time is it?", "tell me the time", "current time", "what's the time"
        if re.search(r"\b(?:what(?:\'s|\s+is)?\s+(?:the\s+)?time|tell\s+me\s+(?:the\s+)?time|current\s+time|what\s+time\s+is\s+it)\b", cleaned):
            return NexusIntentResult(
                intent=NexusIntent.TIME_QUERY,
                confidence=0.98,
                entities={"timezone": self.temporal.timezone_name},
                raw_query=raw,
            )

        # 2. DATE / YEAR / MONTH QUERY
        # e.g., "what year is it?", "what year is this?", "what is the current year?", "what's today's date?", "what is the date", "what day is tomorrow?", "what day is it today?"
        is_year_query = bool(re.search(r"\b(?:what(?:\'s|\s+is)?\s+(?:the\s+)?(?:current\s+)?year|what\s+year\s+is\s+(?:it|this)|which\s+year(?:\s+is\s+it|\s+are\s+we\s+in)?|current\s+year)\b", cleaned))
        is_month_query = bool(re.search(r"\b(?:what(?:\'s|\s+is)?\s+(?:the\s+)?(?:current\s+)?month|what\s+month\s+is\s+(?:it|this)|which\s+month(?:\s+is\s+it|\s+are\s+we\s+in)?|current\s+month)\b", cleaned))
        is_date_query = bool(re.search(r"\b(?:what(?:\'s|\s+is)?\s+(?:today(?:\'s)?\s+)?date|what\s+date\s+is\s+it|what\s+day\s+is\s+(?:today|tomorrow|yesterday)|today(?:\'s)?\s+date|what\s+is\s+today|tell\s+me\s+(?:the\s+)?(?:today(?:\'s)?\s+)?date)\b", cleaned))

        if is_year_query or is_month_query or is_date_query:
            target_expr = "today"
            if "tomorrow" in cleaned:
                target_expr = "tomorrow"
            elif "yesterday" in cleaned:
                target_expr = "yesterday"

            query_type = "date"
            if is_year_query:
                query_type = "year"
            elif is_month_query:
                query_type = "month"
            elif "what day" in cleaned:
                query_type = "day"

            return NexusIntentResult(
                intent=NexusIntent.DATE_QUERY,
                confidence=0.98,
                entities={"target_expr": target_expr, "query_type": query_type},
                raw_query=raw,
            )

        # 3. REMINDER_CANCEL
        # e.g., "cancel my 11 PM reminder", "cancel reminder 123", "delete my study maths reminder"
        if re.search(r"\b(?:cancel|delete|remove)\s+(?:my\s+)?(?:reminder\b|.*?\s+reminder\b)", cleaned):
            target = re.sub(r"\b(?:cancel|delete|remove)\s+(?:my\s+)?reminder\s*(?:for|to|about|at)?\s*", "", cleaned).strip()
            target = re.sub(r"\breminder\b", "", target).strip()
            return NexusIntentResult(
                intent=NexusIntent.REMINDER_CANCEL,
                confidence=0.95,
                entities={"target": target or cleaned},
                raw_query=raw,
            )

        # 4. REMINDER_LIST
        # e.g., "show my reminders", "list my reminders", "what are my reminders?", "get reminders"
        if re.search(r"\b(?:show|list|get|view|display|what\s+are)\s+(?:my\s+|all\s+)?reminders\b", cleaned) or cleaned in ("reminders", "my reminders", "show reminders"):
            return NexusIntentResult(
                intent=NexusIntent.REMINDER_LIST,
                confidence=0.95,
                entities={},
                raw_query=raw,
            )

        # 5. REMINDER_CREATE
        # e.g., "Remind me tomorrow at 7 AM to study Maths.", "Remind me at 11 PM to prepare for tomorrow.", "Remind me in 30 minutes to drink water"
        reminder_create_match = re.match(r"^remind\s+(?:me\s+)?(.*)", cleaned)
        if reminder_create_match:
            rest = reminder_create_match.group(1).strip()
            # Attempt to split time expression and action/title
            # Patterns:
            # "tomorrow at 7 AM to study Maths" -> time: "tomorrow at 7 AM", title: "study Maths"
            # "at 11 PM to prepare for tomorrow" -> time: "at 11 PM", title: "prepare for tomorrow"
            # "in 30 minutes to drink water" -> time: "in 30 minutes", title: "drink water"
            # "to study Maths tomorrow at 7 AM" -> title: "study Maths", time: "tomorrow at 7 AM"
            title = ""
            time_expr = ""

            to_match = re.search(r"\bto\s+(.*)", rest)
            if to_match:
                # "tomorrow at 7 AM to study Maths"
                time_candidate = rest[:to_match.start()].strip()
                title_candidate = to_match.group(1).strip()
                resolved = self.temporal.resolve_datetime(time_candidate)
                if resolved:
                    time_expr = time_candidate
                    title = title_candidate

            if not time_expr:
                # Check if "to <action>" came first, e.g. "to call mom at 5 PM"
                to_first = re.match(r"^to\s+(.*?)\s+(?:at|in|on|tomorrow|today|yesterday|next)\s+(.*)", rest)
                if to_first:
                    title_candidate = to_first.group(1).strip()
                    time_candidate = rest[len(title_candidate) + 3:].strip()
                    resolved = self.temporal.resolve_datetime(time_candidate)
                    if resolved:
                        title = title_candidate
                        time_expr = time_candidate

            if not time_expr:
                # Fallback: attempt direct temporal resolution of portions
                title = rest
                time_expr = "in 1 hour"  # default fallback if no explicit time found
                resolved = self.temporal.resolve_datetime(rest)
                if resolved:
                    time_expr = rest
                    title = "Reminder"

            resolved_dt = self.temporal.resolve_datetime(time_expr)
            return NexusIntentResult(
                intent=NexusIntent.REMINDER_CREATE,
                confidence=0.95,
                entities={
                    "title": title.title() if title else "Reminder",
                    "remind_expr": time_expr,
                    "remind_at": resolved_dt.isoformat() if resolved_dt else None,
                    "timezone": self.temporal.timezone_name,
                },
                raw_query=raw,
            )

        # 6. TASK_CREATE
        # e.g., "Create a task to finish my Vennela project tomorrow.", "Add a task to prepare report", "New task: study python"
        if re.search(r"\b(?:create|add|new|set)\s+(?:a\s+)?task\b", cleaned) or cleaned.startswith("task:"):
            # Extract raw substring for title after create task
            match = re.search(r"\b(?:create|add|new|set)\s+(?:a\s+)?task(?:\s+to|:)?\s*", cleaned)
            start_idx = match.end() if match else 0
            rest = raw[start_idx:].strip()
            rest_lower = cleaned[start_idx:].strip()

            due_expr = None
            title = rest

            # Look for temporal markers at the end e.g. "tomorrow", "today", "by Friday", "on Monday"
            temporal_search = re.search(r"\b(?:by|on|for|tomorrow|today|yesterday|next\s+\w+|in\s+\d+\s+\w+)\b.*$", rest_lower)
            if temporal_search:
                cand_expr = temporal_search.group(0).strip()
                # strip preposition
                cand_clean = re.sub(r"^(?:by|on|for)\s+", "", cand_expr).strip()
                resolved = self.temporal.resolve_datetime(cand_clean)
                if resolved:
                    due_expr = cand_clean
                    title = rest[:temporal_search.start()].strip()

            resolved_due_dt = self.temporal.resolve_datetime(due_expr) if due_expr else None
            return NexusIntentResult(
                intent=NexusIntent.TASK_CREATE,
                confidence=0.95,
                entities={
                    "title": title if title else "New Task",
                    "due_expr": due_expr,
                    "due_at": resolved_due_dt.isoformat() if resolved_due_dt else None,
                },
                raw_query=raw,
            )

        # 7. TASK_COMPLETE
        # e.g., "mark my Vennela project task complete", "complete task 123", "mark task finished"
        if re.search(r"\b(?:mark\s+.*?complete|complete\s+(?:task\s+)?|finish\s+(?:task\s+)?)\b", cleaned):
            task_ref = re.sub(r"\b(?:mark|complete|finish|task|my|as|complete|completed|done)\b", "", cleaned).strip()
            return NexusIntentResult(
                intent=NexusIntent.TASK_COMPLETE,
                confidence=0.92,
                entities={"task_ref": task_ref or cleaned},
                raw_query=raw,
            )

        # 8. TASK_CANCEL
        # e.g., "cancel task 123", "delete task buy milk"
        if re.search(r"\b(?:cancel|delete|remove)\s+(?:task\b|my\s+task\b)", cleaned):
            task_ref = re.sub(r"\b(?:cancel|delete|remove)\s+(?:my\s+)?task\s*", "", cleaned).strip()
            return NexusIntentResult(
                intent=NexusIntent.TASK_CANCEL,
                confidence=0.92,
                entities={"task_ref": task_ref or cleaned},
                raw_query=raw,
            )

        # 9. TASK_LIST
        # e.g., "show my tasks for tomorrow", "show today's tasks", "list my tasks", "what are my tasks"
        if re.search(r"\b(?:show|list|get|view|display|what\s+are)\s+(?:my\s+|all\s+)?tasks\b", cleaned) or cleaned in ("tasks", "my tasks", "show tasks"):
            due_date_expr = None
            if "tomorrow" in cleaned:
                due_date_expr = "tomorrow"
            elif "today" in cleaned:
                due_date_expr = "today"
            elif "yesterday" in cleaned:
                due_date_expr = "yesterday"
            return NexusIntentResult(
                intent=NexusIntent.TASK_LIST,
                confidence=0.95,
                entities={"due_date_expr": due_date_expr},
                raw_query=raw,
            )

        return NexusIntentResult(NexusIntent.UNKNOWN, 0.0, {}, raw)


def execute_nexus_intent(
    intent_result: NexusIntentResult,
    task_manager: TaskManager,
    reminder_manager: ReminderManager,
    owner_id: str,
    temporal_context: Optional[TemporalContext] = None,
) -> str:
    """
    Safely and deterministically execute a validated Nexus intent.
    """
    temporal = temporal_context or TemporalContext()

    if intent_result.intent == NexusIntent.TIME_QUERY:
        current_time_str = temporal.format_time()
        return f"It is currently {current_time_str}."

    if intent_result.intent == NexusIntent.DATE_QUERY:
        target_expr = intent_result.entities.get("target_expr", "today")
        query_type = intent_result.entities.get("query_type", "date")

        if query_type == "year":
            today_dt = temporal.now()
            return f"It is {today_dt.year}."
        if query_type == "month":
            today_dt = temporal.now()
            return f"The current month is {today_dt.strftime('%B %Y')}."

        if target_expr == "tomorrow":
            tomorrow_dt = temporal.tomorrow()
            day_name = temporal.day_of_week(tomorrow_dt)
            date_str = temporal.format_date(tomorrow_dt)
            # If user asked "what day is tomorrow?" return day name prominently
            if query_type == "day" or "what day" in intent_result.raw_query.lower():
                return f"Tomorrow is {day_name}."
            return f"Tomorrow's date is {date_str}."
        elif target_expr == "yesterday":
            yesterday_dt = temporal.yesterday()
            day_name = temporal.day_of_week(yesterday_dt)
            return f"Yesterday was {day_name}, {temporal.format_date(yesterday_dt)}."
        else:
            today_dt = temporal.now()
            day_name = temporal.day_of_week(today_dt)
            date_str = temporal.format_date(today_dt)
            if query_type == "day" or "what day" in intent_result.raw_query.lower():
                return f"Today is {day_name}."
            return f"Today is {date_str}."

    if intent_result.intent == NexusIntent.TASK_CREATE:
        title = intent_result.entities.get("title", "New Task")
        due_expr = intent_result.entities.get("due_expr")
        task = task_manager.create_task(
            owner_id=owner_id,
            title=title,
            due_expr=due_expr,
        )
        due_info = f" due {due_expr}" if due_expr else ""
        return f"Task created: '{task.title}'{due_info} (ID: {task.task_id})."

    if intent_result.intent == NexusIntent.TASK_LIST:
        due_date_expr = intent_result.entities.get("due_date_expr")
        tasks = task_manager.list_tasks(owner_id=owner_id, due_date_expr=due_date_expr)
        if not tasks:
            filter_info = f" for {due_date_expr}" if due_date_expr else ""
            return f"You have no tasks{filter_info}."
        lines = [f"- [{t.status.value}] {t.title} (ID: {t.task_id})" for t in tasks]
        filter_info = f" for {due_date_expr}" if due_date_expr else ""
        return f"Your tasks{filter_info}:\n" + "\n".join(lines)

    if intent_result.intent == NexusIntent.TASK_COMPLETE:
        task_ref = intent_result.entities.get("task_ref", "").lower().strip()
        # Find matching task
        all_tasks = task_manager.list_tasks(owner_id=owner_id)
        matched_task: Optional[Task] = None
        for t in all_tasks:
            if t.task_id.lower() == task_ref or task_ref in t.title.lower() or t.title.lower() in task_ref:
                matched_task = t
                break
        if not matched_task:
            # Fallback to first pending task if only one exists or general phrase
            pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]
            if len(pending) == 1:
                matched_task = pending[0]

        if matched_task:
            updated = task_manager.complete_task(owner_id=owner_id, task_id=matched_task.task_id)
            return f"Marked task '{updated.title}' as COMPLETED."
        return f"Could not find a matching task to complete."

    if intent_result.intent == NexusIntent.TASK_CANCEL:
        task_ref = intent_result.entities.get("task_ref", "").lower().strip()
        all_tasks = task_manager.list_tasks(owner_id=owner_id)
        matched_task = None
        for t in all_tasks:
            if t.task_id.lower() == task_ref or task_ref in t.title.lower():
                matched_task = t
                break
        if matched_task:
            task_manager.cancel_task(owner_id=owner_id, task_id=matched_task.task_id)
            return f"Cancelled task '{matched_task.title}'."
        return f"Could not find a matching task to cancel."

    if intent_result.intent == NexusIntent.REMINDER_CREATE:
        title = intent_result.entities.get("title", "Reminder")
        remind_expr = intent_result.entities.get("remind_expr")
        reminder = reminder_manager.create_reminder(
            owner_id=owner_id,
            title=title,
            remind_expr=remind_expr,
        )
        formatted_time = temporal.format_time(reminder.remind_at.astimezone(temporal.tz))
        formatted_date = temporal.format_date(reminder.remind_at.astimezone(temporal.tz))
        return f"Reminder set: '{reminder.title}' for {formatted_date} at {formatted_time}."

    if intent_result.intent == NexusIntent.REMINDER_LIST:
        reminders = reminder_manager.list_reminders(owner_id=owner_id, status=ReminderStatus.PENDING)
        if not reminders:
            return "You have no pending reminders."
        lines = [
            f"- '{r.title}' at {temporal.format_time(r.remind_at.astimezone(temporal.tz))} on {temporal.format_date(r.remind_at.astimezone(temporal.tz))} (ID: {r.reminder_id})"
            for r in reminders
        ]
        return "Your reminders:\n" + "\n".join(lines)

    if intent_result.intent == NexusIntent.REMINDER_CANCEL:
        target = intent_result.entities.get("target", "").lower().strip()
        all_rems = reminder_manager.list_reminders(owner_id=owner_id)
        matched_rem: Optional[Reminder] = None

        # Check by reminder_id or title or time substring
        for r in all_rems:
            r_time_str = temporal.format_time(r.remind_at.astimezone(temporal.tz)).lower()
            if r.reminder_id.lower() == target or target in r.title.lower() or (target and target in r_time_str):
                matched_rem = r
                break

        # If user said "cancel my 11 PM reminder", match time specifically
        if not matched_rem:
            for r in all_rems:
                if r.status == ReminderStatus.PENDING:
                    r_time_str = temporal.format_time(r.remind_at.astimezone(temporal.tz)).lower()
                    if any(part in r_time_str for part in target.split() if len(part) >= 2):
                        matched_rem = r
                        break

        if matched_rem:
            reminder_manager.cancel_reminder(owner_id=owner_id, reminder_id=matched_rem.reminder_id)
            return f"Cancelled reminder '{matched_rem.title}'."
        return "Could not find a matching reminder to cancel."

    return "Intent not recognized."
