from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def now_in_timezone(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def isoformat(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def current_period_weekly(now: datetime) -> tuple[datetime, datetime]:
    start = now - timedelta(days=7)
    return start, now


def previous_period_weekly(now: datetime) -> tuple[datetime, datetime]:
    current_start, _ = current_period_weekly(now)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=7)
    return previous_start, previous_end
