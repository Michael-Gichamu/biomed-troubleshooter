"""SQLAlchemy 2.0 ORM models — full schema for Phases B and C.

Phase B tables
--------------
* :class:`DiagnosticCase`   — one row per completed run of the diagnostic graph
* :class:`CaseMeasurement`  — one row per multimeter measurement within a case

Phase C tables
--------------
* :class:`Equipment`        — one row per equipment model; ``raw_config`` JSONB
  holds the full, lossless YAML document. Top-level scalar fields
  (``name``, ``manufacturer``, ``category``, ``version``) are also materialised
  as columns so SQL queries can filter/group without JSON-path gymnastics.
* :class:`Signal`           — lightweight index of signals per equipment.
  Populated by the seed script from ``raw_config['signals']`` so BI queries
  can answer "which equipment uses a TL431 regulator?" without parsing JSON.
* :class:`Fault`            — lightweight index of faults per equipment.
* :class:`SignalDependency` — directed M:M edges between signals.

Design rationale (pragmatic over doctrinaire)
---------------------------------------------
The YAML schema is rich, evolves, and has variable-length nested structures
(threshold states, fault signatures, recovery-step tool lists). Fully
normalising it into 10+ tables would be brittle and would trap us into
migrations on every schema tweak. Instead we store the full YAML body as
JSONB so Postgres is an authoritative, queryable runtime store without
requiring the ORM to stay 1:1 with the YAML layout. The flat ``signals`` and
``faults`` tables exist because they're what SQL-based analytics actually
needs — e.g. joining ``case_measurements`` against ``signals`` to build a
"fault rate by signal" report.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.engine import Base

# JSONB on Postgres, JSON on every other dialect (SQLite in tests).
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")

# SQLAlchemy 2.0's generic Uuid type uses native UUID on Postgres and
# CHAR(32) on SQLite, transparently (de)serialising to ``uuid.UUID``. Avoids
# the driver-level "type 'UUID' is not supported" error that the Postgres
# dialect's UUID type hits on sqlite3.
_UUID_TYPE = Uuid(as_uuid=True)

# BIGSERIAL in Postgres → autoincrementing INTEGER PRIMARY KEY on SQLite.
# Only the INTEGER column type autoincrements under sqlite3; BigInteger alone
# silently fails with a NOT NULL violation on insert.
_BIGINT_PK = BigInteger().with_variant(Integer(), "sqlite")


# ---------------------------------------------------------------------------
# Phase B — diagnostic cases & measurements
# ---------------------------------------------------------------------------


class DiagnosticCase(Base):
    """One completed run of the diagnostic graph.

    Written at the terminal nodes (``repair`` and the non-repair
    ``decision→END`` paths). ``outcome`` distinguishes how the case ended:
      * ``resolved``      — fault confirmed + recovery handed back
      * ``inconclusive``  — ran out of hypotheses without matching a fault
      * ``max_steps``     — hit the iteration ceiling
      * ``exhausted``     — all test points consumed, no decision
    """

    __tablename__ = "diagnostic_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        _UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    equipment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    final_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    hypothesis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    measurement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    iteration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_cost_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_cost_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    measurements: Mapped[list[CaseMeasurement]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("idx_cases_started", "started_at"),)


class CaseMeasurement(Base):
    """A single multimeter reading taken during a diagnostic case."""

    __tablename__ = "case_measurements"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    case_id: Mapped[uuid.UUID] = mapped_column(
        _UUID_TYPE,
        ForeignKey("diagnostic_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_point: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    signal_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    measured_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    evaluation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hypothesis_being_tested: Mapped[str | None] = mapped_column(String(64), nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    case: Mapped[DiagnosticCase] = relationship(back_populates="measurements")


# ---------------------------------------------------------------------------
# Phase C — equipment catalogue (YAML source of truth, Postgres runtime store)
# ---------------------------------------------------------------------------


class Equipment(Base):
    """Equipment catalogue entry. One row = one YAML file.

    ``raw_config`` holds the full parsed YAML document as JSONB — this is the
    authoritative runtime shape the graph needs. The scalar columns
    (``name``, ``manufacturer``, ``category``, ``version``) are materialised for
    indexing/BI and kept in sync by the seed script.
    """

    __tablename__ = "equipment"

    equipment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_config: Mapped[dict[str, Any]] = mapped_column(_JSON_TYPE, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    signals: Mapped[list[Signal]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan", passive_deletes=True
    )
    faults: Mapped[list[Fault]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan", passive_deletes=True
    )


class Signal(Base):
    """Signal/test-point index. One row per (equipment, signal_id).

    The source of truth for a signal's full config is still the
    :class:`Equipment`.raw_config JSONB. This table exists so SQL analytics and
    BI queries can filter/group/join without JSON-path expressions.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    equipment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("equipment.equipment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parameter: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    test_point: Mapped[str | None] = mapped_column(String(128), nullable=True)
    diagnostic_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment: Mapped[Equipment] = relationship(back_populates="signals")

    __table_args__ = (
        UniqueConstraint("equipment_id", "signal_id", name="uq_signal_per_equipment"),
    )


class Fault(Base):
    """Fault-catalogue index. One row per (equipment, fault_id)."""

    __tablename__ = "faults"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    fault_id: Mapped[str] = mapped_column(String(64), nullable=False)
    equipment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("equipment.equipment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment: Mapped[Equipment] = relationship(back_populates="faults")

    __table_args__ = (UniqueConstraint("equipment_id", "fault_id", name="uq_fault_per_equipment"),)


class SignalDependency(Base):
    """Directed dependency between two signals on the same equipment."""

    __tablename__ = "signal_dependencies"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("equipment.equipment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upstream_signal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    downstream_signal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "equipment_id",
            "upstream_signal_id",
            "downstream_signal_id",
            name="uq_signal_dep_triple",
        ),
    )
