"""
Temporal Context Foundation for Vennela AI.
Shared, timezone-aware, deterministic temporal resolution for Tasks, Reminders, NEXUS, and Scheduler.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Kolkata"

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class TemporalContext:
    """
    Timezone-aware, deterministic temporal context provider and natural language parser.
    """

    def __init__(self, tz_name: str = DEFAULT_TIMEZONE, fixed_now: Optional[datetime] = None) -> None:
        try:
            self._tz = ZoneInfo(tz_name)
            self._tz_name = tz_name
        except Exception:
            self._tz = ZoneInfo("UTC")
            self._tz_name = "UTC"
        self._fixed_now = fixed_now

    @property
    def timezone_name(self) -> str:
        return self._tz_name

    @property
    def tz(self) -> ZoneInfo:
        return self._tz

    def now(self) -> datetime:
        """Get current timezone-aware datetime."""
        if self._fixed_now is not None:
            if self._fixed_now.tzinfo is None:
                return self._fixed_now.replace(tzinfo=self._tz)
            return self._fixed_now.astimezone(self._tz)
        return datetime.now(self._tz)

    def current_date(self) -> date:
        """Get current date in context timezone."""
        return self.now().date()

    def current_time(self) -> time:
        """Get current time in context timezone."""
        return self.now().time()

    def day_of_week(self, dt: Optional[datetime] = None) -> str:
        """Get day of week name (e.g. 'Wednesday')."""
        target = dt if dt is not None else self.now()
        return target.strftime("%A")

    def today(self) -> datetime:
        """Get start of today in context timezone."""
        n = self.now()
        return datetime(n.year, n.month, n.day, 0, 0, 0, tzinfo=self._tz)

    def tomorrow(self) -> datetime:
        """Get start of tomorrow in context timezone."""
        return self.today() + timedelta(days=1)

    def yesterday(self) -> datetime:
        """Get start of yesterday in context timezone."""
        return self.today() - timedelta(days=1)

    def format_time(self, dt: Optional[datetime] = None) -> str:
        """Format time nicely, e.g. '10:30 PM'."""
        target = dt if dt is not None else self.now()
        return target.strftime("%I:%M %p").lstrip("0")

    def format_date(self, dt: Optional[datetime] = None) -> str:
        """Format date nicely, e.g. 'Wednesday, 09 September 2026'."""
        target = dt if dt is not None else self.now()
        return target.strftime("%A, %d %B %Y")

    def resolve_datetime(self, expr: str, base_dt: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parse and resolve a natural language temporal expression into a timezone-aware datetime.
        Supports:
        - "in 30 minutes", "in 2 hours", "in 1 day", "in 45 seconds"
        - "today", "tomorrow", "yesterday"
        - "at 8 PM", "at 7:30 AM", "8 PM", "11:00 PM"
        - "tomorrow at 7 AM", "today at 10 PM", "yesterday at 3 PM"
        - "Friday", "next Monday", "next Friday at 4 PM"
        - ISO strings: "2026-09-10T07:00:00"
        """
        if not expr or not expr.strip():
            return None

        clean_expr = expr.strip().lower()
        base = base_dt if base_dt is not None else self.now()
        if base.tzinfo is None:
            base = base.replace(tzinfo=self._tz)
        else:
            base = base.astimezone(self._tz)

        # Direct ISO format check
        try:
            iso_dt = datetime.fromisoformat(clean_expr.replace("z", "+00:00"))
            if iso_dt.tzinfo is None:
                return iso_dt.replace(tzinfo=self._tz)
            return iso_dt.astimezone(self._tz)
        except ValueError:
            pass

        # 1. Relative duration: "in X minutes/hours/days/seconds"
        duration_match = re.match(
            r"^in\s+(\d+(?:\.\d+)?)\s+(minute|min|hour|hr|day|second|sec)s?$",
            clean_expr,
        )
        if duration_match:
            amount = float(duration_match.group(1))
            unit = duration_match.group(2)
            if unit in ("minute", "min"):
                return base + timedelta(minutes=amount)
            if unit in ("hour", "hr"):
                return base + timedelta(hours=amount)
            if unit == "day":
                return base + timedelta(days=amount)
            if unit in ("second", "sec"):
                return base + timedelta(seconds=amount)

        # Extract potential time component (e.g., "at 7 AM", "7:30 PM", "8 PM", "11 PM")
        time_part_match = re.search(
            r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
            clean_expr,
        )
        # Extract 24-hr time component (e.g., "at 19:30", "19:00")
        military_time_match = re.search(
            r"(?:at\s+)?(\d{1,2}):(\d{2})(?!\s*(?:am|pm))",
            clean_expr,
        )

        extracted_hour: Optional[int] = None
        extracted_minute: Optional[int] = None

        if time_part_match:
            hr = int(time_part_match.group(1))
            mn = int(time_part_match.group(2)) if time_part_match.group(2) else 0
            meridiem = time_part_match.group(3)
            if meridiem == "pm" and hr < 12:
                hr += 12
            elif meridiem == "am" and hr == 12:
                hr = 0
            extracted_hour = hr
            extracted_minute = mn
        elif military_time_match:
            hr = int(military_time_match.group(1))
            mn = int(military_time_match.group(2))
            if 0 <= hr <= 23 and 0 <= mn <= 59:
                extracted_hour = hr
                extracted_minute = mn

        # Determine target date
        target_date: Optional[date] = None

        # Check for "today", "tomorrow", "yesterday"
        if "tomorrow" in clean_expr:
            target_date = (base + timedelta(days=1)).date()
        elif "yesterday" in clean_expr:
            target_date = (base - timedelta(days=1)).date()
        elif "today" in clean_expr:
            target_date = base.date()
        else:
            # Check for weekday names ("friday", "next monday", etc.)
            for day_name, day_idx in WEEKDAYS.items():
                if day_name in clean_expr:
                    is_next = "next" in clean_expr
                    current_day_idx = base.weekday()
                    days_ahead = day_idx - current_day_idx
                    if days_ahead <= 0 or is_next:
                        days_ahead += 7
                    target_date = (base + timedelta(days=days_ahead)).date()
                    break

        # If only time was provided (e.g. "at 8 PM" or "8 PM")
        if target_date is None and extracted_hour is not None:
            candidate = datetime(
                base.year,
                base.month,
                base.day,
                extracted_hour,
                extracted_minute or 0,
                0,
                tzinfo=self._tz,
            )
            if candidate < base:
                target_date = (base + timedelta(days=1)).date()
            else:
                target_date = base.date()

        # If a date was identified
        if target_date is not None:
            hr = extracted_hour if extracted_hour is not None else 9  # Default to 9 AM if only date given
            mn = extracted_minute if extracted_minute is not None else 0
            return datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hr,
                mn,
                0,
                tzinfo=self._tz,
            )

        # Fallback date regex: YYYY-MM-DD
        date_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", clean_expr)
        if date_match:
            y = int(date_match.group(1))
            m = int(date_match.group(2))
            d = int(date_match.group(3))
            hr = extracted_hour if extracted_hour is not None else 9
            mn = extracted_minute if extracted_minute is not None else 0
            return datetime(y, m, d, hr, mn, 0, tzinfo=self._tz)

        return None
