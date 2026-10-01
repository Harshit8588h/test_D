"""Input validation helpers."""

from __future__ import annotations

import re

from src.utils.errors import ValidationError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)


def validate_email(email: str) -> str:
    """Return the normalised email, or raise if it is not one."""
    cleaned = email.strip().lower()
    if not _EMAIL.match(cleaned):
        raise ValidationError(f"not a valid email address: {email!r}")
    return cleaned


def validate_amount(cents: int) -> int:
    """Return the amount, or raise when it is not a positive integer of cents."""
    if not isinstance(cents, int) or cents <= 0:
        raise ValidationError(f"amount must be a positive number of cents, got {cents!r}")
    return cents


def validate_currency(code: str) -> str:
    """Return the upper-cased ISO currency code, or raise."""
    if len(code) != 3 or not code.isalpha():
        raise ValidationError(f"not an ISO-4217 currency code: {code!r}")
    return code.upper()
