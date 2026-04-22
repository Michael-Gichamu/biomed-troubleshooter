"""Canonical analytics queries over the diagnostic case history.

Every function returns a typed dataclass (or list of) so callers get IDE
completions and the shape is stable. All queries use SQLAlchemy Core /
textual SQL — no ORM round-trips — because the schema is fixed and we're
chasing "a readable SQL string" over "Pythonic query composition" here.

The functions accept an optional :class:`sqlalchemy.orm.Session` to make
tests easy (pytest constructs a session scoped to a transactional fixture
and passes it in). Production callers pass nothing; we open a short-lived
session against the configured pool.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.infrastructure.db.engine import get_session_factory

# ---------------------------------------------------------------------------
# Session plumbing — tests pass a session; callers usually don't.
# ---------------------------------------------------------------------------


@contextmanager
def _maybe_session(session: Session | None):
    """Yield the caller-provided session, or open a fresh one."""
    if session is not None:
        yield session
        return
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is not configured; analytics queries require a database.")
    s = factory()
    try:
        yield s
    finally:
        s.close()


# ---------------------------------------------------------------------------
# 1. fault_frequency_by_equipment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FaultFrequencyRow:
    test_point: str
    signal_name: str | None
    fault_count: int
    total_observations: int
    fault_rate: float  # 0.0 – 1.0


def fault_frequency_by_equipment(
    equipment_id: str,
    *,
    session: Session | None = None,
    limit: int = 25,
) -> list[FaultFrequencyRow]:
    """Per-signal fault rate for a single equipment model.

    "How often, when we measured test point X on this equipment, did we find
    it to be at fault?" — the canonical reliability metric.
    """
    sql = text("""
        SELECT
            m.test_point,
            MAX(m.signal_name) AS signal_name,
            SUM(CASE WHEN m.evaluation = 'fault' THEN 1 ELSE 0 END) AS fault_count,
            COUNT(*) AS total_observations
        FROM case_measurements m
        JOIN diagnostic_cases c ON c.id = m.case_id
        WHERE c.equipment_id = :equipment_id
        GROUP BY m.test_point
        HAVING COUNT(*) > 0
        ORDER BY fault_count DESC, total_observations DESC
        LIMIT :limit
        """)
    with _maybe_session(session) as s:
        rows = s.execute(sql, {"equipment_id": equipment_id, "limit": limit}).all()
    return [
        FaultFrequencyRow(
            test_point=r.test_point,
            signal_name=r.signal_name,
            fault_count=int(r.fault_count or 0),
            total_observations=int(r.total_observations or 0),
            fault_rate=(float(r.fault_count or 0) / float(r.total_observations or 1)),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 2. mean_time_to_diagnosis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeanTimeToDiagnosis:
    equipment_id: str
    case_count: int
    p50_seconds: float
    p95_seconds: float
    mean_seconds: float


def mean_time_to_diagnosis(
    equipment_id: str,
    *,
    since: datetime | None = None,
    session: Session | None = None,
) -> MeanTimeToDiagnosis:
    """Wall-clock time from first measurement to terminal node.

    Uses percentile_cont on Postgres; SQLite falls through to Python-side
    percentile computation so the function also works in unit tests.
    """
    since = since or datetime.now(timezone.utc) - timedelta(days=90)
    sql = text("""
        SELECT EXTRACT(EPOCH FROM (completed_at - started_at)) AS seconds
        FROM diagnostic_cases
        WHERE equipment_id = :equipment_id
          AND completed_at >= :since
          AND outcome = 'resolved'
        ORDER BY seconds
        """)
    with _maybe_session(session) as s:
        dialect = s.bind.dialect.name if s.bind else ""
        if dialect == "sqlite":
            sql = text("""
                SELECT (julianday(completed_at) - julianday(started_at)) * 86400.0 AS seconds
                FROM diagnostic_cases
                WHERE equipment_id = :equipment_id
                  AND completed_at >= :since
                  AND outcome = 'resolved'
                ORDER BY seconds
                """)
        rows = s.execute(sql, {"equipment_id": equipment_id, "since": since}).all()

    seconds = [float(r.seconds) for r in rows if r.seconds is not None]
    if not seconds:
        return MeanTimeToDiagnosis(equipment_id, 0, 0.0, 0.0, 0.0)

    def _pct(xs: list[float], p: float) -> float:
        if not xs:
            return 0.0
        k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
        return xs[k]

    return MeanTimeToDiagnosis(
        equipment_id=equipment_id,
        case_count=len(seconds),
        p50_seconds=_pct(seconds, 50),
        p95_seconds=_pct(seconds, 95),
        mean_seconds=sum(seconds) / len(seconds),
    )


# ---------------------------------------------------------------------------
# 3. hypothesis_accuracy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HypothesisAccuracy:
    resolved_cases: int
    avg_hypotheses_per_case: float
    avg_measurements_per_case: float
    avg_iterations_per_case: float


def hypothesis_accuracy(
    *,
    session: Session | None = None,
) -> HypothesisAccuracy:
    """Shape of the hypothesis/measurement trajectory on cases that resolved.

    A low ``avg_measurements_per_case`` with a high ``resolved_cases`` is the
    good-efficiency signal: the hypothesis ranker is finding the right test
    point early.
    """
    sql = text("""
        SELECT
            COUNT(*) AS n,
            COALESCE(AVG(hypothesis_count), 0)  AS avg_hyp,
            COALESCE(AVG(measurement_count), 0) AS avg_meas,
            COALESCE(AVG(iteration_count), 0)   AS avg_iter
        FROM diagnostic_cases
        WHERE outcome = 'resolved'
        """)
    with _maybe_session(session) as s:
        r = s.execute(sql).one()
    return HypothesisAccuracy(
        resolved_cases=int(r.n or 0),
        avg_hypotheses_per_case=float(r.avg_hyp or 0),
        avg_measurements_per_case=float(r.avg_meas or 0),
        avg_iterations_per_case=float(r.avg_iter or 0),
    )


# ---------------------------------------------------------------------------
# 4. token_cost_per_case
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenCostByOutcome:
    outcome: str
    cases: int
    mean_input_tokens: float
    mean_output_tokens: float
    mean_total_tokens: float


def token_cost_per_case(
    *,
    outcome: str | None = None,
    session: Session | None = None,
) -> list[TokenCostByOutcome]:
    """LLM token spend grouped by case outcome.

    Useful for answering: "how much more expensive, on average, is a resolved
    case vs. an inconclusive one?" — a direct cost-efficiency metric.
    """
    where = "WHERE outcome = :outcome" if outcome else ""
    sql = text(f"""
        SELECT
            outcome,
            COUNT(*) AS cases,
            COALESCE(AVG(token_cost_input), 0)  AS mean_in,
            COALESCE(AVG(token_cost_output), 0) AS mean_out
        FROM diagnostic_cases
        {where}
        GROUP BY outcome
        ORDER BY cases DESC
        """)
    params = {"outcome": outcome} if outcome else {}
    with _maybe_session(session) as s:
        rows = s.execute(sql, params).all()
    return [
        TokenCostByOutcome(
            outcome=r.outcome,
            cases=int(r.cases or 0),
            mean_input_tokens=float(r.mean_in or 0),
            mean_output_tokens=float(r.mean_out or 0),
            mean_total_tokens=float((r.mean_in or 0) + (r.mean_out or 0)),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 5. measurement_reuse_rate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeasurementReuseRow:
    test_point: str
    cases_touched: int
    total_measurements: int


def measurement_reuse_rate(
    *,
    limit: int = 25,
    session: Session | None = None,
) -> list[MeasurementReuseRow]:
    """Test points that appear across the most cases.

    Ranks by distinct ``case_id`` count so a test point that shows up once per
    case (in 50 cases) beats one that shows up ten times in one case.
    """
    sql = text("""
        SELECT
            test_point,
            COUNT(DISTINCT case_id) AS cases_touched,
            COUNT(*) AS total_measurements
        FROM case_measurements
        GROUP BY test_point
        ORDER BY cases_touched DESC, total_measurements DESC
        LIMIT :limit
        """)
    with _maybe_session(session) as s:
        rows = s.execute(sql, {"limit": limit}).all()
    return [
        MeasurementReuseRow(
            test_point=r.test_point,
            cases_touched=int(r.cases_touched or 0),
            total_measurements=int(r.total_measurements or 0),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 6. outcome_distribution_by_model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeByModelRow:
    llm_provider: str | None
    llm_model: str | None
    outcome: str
    cases: int


def outcome_distribution_by_model(
    *,
    session: Session | None = None,
) -> list[OutcomeByModelRow]:
    """Case outcome × LLM used — drives provider-comparison plots."""
    sql = text("""
        SELECT llm_provider, llm_model, outcome, COUNT(*) AS cases
        FROM diagnostic_cases
        GROUP BY llm_provider, llm_model, outcome
        ORDER BY llm_provider, llm_model, cases DESC
        """)
    with _maybe_session(session) as s:
        rows = s.execute(sql).all()
    return [
        OutcomeByModelRow(
            llm_provider=r.llm_provider,
            llm_model=r.llm_model,
            outcome=r.outcome,
            cases=int(r.cases or 0),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 7. daily_case_volume
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyVolume:
    day: str  # ISO date
    cases: int
    resolved: int


def daily_case_volume(
    *,
    days: int = 30,
    session: Session | None = None,
) -> list[DailyVolume]:
    """Per-day case volume for the last ``days`` days (time-series)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    # date() works on both Postgres and SQLite.
    sql = text("""
        SELECT
            CAST(completed_at AS DATE) AS day,
            COUNT(*) AS cases,
            SUM(CASE WHEN outcome = 'resolved' THEN 1 ELSE 0 END) AS resolved
        FROM diagnostic_cases
        WHERE completed_at >= :since
        GROUP BY day
        ORDER BY day
        """)
    with _maybe_session(session) as s:
        rows = s.execute(sql, {"since": since}).all()
    return [
        DailyVolume(
            day=str(r.day),
            cases=int(r.cases or 0),
            resolved=int(r.resolved or 0),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 8. most_informative_measurements
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestPointInformativeness:
    test_point: str
    signal_name: str | None
    fault_confirmations: int
    cases_appeared: int
    confirmation_rate: float  # fault_confirmations / cases_appeared


def most_informative_measurements(
    *,
    limit: int = 15,
    min_cases: int = 3,
    session: Session | None = None,
) -> list[TestPointInformativeness]:
    """Test points whose 'fault' reading most often coincides with a resolved
    case — a proxy for information-gain per probe.
    """
    sql = text("""
        SELECT
            m.test_point,
            MAX(m.signal_name) AS signal_name,
            SUM(
                CASE WHEN m.evaluation = 'fault' AND c.outcome = 'resolved'
                     THEN 1 ELSE 0 END
            ) AS fault_confirmations,
            COUNT(DISTINCT m.case_id) AS cases_appeared
        FROM case_measurements m
        JOIN diagnostic_cases c ON c.id = m.case_id
        GROUP BY m.test_point
        HAVING COUNT(DISTINCT m.case_id) >= :min_cases
        ORDER BY fault_confirmations DESC, cases_appeared DESC
        LIMIT :limit
        """)
    with _maybe_session(session) as s:
        rows = s.execute(sql, {"min_cases": min_cases, "limit": limit}).all()
    return [
        TestPointInformativeness(
            test_point=r.test_point,
            signal_name=r.signal_name,
            fault_confirmations=int(r.fault_confirmations or 0),
            cases_appeared=int(r.cases_appeared or 0),
            confirmation_rate=(float(r.fault_confirmations or 0) / float(r.cases_appeared or 1)),
        )
        for r in rows
    ]
