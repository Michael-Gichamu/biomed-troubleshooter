"""Smoke tests for :mod:`src.analytics.queries`.

Runs every canonical query against an in-memory SQLite populated with a tiny
fixture. We're not asserting exact business logic here — we're asserting the
SQL compiles, runs, and shapes results into the expected dataclasses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analytics import queries as Q
from src.infrastructure.db.engine import Base
from src.infrastructure.db.models import CaseMeasurement, DiagnosticCase


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)
    s = Session()

    # --- fixture data ---
    now = datetime.now(timezone.utc)
    case_a = DiagnosticCase(
        id=uuid.uuid4(),
        thread_id="t-a",
        equipment_id="psu-x",
        started_at=now - timedelta(minutes=5),
        completed_at=now,
        outcome="resolved",
        hypothesis_count=2,
        measurement_count=2,
        iteration_count=3,
        final_diagnosis="MOSFET short",
        llm_provider="anthropic",
        llm_model="claude-opus-4-6",
        token_cost_input=1200,
        token_cost_output=480,
    )
    case_b = DiagnosticCase(
        id=uuid.uuid4(),
        thread_id="t-b",
        equipment_id="psu-x",
        started_at=now - timedelta(minutes=8),
        completed_at=now - timedelta(minutes=1),
        outcome="inconclusive",
        hypothesis_count=3,
        measurement_count=3,
        iteration_count=4,
        llm_provider="groq",
        llm_model="llama-3.3-70b-versatile",
        token_cost_input=900,
        token_cost_output=200,
    )
    s.add_all([case_a, case_b])
    s.flush()

    s.add_all(
        [
            CaseMeasurement(
                case_id=case_a.id,
                test_point="primary_mosfet",
                signal_name="Q1",
                evaluation="fault",
                taken_at=now - timedelta(minutes=3),
                measured_value=0.0,
                unit="ohm",
                hypothesis_being_tested="HYPOTHESIS_1",
            ),
            CaseMeasurement(
                case_id=case_a.id,
                test_point="output_voltage",
                signal_name="+12V",
                evaluation="fault",
                taken_at=now - timedelta(minutes=1),
                measured_value=0.0,
                unit="V",
                hypothesis_being_tested="HYPOTHESIS_1",
            ),
            CaseMeasurement(
                case_id=case_b.id,
                test_point="primary_mosfet",
                signal_name="Q1",
                evaluation="normal",
                taken_at=now - timedelta(minutes=7),
                measured_value=50_000,
                unit="ohm",
                hypothesis_being_tested="HYPOTHESIS_1",
            ),
            CaseMeasurement(
                case_id=case_b.id,
                test_point="rail_12v",
                signal_name="rail",
                evaluation="normal",
                taken_at=now - timedelta(minutes=6),
                measured_value=12.0,
                unit="V",
                hypothesis_being_tested="HYPOTHESIS_2",
            ),
            CaseMeasurement(
                case_id=case_b.id,
                test_point="output_voltage",
                signal_name="+12V",
                evaluation="measurement_unavailable",
                taken_at=now - timedelta(minutes=4),
                measured_value=None,
                unit="V",
                hypothesis_being_tested="HYPOTHESIS_2",
            ),
        ]
    )
    s.commit()

    yield s
    s.close()
    Base.metadata.drop_all(eng)


def test_fault_frequency_by_equipment(session):
    rows = Q.fault_frequency_by_equipment("psu-x", session=session)
    by_tp = {r.test_point: r for r in rows}
    assert by_tp["primary_mosfet"].fault_count == 1
    assert by_tp["primary_mosfet"].total_observations == 2
    assert 0.0 < by_tp["primary_mosfet"].fault_rate < 1.0


def test_mean_time_to_diagnosis(session):
    mtd = Q.mean_time_to_diagnosis("psu-x", session=session)
    assert mtd.case_count == 1
    assert mtd.p50_seconds > 0
    assert mtd.mean_seconds == pytest.approx(mtd.p50_seconds)


def test_hypothesis_accuracy(session):
    acc = Q.hypothesis_accuracy(session=session)
    assert acc.resolved_cases == 1
    assert acc.avg_measurements_per_case == pytest.approx(2.0)


def test_token_cost_per_case(session):
    rows = Q.token_cost_per_case(session=session)
    assert {r.outcome for r in rows} == {"resolved", "inconclusive"}
    resolved = next(r for r in rows if r.outcome == "resolved")
    assert resolved.mean_input_tokens == 1200


def test_measurement_reuse_rate(session):
    rows = Q.measurement_reuse_rate(session=session)
    by_tp = {r.test_point: r for r in rows}
    # primary_mosfet and output_voltage each appear in both cases
    assert by_tp["primary_mosfet"].cases_touched == 2
    assert by_tp["output_voltage"].cases_touched == 2


def test_outcome_distribution_by_model(session):
    rows = Q.outcome_distribution_by_model(session=session)
    providers = {r.llm_provider for r in rows}
    assert providers == {"anthropic", "groq"}


def test_daily_case_volume(session):
    rows = Q.daily_case_volume(days=30, session=session)
    assert rows  # at least today's bucket
    total = sum(r.cases for r in rows)
    assert total == 2


def test_most_informative_measurements(session):
    rows = Q.most_informative_measurements(min_cases=1, limit=10, session=session)
    by_tp = {r.test_point: r for r in rows}
    # primary_mosfet had fault in the resolved case only → 1 confirmation
    assert by_tp["primary_mosfet"].fault_confirmations == 1
