"""Inbound webhooks from the payment processor."""

from __future__ import annotations

from fastapi import APIRouter

from src.config import load_settings
from src.db import get_session
from src.models import Payment
from src.services import audit_service
from src.utils.crypto import verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/processor")
def processor_event(payload: bytes, signature: str, event: str, payment_id: int) -> dict:
    """Accept a processor callback, verifying its signature first."""
    settings = load_settings()
    if not verify_signature(payload, signature, settings.stripe_api_key):
        return {"accepted": False, "reason": "bad signature"}

    with get_session() as session:
        payment = session.get(Payment, payment_id)
        payment.status = "succeeded" if event == "charge.succeeded" else "failed"
        session.add(payment)

    audit_service.record("processor", event, f"payment:{payment_id}")
    return {"accepted": True}
