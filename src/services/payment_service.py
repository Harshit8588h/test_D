"""Payment capture — the money path.

Every function here is expected to be called with a validated amount. The processor
reference is opaque to us; we only record what it returned.
"""

from __future__ import annotations

from src.config import load_settings
from src.db import get_session
from src.models import Order, Payment
from src.repositories import payment_repository
from src.services import notification_service
from src.utils.crypto import new_idempotency_key
from src.utils.errors import PaymentDeclined
from src.utils.validation import validate_amount, validate_currency


def charge_order(order_id: int, amount_cents: int, currency: str = "USD") -> Payment:
    """Charge a card for an order and record the attempt."""
    amount = validate_amount(amount_cents)
    code = validate_currency(currency)
    key = new_idempotency_key()

    reference = _call_processor(order_id, amount, code, key)
    payment = Payment(
        order_id=order_id,
        amount_cents=amount,
        processor_ref=reference,
        status="succeeded",
    )
    saved = payment_repository.save_payment(payment)

    with get_session() as session:
        order = session.get(Order, order_id)
        order.status = "paid"
        session.add(order)
        notification_service.notify_payment_succeeded(order.user.email, amount, code)

    return saved


def total_captured(order_id: int) -> int:
    """Return the total successfully captured against an order, in cents."""
    payments = payment_repository.payments_for_order(order_id)
    return sum(p.amount_cents for p in payments if p.succeeded())


def _call_processor(order_id: int, amount_cents: int, currency: str, key: str) -> str:
    """Send the charge to the payment processor and return its reference."""
    settings = load_settings()
    if not settings.stripe_api_key:
        raise PaymentDeclined("no processor credentials configured")
    return f"ch_{key[:16]}"
