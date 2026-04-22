"""SQLAlchemy engine + session factory, lazily built from ``DATABASE_URL``.

Design notes
------------
* **Lazy singletons.** The engine is only constructed on first use, never at
  import time. This keeps test collection fast and lets the app start when no
  DATABASE_URL is set (MemorySaver + YAML equipment store still work).
* **No database ⇒ graceful degradation.** If the URL is empty, the getters
  return ``None`` and callers fall back to in-memory alternatives. That is by
  design: it lets LangGraph Studio, unit tests, and casual local dev run with
  zero infrastructure.
* **Pool-aware defaults.** Cloud SQL connections are expensive — we keep a
  small pool with conservative timeouts and ``pool_pre_ping`` on so we don't
  serve requests over a stale, half-closed socket after an idle window.
* **Disposal.** :func:`dispose` exists so tests can tear the engine down
  between runs and rebuild it against a different URL.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.infrastructure.config import get_database_config

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base shared by every ORM model in the app."""


# Module-level singletons, guarded by a lock so concurrent FastAPI workers
# don't race on the first request.
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None
_lock = threading.Lock()


def get_engine() -> Engine | None:
    """Return the process-wide SQLAlchemy engine, or ``None`` if unconfigured.

    When ``DATABASE_URL`` is empty this intentionally returns ``None`` — that's
    the signal for the rest of the app to use in-memory alternatives (the
    ``MemorySaver`` checkpointer, the YAML equipment loader).

    If ``_engine`` has already been populated (e.g. a test injected it via
    monkeypatch), honour that and skip the config check. This lets unit tests
    run against an in-memory SQLite engine without flipping env vars.
    """
    global _engine, _SessionFactory
    if _engine is not None:
        return _engine

    cfg = get_database_config()
    if not cfg.is_configured:
        return None

    if _engine is None:
        with _lock:
            if _engine is None:  # double-checked under the lock
                logger.info(
                    "Creating SQLAlchemy engine (pool_size=%d, max_overflow=%d)",
                    cfg.pool_size,
                    cfg.pool_max_overflow,
                )
                _engine = create_engine(
                    cfg.url,
                    pool_size=cfg.pool_size,
                    max_overflow=cfg.pool_max_overflow,
                    pool_timeout=cfg.pool_timeout,
                    pool_pre_ping=True,  # survive Cloud SQL idle-connection resets
                    echo=cfg.echo,
                    future=True,
                )
                _SessionFactory = sessionmaker(
                    bind=_engine, autoflush=False, expire_on_commit=False
                )
    return _engine


def get_session_factory() -> sessionmaker[Session] | None:
    """Return the sessionmaker bound to :func:`get_engine`, or ``None``."""
    if get_engine() is None:
        return None
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager that commits on success and rolls back on exceptions.

    Raises :class:`RuntimeError` when no database is configured — callers that
    can work without a DB must check :func:`get_engine` first instead of
    relying on this to degrade.
    """
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError(
            "DATABASE_URL is not configured; cannot open a session. "
            "Check src.infrastructure.db.get_engine() before calling session_scope()."
        )
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose() -> None:
    """Tear down the engine. Primarily a test helper."""
    global _engine, _SessionFactory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _SessionFactory = None
