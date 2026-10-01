"""Order lifecycle."""

from __future__ import annotations

from src.db import get_session
from src.models import Order
from src.repositories import order_repository, user_repository
from src.utils.errors import ValidationError
from src.utils.validation import validate_amount, validate_currency


def place_order(user_id: int, total_cents: int, currency: str = "USD") -> Order:
    """Create a pending order for an active user."""
    user = user_repository.get_user(user_id)
    if not user.is_active():
        raise ValidationError("inactive accounts cannot place orders")

    order = Order(
        user_id=user_id,
        total_cents=validate_amount(total_cents),
        currency=validate_currency(currency),
    )
    return order_repository.save_order(order)


def cancel_order(order_id: int) -> Order:
    """Cancel an order that has not been settled."""
    with get_session() as session:
        order = session.get(Order, order_id)
        if order.is_settled():
            raise ValidationError("a settled order cannot be cancelled")
        order.status = "cancelled"
        session.add(order)
        return order


def order_history(user_id: int) -> list[Order]:
    """Return every order a user has placed."""
    return order_repository.orders_for_user(user_id)
