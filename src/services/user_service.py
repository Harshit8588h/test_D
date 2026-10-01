"""User lifecycle: registration, lookup, deactivation."""

from __future__ import annotations

from src.db import get_session
from src.models import User
from src.repositories import user_repository
from src.utils.errors import ValidationError
from src.utils.validation import validate_email


def register_user(email: str, full_name: str) -> User:
    """Create a new account, refusing duplicates."""
    address = validate_email(email)
    if user_repository.find_by_email(address) is not None:
        raise ValidationError(f"an account already exists for {address}")
    user = User(email=address, full_name=full_name.strip())
    return user_repository.save_user(user)


def deactivate_user(user_id: int) -> User:
    """Mark an account inactive so it can no longer transact."""
    with get_session() as session:
        user = session.get(User, user_id)
        user.status = "inactive"
        session.add(user)
        return user


def describe_user(user_id: int) -> str:
    """Return a one-line summary for support tooling."""
    user = user_repository.get_user(user_id)
    state = "active" if user.is_active() else "inactive"
    return f"{user.display_name()} <{user.email}> ({state})"
