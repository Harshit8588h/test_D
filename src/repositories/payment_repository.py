"""Queries against the payments and refunds tables."""

from __future__ import annotations

from src.db import get_session
from src.models import Payment, Refund
from src.utils.errors import NotFound


def get_payment(payment_id: int) -> Payment:
    """Return one payment, or raise NotFound."""
    with get_session() as session:
        payment = session.get(Payment, payment_id)
        if payment is None:
            raise NotFound(f"no payment with id {payment_id}")
        return payment


def payments_for_order(order_id: int) -> list[Payment]:
    """Return every payment attempt against an order."""
    with get_session() as session:
        return session.query(Payment).filter(Payment.order_id == order_id).all()


def save_payment(payment: Payment) -> Payment:
    """Persist a payment attempt."""
    with get_session() as session:
        session.add(payment)
        session.flush()
        return payment


def save_refund(refund: Refund) -> Refund:
    """Persist a refund."""
    with get_session() as session:
        session.add(refund)
        session.flush()
        return refund
