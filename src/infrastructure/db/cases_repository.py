"""Write path for Phase B: persist completed diagnostic cases.

Design
------
* **Fire-and-forget.** A database blip must never break the conversation. We
  submit writes to a small daemon thread pool and return immediately. Errors
  are logged — callers get no exception, no retry, no crash.
* **Graceful degradation.** When no ``DATABASE_URL`` is configured, :func:`record_case`
  is a no-op. That keeps unit tests and LangGraph Studio runs clean.
* **Pure data in.** This module never touches graph state directly. The caller
  passes a :class:`CaseRecord` dataclass that it builds from
  :class:`ConversationalAgentState`. That keeps the repository schema-stable
  even as node implementations drift.

Usage
-----
::

    from src.infrastructure.db.cases_repository import CaseRecord, record_case
    record_case(CaseRecord(
        thread_id="case-42",
        equipment_id="cctv-psu-24w-v1",
        started_at=...,
        completed_at=...,
        outcome="resolved",
        final_diagnosis="Shorted primary MOSFET",
        hypothesis_count=3,
        iteration_count=4,
        measurements=[
            MeasurementRecord(test_point="primary_mosfet", ...),
            ...
        ],
    ))
"""

from __future__ import annotations

import atexit
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.infrastructure.db.engine import get_engine, session_scope
from src.infrastructure.db.models import CaseMeasurement, DiagnosticCase

logger = logging.getLogger(__name__)

# A single shared pool — one worker is plenty since writes are rare (once per
# completed case) and we want strict ordering within a single case.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cases-writer")
atexit.register(_executor.shutdown, wait=True)


@dataclass
class MeasurementRecord:
    test_point: str
    signal_name: str | None = None
    measured_value: float | None = None
    unit: str | None = None
    evaluation: str | None = None
    hypothesis_being_tested: str | None = None
    taken_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CaseRecord:
    thread_id: str
    equipment_id: str
    started_at: datetime
    completed_at: datetime
    outcome: str
    final_diagnosis: str | None = None
    hypothesis_count: int = 0
    iteration_count: int = 0
    token_cost_input: int | None = None
    token_cost_output: int | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    measurements: list[MeasurementRecord] = field(default_factory=list)

    @property
    def measurement_count(self) -> int:
        return len(self.measurements)


def _write(record: CaseRecord) -> uuid.UUID | None:
    """Synchronous insert. Returns the new case's UUID on success.

    This is the only function in this module that touches the database.
    :func:`record_case` delegates here via the thread pool.
    """
    if get_engine() is None:
        return None

    case_id = uuid.uuid4()
    try:
        with session_scope() as session:
            case = DiagnosticCase(
                id=case_id,
                thread_id=record.thread_id,
                equipment_id=record.equipment_id,
                started_at=record.started_at,
                completed_at=record.completed_at,
                final_diagnosis=record.final_diagnosis,
                outcome=record.outcome,
                hypothesis_count=record.hypothesis_count,
                measurement_count=record.measurement_count,
                iteration_count=record.iteration_count,
                token_cost_input=record.token_cost_input,
                token_cost_output=record.token_cost_output,
                llm_provider=record.llm_provider,
                llm_model=record.llm_model,
            )
            session.add(case)
            for m in record.measurements:
                session.add(
                    CaseMeasurement(
                        case_id=case_id,
                        test_point=m.test_point,
                        signal_name=m.signal_name,
                        measured_value=m.measured_value,
                        unit=m.unit,
                        evaluation=m.evaluation,
                        hypothesis_being_tested=m.hypothesis_being_tested,
                        taken_at=m.taken_at,
                    )
                )
        logger.info(
            "Recorded case %s thread=%s equipment=%s outcome=%s measurements=%d",
            case_id,
            record.thread_id,
            record.equipment_id,
            record.outcome,
            record.measurement_count,
        )
        return case_id
    except Exception:
        logger.exception(
            "Failed to record diagnostic case (thread=%s, equipment=%s)",
            record.thread_id,
            record.equipment_id,
        )
        return None


def record_case(record: CaseRecord, *, block: bool = False) -> uuid.UUID | None:
    """Persist a completed diagnostic case.

    Args:
        record: The :class:`CaseRecord` to insert.
        block: If ``True``, wait for the write to finish and return the new
            case UUID. Defaults to ``False`` (fire-and-forget) so the agent
            response isn't blocked on DB latency. Tests set ``block=True``.

    Returns:
        The case UUID on a synchronous successful write, ``None`` otherwise
        (no DB configured, DB error, or async submission).
    """
    if get_engine() is None:
        logger.debug("DATABASE_URL not set — skipping case write.")
        return None

    if block:
        return _write(record)

    try:
        _executor.submit(_write, record)
    except RuntimeError:
        # Interpreter shutting down — fall back to synchronous write so we
        # don't silently drop the record.
        return _write(record)
    return None


# ---------------------------------------------------------------------------
# Helper: build a CaseRecord from the graph's terminal state.
# ---------------------------------------------------------------------------


def case_from_state(
    state: Any,
    *,
    thread_id: str,
    outcome: str,
    final_diagnosis: str | None = None,
    started_at: datetime | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> CaseRecord:
    """Build a :class:`CaseRecord` from a ``ConversationalAgentState``.

    Uses duck-typing (via ``getattr``) so this helper doesn't need to import
    :class:`ConversationalAgentState` and stays safe in partial-state scenarios
    (e.g. the non-repair END paths where some fields are still defaults).
    """
    now = datetime.now(timezone.utc)
    equipment_id = getattr(state, "equipment_model", "") or ""

    measurements_in = getattr(state, "measurements", []) or []
    measurement_records: list[MeasurementRecord] = []
    for m in measurements_in:
        try:
            raw_ts = m.get("timestamp") if isinstance(m, dict) else None
            taken_at = _parse_ts(raw_ts) or now
            value = m.get("value") if isinstance(m, dict) else None
            # Coerce numeric-like values; drop unparseable ones rather than fail.
            try:
                value_f = float(value) if value is not None else None
            except (TypeError, ValueError):
                value_f = None
            measurement_records.append(
                MeasurementRecord(
                    test_point=m.get("test_point", "?"),
                    signal_name=m.get("signal_name"),
                    measured_value=value_f,
                    unit=m.get("unit"),
                    evaluation=m.get("evaluation"),
                    hypothesis_being_tested=m.get("hypothesis_being_tested"),
                    taken_at=taken_at,
                )
            )
        except Exception:
            logger.debug("Skipping unparseable measurement record: %r", m)

    return CaseRecord(
        thread_id=thread_id,
        equipment_id=equipment_id,
        started_at=started_at or now,
        completed_at=now,
        outcome=outcome,
        final_diagnosis=final_diagnosis or getattr(state, "confirmed_fault", None) or None,
        hypothesis_count=len(getattr(state, "hypotheses", []) or []),
        iteration_count=int(getattr(state, "iteration_count", 0) or 0),
        llm_provider=llm_provider,
        llm_model=llm_model,
        measurements=measurement_records,
    )


def _parse_ts(value: Any) -> datetime | None:
    """Best-effort parse of the timestamp values written by ``step_node``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            # str(datetime.now()) format (no tz) — treat as UTC
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None
