# acme-billing

The billing service behind ACME's checkout: users, orders, payments, refunds.

    src/api/          HTTP endpoints (FastAPI routers)
    src/services/     business logic
    src/repositories/ database access
    src/utils/        crypto, validation, formatting helpers
    src/db.py         session management — used by nearly everything
    src/models.py     SQLAlchemy models (User, Order, Payment, Refund)

This is the sample codebase Devolyn Guard indexes for demonstrations. It is a
realistic small service: real cross-module calls, a genuine dependency hub
(`db.get_session`), and no deliberately planted bugs.
