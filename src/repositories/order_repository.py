"""Queries against the orders table."""

from __future__ import annotations

from src.db import get_session
from src.models import Order
from src.utils.errors import NotFound


def get_order(order_id: int) -> Order:
    """Return one order, or raise NotFound."""
    with get_session() as session:
        order = session.get(Order, order_id)
        if order is None:
            raise NotFound(f"no order with id {order_id}")
        return order


def orders_for_user(user_id: int) -> list[Order]:
    """Return every order a user has placed."""
    with get_session() as session:
        return session.query(Order).filter(Order.user_id == user_id).all()


def save_order(order: Order) -> Order:
    """Persist a new or modified order."""
    with get_session() as session:
        session.add(order)
        session.flush()
        return order
