"""Database package — SQLAlchemy engine, ORM schema, and repositories.

Public surface
--------------
* :func:`get_engine` / :func:`get_session_factory` — lazy engine + session
  factory singletons. Both return ``None`` when ``DATABASE_URL`` is empty so
  callers can degrade gracefully (in-memory checkpointer, YAML equipment store).
* :func:`session_scope` — convenience context manager that commits on success
  and rolls back on any exception.
* :func:`dispose` — test helper that tears down the engine and forces the next
  call to :func:`get_engine` to rebuild it. Used by ``tests/conftest.py``.
* :class:`Base` — SQLAlchemy 2.0 declarative base for ORM models.
* :mod:`.models` — ORM models for every table the app owns.
* :mod:`.cases_repository` — Phase B: writes diagnostic cases + measurements.
* :mod:`.equipment_repository` — Phase C: reads equipment config from Postgres.
"""

from src.infrastructure.db.engine import (
    Base,
    dispose,
    get_engine,
    get_session_factory,
    session_scope,
)

__all__ = [
    "Base",
    "dispose",
    "get_engine",
    "get_session_factory",
    "session_scope",
]
