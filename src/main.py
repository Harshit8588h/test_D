"""Application entrypoint — wires every router onto one FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from src.api import admin, health, orders, payments, users, webhooks


def create_app() -> FastAPI:
    """Build the ACME billing application."""
    app = FastAPI(title="ACME Billing", version="1.4.0")
    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(orders.router)
    app.include_router(payments.router)
    app.include_router(admin.router)
    app.include_router(webhooks.router)
    return app


app = create_app()
