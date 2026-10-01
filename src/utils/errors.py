"""Domain errors raised across the service."""

from __future__ import annotations


class BillingError(Exception):
    """Base class for every billing failure."""


class ValidationError(BillingError):
    """The caller supplied something invalid."""


class PaymentDeclined(BillingError):
    """The processor refused the charge."""


class NotFound(BillingError):
    """The requested record does not exist."""
