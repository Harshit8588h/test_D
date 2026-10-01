"""Order endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.db import get_session
from src.models import Order
from src.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("")
def create_order(user_id: int, total_cents: int, currency: str = "USD") -> dict:
    """Place a new order."""
    order = order_service.place_order(user_id, total_cents, currency)
    return {"id": order.id, "status": order.status}


@router.get("/{order_id}")
def read_order(order_id: int) -> dict:
    """Return one order."""
    with get_session() as session:
        order = session.get(Order, order_id)
        return {"id": order.id, "settled": order.is_settled(), "status": order.status}


@router.post("/{order_id}/cancel")
def cancel(order_id: int) -> dict:
    """Cancel an unsettled order."""
    order = order_service.cancel_order(order_id)
    return {"id": order.id, "status": order.status}


@router.get("/user/{user_id}")
def history(user_id: int) -> dict:
    """Return a user's order history."""
    orders = order_service.order_history(user_id)
    return {"orders": [o.id for o in orders]}
