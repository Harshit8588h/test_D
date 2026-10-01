"""Tests for model helper methods."""

from src.models import Order, Payment, User


def test_display_name_prefers_full_name():
    user = User(email="a@b.com", full_name="Alice Smith")
    assert user.display_name() == "Alice Smith"


def test_active_status():
    assert User(email="a@b.com", full_name="A", status="active").is_active() is True
    assert User(email="a@b.com", full_name="A", status="inactive").is_active() is False


def test_settled_orders():
    assert Order(user_id=1, total_cents=100, status="paid").is_settled() is True
    assert Order(user_id=1, total_cents=100, status="pending").is_settled() is False


def test_payment_success():
    assert Payment(order_id=1, amount_cents=1, processor_ref="x", status="succeeded").succeeded()
