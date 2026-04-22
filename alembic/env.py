"""Alembic migration environment.

Pulls the DATABASE_URL from ``src.infrastructure.config`` so a single env var
drives local dev, CI, and Cloud Run deploys. Falls back to the value in
``alembic.ini`` when DATABASE_URL isn't set — useful for offline ``--sql``
generation.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.infrastructure.config import get_database_config

# Import ORM metadata so autogenerate sees every table.
from src.infrastructure.db import Base  # noqa: F401
from src.infrastructure.db import models as _models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override the INI URL with the runtime value when it's set.
_runtime_url = get_database_config().url
if _runtime_url:
    config.set_main_option("sqlalchemy.url", _runtime_url)


def run_migrations_offline() -> None:
    """Emit SQL without connecting — writes to stdout when run with ``--sql``."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
