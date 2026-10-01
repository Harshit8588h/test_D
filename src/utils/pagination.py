"""Offset pagination helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    """One page of results."""

    items: list
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        """Return True when more rows follow this page."""
        return self.offset + len(self.items) < self.total


def clamp_limit(limit: int, maximum: int = 200) -> int:
    """Keep a caller-supplied page size within sane bounds."""
    return max(1, min(limit, maximum))
