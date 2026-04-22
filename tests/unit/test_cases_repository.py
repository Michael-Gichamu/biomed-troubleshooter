"""Tests for :mod:`src.infrastructure.db.cases_repository`.

Uses an in-process SQLite engine so the suite stays hermetic. The engine is
injected into the module's lazy singleton via a fixture.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db import engine as engine_mod
from src.infrastructure.db.cases_repository import (
    CaseRecord,
    MeasurementRecord,
    case_from_state,
    record_case,
)
from src.infrastructure.db.engine import Base


@pytest.fixture
def sqlite_engine(monkeypatch):
    """Spin up a fresh in-memory SQLite engine and plug it into the module."""
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, expire_on_commit=False)

    # Point the module's lazy singletons at our test engine. The production
    # ``get_engine`` path consults DatabaseConfig — we bypass that here.
    monkeypatch.setattr(engine_mod, "_engine", eng, raising=False)
    monkeypatch.setattr(engine_mod, "_SessionFactory", factory, raising=False)

    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()
    monkeypatch.setattr(engine_mod, "_engine", None, raising=False)
    monkeypatch.setattr(engine_mod, "_SessionFactory", None, raising=False)


def test_record_case_writes_case_and_measurements(sqlite_engine):
    now = datetime.now(timezone.utc)
    record = CaseRecord(
        thread_id="thread-1",
        equipment_id="test-psu-v1",
        started_at=now - timedelta(minutes=3),
        completed_at=now,
        outcome="resolved",
        final_diagnosis="Shorted Primary MOSFET",
        hypothesis_count=2,
        iteration_count=3,
        measurements=[
            MeasurementRecord(
                test_point="primary_mosfet",
                signal_name="Q1",
                measured_value=0.1,
                unit="ohm",
                evaluation="fault",
                hypothesis_being_tested="HYPOTHESIS_1",
                taken_at=now - timedelta(minutes=1),
            ),
            MeasurementRecord(
                test_point="output_voltage",
                signal_name="+12V rail",
                measured_value=0.0,
                unit="V",
                evaluation="fault",
                hypothesis_being_tested="HYPOTHESIS_1",
                taken_at=now,
            ),
        ],
    )

    case_id = record_case(record, block=True)
    assert case_id is not None

    # Verify round-trip via raw SQL.
    with sqlite_engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT outcome, measurement_count, hypothesis_count FROM diagnostic_cases"
        ).all()
        assert rows == [("resolved", 2, 2)]

        meas = conn.exec_driver_sql(
            "SELECT test_point, evaluation FROM case_measurements ORDER BY test_point"
        ).all()
        assert meas == [
            ("output_voltage", "fault"),
            ("primary_mosfet", "fault"),
        ]


def test_record_case_is_noop_without_engine(monkeypatch):
    """When no engine is configured :func:`record_case` must not raise."""
    monkeypatch.setattr(engine_mod, "_engine", None, raising=False)
    monkeypatch.setattr(engine_mod, "_SessionFactory", None, raising=False)
    from src.infrastructure import config as cfg

    monkeypatch.setattr(
        cfg,
        "get_database_config",
        lambda: cfg.DatabaseConfig(url="", equipment_store="yaml"),
    )

    result = record_case(
        CaseRecord(
            thread_id="t",
            equipment_id="e",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            outcome="inconclusive",
        ),
        block=True,
    )
    assert result is None


def test_case_from_state_maps_measurements(base_state):
    """``case_from_state`` should preserve measurement shape from graph state."""
    # Simulate a completed state with two measurements.
    base_state.measurements = [
        {
            "test_point": "primary_mosfet",
            "signal_name": "Q1",
            "value": 0.0,
            "unit": "ohm",
            "evaluation": "fault",
            "hypothesis_being_tested": "HYPOTHESIS_1",
            "timestamp": str(datetime.now()),
        },
        {
            "test_point": "output_voltage",
            "signal_name": "+12V",
            "value": "n/a",  # non-numeric — should become None
            "unit": "V",
            "evaluation": "measurement_unavailable",
            "hypothesis_being_tested": "HYPOTHESIS_1",
            "timestamp": str(datetime.now()),
        },
    ]
    base_state.confirmed_fault = "Shorted Primary MOSFET"
    base_state.iteration_count = 3

    rec = case_from_state(
        base_state,
        thread_id="thread-42",
        outcome="resolved",
    )

    assert rec.thread_id == "thread-42"
    assert rec.outcome == "resolved"
    assert rec.final_diagnosis == "Shorted Primary MOSFET"
    assert rec.equipment_id == "test-psu-v1"
    assert rec.measurement_count == 2
    assert rec.measurements[1].measured_value is None
