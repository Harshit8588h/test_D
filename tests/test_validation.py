"""Tests for input validation helpers."""

import pytest

from src.utils.errors import ValidationError
from src.utils.validation import validate_amount, validate_currency, validate_email


def test_valid_email_is_normalised():
    assert validate_email("  Alice@Example.COM ") == "alice@example.com"


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        validate_email("not-an-email")


def test_amount_must_be_positive():
    assert validate_amount(500) == 500
    with pytest.raises(ValidationError):
        validate_amount(0)


def test_currency_upper_cased():
    assert validate_currency("usd") == "USD"
    with pytest.raises(ValidationError):
        validate_currency("dollars")
