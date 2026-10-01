"""Payment endpoints. The money path — every route here moves funds."""

from __future__ import annotations

from fastapi import APIRouter

from src.db import get_session
from src.models import Payment
from src.services import audit_service, payment_service, refund_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/charge")
def charge(order_id: int, amount_cents: int, currency: str = "USD") -> dict:
    """Capture a payment against an order."""
    payment = payment_service.charge_order(order_id, amount_cents, currency)
    audit_service.record("api", "charge", f"order:{order_id}")
    return {"payment_id": payment.id, "status": payment.status}


@router.post("/refund")
def refund(payment_id: int, amount_cents: int, reason: str) -> dict:
    """Refund a captured payment."""
    issued = refund_service.issue_refund(payment_id, amount_cents, reason)
    audit_service.record("api", "refund", f"payment:{payment_id}")
    return {"refund_id": issued.id, "amount_cents": issued.amount_cents}


@router.get("/{payment_id}")
def read_payment(payment_id: int) -> dict:
    """Return one payment attempt."""
    with get_session() as session:
        payment = session.get(Payment, payment_id)
        return {
            "id": payment.id,
            "status": payment.status,
            "succeeded": payment.succeeded(),
        }
