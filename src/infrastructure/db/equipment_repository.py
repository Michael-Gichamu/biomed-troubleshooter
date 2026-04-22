"""Phase C: equipment-catalogue reads backed by Postgres.

This is the analogue of :func:`src.infrastructure.equipment_config.EquipmentConfig.from_file`
but sourced from the ``equipment`` row's ``raw_config`` JSONB column. The YAML
file ships the same shape, so:
  * tests/local dev use the YAML loader (fast, zero infra),
  * production Cloud Run uses Postgres via this repository,
and downstream code (``EquipmentConfig`` dataclass + its consumers) is
identical in either case.

The caller-facing surface is deliberately tiny so the switch in
:class:`EquipmentConfigLoader` is a one-liner.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from src.infrastructure.db.engine import get_engine, session_scope
from src.infrastructure.db.models import Equipment

logger = logging.getLogger(__name__)


def load_equipment_raw(equipment_id: str) -> dict[str, Any] | None:
    """Return the full YAML-shape dict for one equipment, or ``None`` if absent.

    Returns ``None`` when:
      * no ``DATABASE_URL`` is configured (caller must fall back to YAML), or
      * the equipment_id isn't in the ``equipment`` table.
    """
    if get_engine() is None:
        return None

    with session_scope() as session:
        row = session.execute(
            select(Equipment).where(Equipment.equipment_id == equipment_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        # row.raw_config is JSON/JSONB — already a Python dict after SQLAlchemy
        # decoding.
        return dict(row.raw_config)


def list_equipment_ids() -> list[str]:
    """Sorted list of equipment IDs present in the Postgres catalogue.

    Empty list if no database is configured — callers fall back to the
    YAML ``list_available()`` method.
    """
    if get_engine() is None:
        return []
    with session_scope() as session:
        ids = session.execute(select(Equipment.equipment_id)).scalars().all()
    return sorted(ids)
