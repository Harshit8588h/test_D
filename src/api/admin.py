"""Admin endpoints. Privileged — every route is staff-only."""

from __future__ import annotations

from fastapi import APIRouter

from src.db import get_session
from src.models import User
from src.services import audit_service, report_service, user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/revenue")
def revenue(days: int = 30) -> dict:
    """Return the revenue summary for the ops channel."""
    return {"summary": report_service.revenue_summary(days)}


@router.get("/activity")
def activity(limit: int = 100) -> dict:
    """Return the recent internal activity log."""
    return {"rows": len(audit_service.recent(limit))}


@router.post("/users/{user_id}/deactivate")
def force_deactivate(user_id: int, actor: str) -> dict:
    """Deactivate an account on a customer's behalf."""
    user = user_service.deactivate_user(user_id)
    audit_service.record(actor, "deactivate", f"user:{user_id}")
    return {"id": user.id, "status": user.status}


@router.get("/counts")
def counts() -> dict:
    """Return row counts for the admin dashboard."""
    with get_session() as session:
        return {"users": session.query(User).count()}
