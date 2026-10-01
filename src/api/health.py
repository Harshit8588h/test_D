"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.db import get_session, healthcheck

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Return service health, including database reachability."""
    return {"status": "ok" if healthcheck() else "degraded"}


@router.get("/health/db")
def database_health() -> dict:
    """Confirm a session can be opened and a query answered."""
    with get_session() as session:
        session.execute("SELECT 1")
    return {"database": "reachable"}
