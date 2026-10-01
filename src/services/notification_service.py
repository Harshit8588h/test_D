"""Outbound notifications. Deliberately fire-and-forget."""

from __future__ import annotations

from src.config import load_settings
from src.utils.formatting import format_money


def notify_payment_succeeded(email: str, amount_cents: int, currency: str) -> None:
    """Tell a customer their payment went through."""
    settings = load_settings()
    body = f"We received {format_money(amount_cents, currency)}. Thank you."
    _send(settings.notification_url, email, "Payment received", body)


def notify_refund_issued(email: str, amount_cents: int, currency: str) -> None:
    """Tell a customer a refund is on its way."""
    settings = load_settings()
    body = f"We refunded {format_money(amount_cents, currency)}."
    _send(settings.notification_url, email, "Refund issued", body)


def _send(url: str, to: str, subject: str, body: str) -> None:
    """Hand the message to the notification service."""
    print(f"POST {url} to={to} subject={subject!r} body={body!r}")
