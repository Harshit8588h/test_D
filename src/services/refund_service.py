"""Refunds — the reverse money path."""

from __future__ import annotations

from src.models import Refund
from src.repositories import payment_repository
from src.services import notification_service, payment_service
from src.utils.errors import ValidationError
from src.utils.validation import validate_amount


def issue_refund(payment_id: int, amount_cents: int, reason: str) -> Refund:
    """Refund part or all of a payment, never more than was captured."""
    amount = validate_amount(amount_cents)
    payment = payment_repository.get_payment(payment_id)

    captured = payment_service.total_captured(payment.order_id)
    if amount > captured:
        raise ValidationError(f"cannot refund {amount} against {captured} captured")

    refund = Refund(payment_id=payment_id, amount_cents=amount, reason=reason)
    saved = payment_repository.save_refund(refund)
    notification_service.notify_refund_issued("customer@example.com", amount, "USD")
    return saved
