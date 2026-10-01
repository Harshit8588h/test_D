"""Tests for pagination helpers."""

from src.utils.pagination import Page, clamp_limit


def test_clamp_keeps_limit_in_range():
    assert clamp_limit(0) == 1
    assert clamp_limit(5000) == 200
    assert clamp_limit(50) == 50


def test_has_more_when_page_is_partial():
    page = Page(items=[1, 2], total=10, offset=0, limit=2)
    assert page.has_more is True


def test_no_more_on_last_page():
    page = Page(items=[1, 2], total=2, offset=0, limit=2)
    assert page.has_more is False
