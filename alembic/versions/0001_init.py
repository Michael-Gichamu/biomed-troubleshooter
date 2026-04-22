"""Initial schema — diagnostic cases, measurements, and equipment catalogue.

Revision ID: 0001
Revises:
Create Date: 2026-04-21

Creates every table the application writes to:
  * ``diagnostic_cases`` + ``case_measurements``                (Phase B)
  * ``equipment`` + ``signals`` + ``faults`` + ``signal_dependencies``  (Phase C)

LangGraph's PostgresSaver creates its own checkpoint tables on the first call
to ``saver.setup()`` at process start. They are NOT managed by this migration
so we don't risk locking mid-deploy.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Phase B — diagnostic cases
    # ------------------------------------------------------------------
    op.create_table(
        "diagnostic_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", sa.String(128), nullable=False),
        sa.Column("equipment_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_diagnosis", sa.Text, nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("hypothesis_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("measurement_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("iteration_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_cost_input", sa.Integer, nullable=True),
        sa.Column("token_cost_output", sa.Integer, nullable=True),
        sa.Column("llm_provider", sa.String(32), nullable=True),
        sa.Column("llm_model", sa.String(64), nullable=True),
    )
    op.create_index("ix_diagnostic_cases_thread_id", "diagnostic_cases", ["thread_id"])
    op.create_index("ix_diagnostic_cases_equipment_id", "diagnostic_cases", ["equipment_id"])
    op.create_index("ix_diagnostic_cases_outcome", "diagnostic_cases", ["outcome"])
    op.create_index("idx_cases_started", "diagnostic_cases", ["started_at"])

    op.create_table(
        "case_measurements",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("diagnostic_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_point", sa.String(128), nullable=False),
        sa.Column("signal_name", sa.String(256), nullable=True),
        sa.Column("measured_value", sa.Float, nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("evaluation", sa.String(32), nullable=True),
        sa.Column("hypothesis_being_tested", sa.String(64), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_measurements_case_id", "case_measurements", ["case_id"])
    op.create_index("ix_case_measurements_test_point", "case_measurements", ["test_point"])

    # ------------------------------------------------------------------
    # Phase C — equipment catalogue
    # ------------------------------------------------------------------
    op.create_table(
        "equipment",
        sa.Column("equipment_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("manufacturer", sa.String(128), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("raw_config", postgresql.JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(128), nullable=False),
        sa.Column(
            "equipment_id",
            sa.String(64),
            sa.ForeignKey("equipment.equipment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("parameter", sa.String(32), nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("test_point", sa.String(128), nullable=True),
        sa.Column("diagnostic_meaning", sa.Text, nullable=True),
        sa.UniqueConstraint("equipment_id", "signal_id", name="uq_signal_per_equipment"),
    )
    op.create_index("ix_signals_equipment_id", "signals", ["equipment_id"])

    op.create_table(
        "faults",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("fault_id", sa.String(64), nullable=False),
        sa.Column(
            "equipment_id",
            sa.String(64),
            sa.ForeignKey("equipment.equipment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("priority", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.UniqueConstraint("equipment_id", "fault_id", name="uq_fault_per_equipment"),
    )
    op.create_index("ix_faults_equipment_id", "faults", ["equipment_id"])

    op.create_table(
        "signal_dependencies",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "equipment_id",
            sa.String(64),
            sa.ForeignKey("equipment.equipment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("upstream_signal_id", sa.String(128), nullable=False),
        sa.Column("downstream_signal_id", sa.String(128), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "equipment_id",
            "upstream_signal_id",
            "downstream_signal_id",
            name="uq_signal_dep_triple",
        ),
    )
    op.create_index(
        "ix_signal_dependencies_equipment_id",
        "signal_dependencies",
        ["equipment_id"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_table("signal_dependencies")
    op.drop_table("faults")
    op.drop_table("signals")
    op.drop_table("equipment")
    op.drop_table("case_measurements")
    op.drop_table("diagnostic_cases")
