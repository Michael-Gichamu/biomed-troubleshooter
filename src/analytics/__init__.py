"""Analytics package — SQL-backed reports over the diagnostic case history.

Every function in :mod:`src.analytics.queries` returns a small dataclass list
(or a single metric) built from a single SQL statement. They are safe to call
from a notebook, a CLI, or a future FastAPI ``/analytics`` route.

The module intentionally has no FastAPI dependency — it stays a pure
SQL-over-SQLAlchemy layer so it can be unit-tested and reused without pulling
in the web stack.
"""

from src.analytics.queries import (
    DailyVolume,
    FaultFrequencyRow,
    HypothesisAccuracy,
    MeanTimeToDiagnosis,
    MeasurementReuseRow,
    OutcomeByModelRow,
    TestPointInformativeness,
    TokenCostByOutcome,
    daily_case_volume,
    fault_frequency_by_equipment,
    hypothesis_accuracy,
    mean_time_to_diagnosis,
    measurement_reuse_rate,
    most_informative_measurements,
    outcome_distribution_by_model,
    token_cost_per_case,
)

__all__ = [
    "DailyVolume",
    "FaultFrequencyRow",
    "HypothesisAccuracy",
    "MeanTimeToDiagnosis",
    "MeasurementReuseRow",
    "OutcomeByModelRow",
    "TestPointInformativeness",
    "TokenCostByOutcome",
    "daily_case_volume",
    "fault_frequency_by_equipment",
    "hypothesis_accuracy",
    "mean_time_to_diagnosis",
    "measurement_reuse_rate",
    "most_informative_measurements",
    "outcome_distribution_by_model",
    "token_cost_per_case",
]
