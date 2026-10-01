"""Internal activity log, separate from the billing tables."""

from __future__ import annotations

from sqlalchemy import text

from src.db import get_session
from src.utils.dates import utc_now


def record(actor: str, action: str, subject: str) -> None:
    """Append one activity row."""
    with get_session() as session:
        session.execute(
            text("INSERT INTO activity (actor, action, subject, at) VALUES (:a, :b, :c, :d)"),
            {"a": actor, "b": action, "c": subject, "d": utc_now()},
        )


def recent(limit: int = 100) -> list:
    """Return the most recent activity rows."""
    with get_session() as session:
        rows = session.execute(
            text("SELECT actor, action, subject, at FROM activity ORDER BY at DESC LIMIT :n"),
            {"n": limit},
        )
        return rows.fetchall()
