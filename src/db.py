"""Database session management.

`get_session` is the single entry point every module uses to talk to the database.
Changing its signature or lifecycle touches the whole service — which is exactly
what makes it interesting to an impact analyzer.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import load_settings

_engine = None
_factory = None


def get_engine():
    """Return the process-wide engine, building it on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine(load_settings().database_url, pool_size=10)
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a transactional session, committing on success and rolling back on error."""
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=get_engine())
    session = _factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def healthcheck() -> bool:
    """Return True when the database answers."""
    with get_session() as session:
        session.execute("SELECT 1")
    return True
