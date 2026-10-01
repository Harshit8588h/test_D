"""Tests for presentation helpers."""

from src.utils.formatting import format_money, truncate


def test_money_rendered_with_currency():
    assert format_money(12345) == "123.45 USD"


def test_truncate_leaves_short_text_alone():
    assert truncate("short") == "short"


def test_truncate_shortens_long_text():
    assert len(truncate("x" * 200, limit=20)) == 20
