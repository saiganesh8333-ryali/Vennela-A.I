"""
Unit tests for Temporal Context foundation.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from core.temporal import DEFAULT_TIMEZONE, TemporalContext


def test_01_temporal_context_timezone_awareness():
    tc = TemporalContext("Asia/Kolkata")
    now_dt = tc.now()
    assert now_dt.tzinfo is not None
    assert str(now_dt.tzinfo) == "Asia/Kolkata"
    assert tc.timezone_name == "Asia/Kolkata"


def test_02_deterministic_fixed_now():
    fixed = datetime(2026, 9, 10, 14, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    assert tc.now() == fixed
    assert tc.current_date().isoformat() == "2026-09-10"
    assert tc.current_time().hour == 14
    assert tc.current_time().minute == 30
    assert tc.day_of_week() == "Thursday"


def test_03_today_tomorrow_yesterday():
    fixed = datetime(2026, 9, 10, 14, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)

    today = tc.today()
    assert today.year == 2026 and today.month == 9 and today.day == 10
    assert today.hour == 0 and today.minute == 0

    tomorrow = tc.tomorrow()
    assert tomorrow.year == 2026 and tomorrow.month == 9 and tomorrow.day == 11
    assert tomorrow.hour == 0 and tomorrow.minute == 0
    assert tc.day_of_week(tomorrow) == "Friday"

    yesterday = tc.yesterday()
    assert yesterday.year == 2026 and yesterday.month == 9 and yesterday.day == 9
    assert yesterday.hour == 0 and yesterday.minute == 0
    assert tc.day_of_week(yesterday) == "Wednesday"


def test_04_relative_duration_parsing():
    fixed = datetime(2026, 9, 10, 12, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)

    # in 30 minutes
    res1 = tc.resolve_datetime("in 30 minutes")
    assert res1 == datetime(2026, 9, 10, 12, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    # in 2 hours
    res2 = tc.resolve_datetime("in 2 hours")
    assert res2 == datetime(2026, 9, 10, 14, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    # in 45 seconds
    res3 = tc.resolve_datetime("in 45 seconds")
    assert res3 == datetime(2026, 9, 10, 12, 0, 45, tzinfo=ZoneInfo("Asia/Kolkata"))

    # in 3 days
    res4 = tc.resolve_datetime("in 3 days")
    assert res4 == datetime(2026, 9, 13, 12, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_05_clock_time_and_date_resolution():
    fixed = datetime(2026, 9, 10, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)

    # "at 8 PM" (later today)
    res_8pm = tc.resolve_datetime("at 8 PM")
    assert res_8pm == datetime(2026, 9, 10, 20, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    # "tomorrow at 7 AM"
    res_tom_7am = tc.resolve_datetime("tomorrow at 7 AM")
    assert res_tom_7am == datetime(2026, 9, 11, 7, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    # "Friday" (2026-09-10 is Thursday, so Friday is 2026-09-11)
    res_fri = tc.resolve_datetime("Friday")
    assert res_fri.date().isoformat() == "2026-09-11"

    # "next Monday"
    res_next_mon = tc.resolve_datetime("next Monday")
    assert res_next_mon.date().isoformat() == "2026-09-14"

    # "tomorrow"
    res_tom = tc.resolve_datetime("tomorrow")
    assert res_tom.date().isoformat() == "2026-09-11"


def test_06_configurable_timezone():
    fixed_utc = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    tc_ny = TemporalContext("America/New_York", fixed_now=fixed_utc)
    assert tc_ny.timezone_name == "America/New_York"
    ny_now = tc_ny.now()
    # UTC 10:00 is EDT (UTC-4) 06:00
    assert ny_now.hour == 6


def test_07_formatting_methods():
    fixed = datetime(2026, 9, 10, 23, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    assert tc.format_time() == "11:15 PM"
    assert tc.format_date() == "Thursday, 10 September 2026"
