"""Date helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    """Return the current UTC time, timezone-aware."""
    return datetime.now(timezone.utc)


def days_ago(days: int) -> datetime:
    """Return the UTC timestamp `days` in the past."""
    return utc_now() - timedelta(days=days)


def to_iso(value: datetime) -> str:
    """Render a timestamp as ISO-8601."""
    return value.isoformat()
