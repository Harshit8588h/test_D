"""Tests for date helpers."""

from src.utils.dates import days_ago, to_iso, utc_now


def test_now_is_timezone_aware():
    assert utc_now().tzinfo is not None


def test_days_ago_is_in_the_past():
    assert days_ago(3) < utc_now()


def test_iso_roundtrip():
    assert to_iso(utc_now()).startswith("20")
