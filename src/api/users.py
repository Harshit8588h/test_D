"""User endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.db import get_session
from src.models import User
from src.services import user_service
from src.utils.pagination import Page, clamp_limit

router = APIRouter(prefix="/users", tags=["users"])


@router.post("")
def create_user(email: str, full_name: str) -> dict:
    """Register a new account."""
    user = user_service.register_user(email, full_name)
    return {"id": user.id, "email": user.email}


@router.get("/{user_id}")
def read_user(user_id: int) -> dict:
    """Return one account."""
    return {"summary": user_service.describe_user(user_id)}


@router.get("")
def list_users(offset: int = 0, limit: int = 50) -> dict:
    """Return a page of accounts."""
    size = clamp_limit(limit)
    with get_session() as session:
        total = session.query(User).count()
        rows = session.query(User).offset(offset).limit(size).all()
    page = Page(items=[r.email for r in rows], total=total, offset=offset, limit=size)
    return {"items": page.items, "total": page.total, "has_more": page.has_more}


@router.delete("/{user_id}")
def deactivate(user_id: int) -> dict:
    """Deactivate an account."""
    user = user_service.deactivate_user(user_id)
    return {"id": user.id, "status": user.status}
