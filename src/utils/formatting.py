"""Presentation helpers."""

from __future__ import annotations


def format_money(cents: int, currency: str = "USD") -> str:
    """Render an integer number of cents as a human-readable amount."""
    return f"{cents / 100:,.2f} {currency}"


def truncate(text: str, limit: int = 80) -> str:
    """Shorten text for log lines and list views."""
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"
