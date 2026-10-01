"""Revenue reporting."""

from __future__ import annotations

from sqlalchemy import text

from src.db import get_session
from src.utils.dates import days_ago
from src.utils.formatting import format_money


def revenue_last_days(days: int = 30) -> int:
    """Return total captured revenue over a window, in cents."""
    since = days_ago(days)
    with get_session() as session:
        row = session.execute(
            text(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM payments "
                "WHERE status = 'succeeded' AND created_at >= :since"
            ),
            {"since": since},
        ).fetchone()
    return int(row[0]) if row else 0


def revenue_summary(days: int = 30) -> str:
    """Return a human-readable revenue line for the ops channel."""
    return f"Last {days} days: {format_money(revenue_last_days(days))}"
