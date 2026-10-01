"""Queries against the users table."""

from __future__ import annotations

from src.db import get_session
from src.models import User
from src.utils.errors import NotFound


def get_user(user_id: int) -> User:
    """Return one user, or raise NotFound."""
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            raise NotFound(f"no user with id {user_id}")
        return user


def find_by_email(email: str) -> User | None:
    """Return the user with this email, or None."""
    with get_session() as session:
        return session.query(User).filter(User.email == email).one_or_none()


def list_users(offset: int = 0, limit: int = 50) -> list[User]:
    """Return a page of users, newest first."""
    with get_session() as session:
        return (
            session.query(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


def save_user(user: User) -> User:
    """Persist a new or modified user."""
    with get_session() as session:
        session.add(user)
        session.flush()
        return user
