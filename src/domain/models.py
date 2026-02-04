"""
Domain Models

Pure business entities with no framework dependencies.
All validation and business rules encapsulated here.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import re


class SemanticState(Enum):
    """Semantic interpretation of signal states."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    OUT_OF_SPEC_LOW = "out_of_spec_low"
    OUT_OF_SPEC_HIGH = "out_of_spec_high"
    MISSING = "missing"
    NOISY = "noisy"
    INTERMITTENT = "intermittent"
    SHORTED = "shorted"
    OPEN_CIRCUIT = "open_circuit"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Severity levels for anomalies and errors."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINOR = "minor"


class DiagnosticStatus(Enum):
    """Overall diagnostic status."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class WorkflowType(Enum):
    """Workflow routing types."""
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    VERIFICATION = "verification"


# =============================================================================
# VALUE OBJECTS
# =============================================================================

@dataclass(frozen=True, slots=True)
class TestPoint:
    """Location and metadata for a test point (Value Object)."""
    id: str
    name: str
    location: Optional[str] = None
    component_id: Optional[str] = None

    def __post_init__(self):
        if not re.match(r'^[A-Za-z0-9_-]+$', self.id):
            raise ValueError(f"Invalid test point ID: {self.id}")


@dataclass(frozen=True, slots=True)
class Measurement:
    """A single measurement value (Value Object)."""
    test_point: TestPoint
    value: float
    unit: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Acceptable range for this measurement
    nominal_value: Optional[float] = None
    tolerance_percent: Optional[float] = None

    def __post_init__(self):
        valid_units = {'V', 'mV', 'A', 'mA', 'Ω', 'kΩ', 'W', 'mW', 'Hz', 'kHz', '°C', '%RH'}
        if self.unit not in valid_units:
            raise ValueError(f"Invalid unit: {self.unit}")

    @property
    def expected_range(self) -> tuple[Optional[float], Optional[float]]:
        """Calculate expected min/max based on nominal and tolerance."""
        if self.nominal_value is None or self.tolerance_percent is None:
            return (None, None)
        tolerance = self.nominal_value * (self.tolerance_percent / 100)
        return (self.nominal_value - tolerance, self.nominal_value + tolerance)


@dataclass(frozen=True, slots=True)
class SignalState:
    """Semantic interpretation of a signal (Value Object)."""
    measurement: Measurement
    semantic_state: SemanticState
    confidence: float = 1.0
    deviation_percent: Optional[float] = None

    def is_anomaly(self) -> bool:
        """Check if this signal represents an anomaly."""
        return self.semantic_state not in (
            SemanticState.NORMAL,
            SemanticState.UNKNOWN
        )


@dataclass(frozen=True, slots=True)
class EquipmentId:
    """Equipment identifier (Value Object)."""
    model: str
    serial: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.model}" + (f"::{self.serial}" if self.serial else "")

    def matches(self, other: "EquipmentId") -> bool:
        """Check if this ID matches another (ignores serial for model match)."""
        return self.model == other.model


# =============================================================================
# DOMAIN ENTITIES
# =============================================================================

@dataclass
class SignalCollection:
    """Collection of measurements for an equipment session."""
    equipment_id: EquipmentId
    measurements: list[Measurement] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    conditions: dict = field(default_factory=dict)

    def add_measurement(self, measurement: Measurement) -> None:
        """Add a measurement to the collection."""
        self.measurements.append(measurement)

    def get_measurement(self, test_point_id: str) -> Optional[Measurement]:
        """Get measurement by test point ID."""
        for m in self.measurements:
            if m.test_point.id == test_point_id:
                return m
        return None

    def count(self) -> int:
        """Return number of measurements."""
        return len(self.measurements)

    def anomaly_count(self) -> int:
        """Return count of anomalous signals."""
        # Requires state mapping - lazy evaluation in domain service
        return 0  # Placeholder


@dataclass
class ThresholdProfile:
    """Threshold configuration for signal interpretation."""
    equipment_model: str
    parameter: str
    nominal_value: float
    unit: str
    thresholds: dict  # semantic_state -> {min, max}
    hysteresis_percent: float = 5.0

    def get_state(self, value: float) -> SemanticState:
        """Determine semantic state from raw value."""
        for state_name, range_spec in self.thresholds.items():
            state = SemanticState(state_name)
            min_val = range_spec.get("min")
            max_val = range_spec.get("max")

            if min_val is not None and value < min_val:
                continue
            if max_val is not None and value > max_val:
                continue

            return state

        return SemanticState.UNKNOWN


@dataclass
class FaultHypothesis:
    """A hypothesis about the root cause of a fault."""
    cause: str
    confidence: float  # 0.0 - 1.0
    component: Optional[str] = None
    failure_mode: Optional[str] = None

    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)

    differential_causes: list["FaultHypothesis"] = field(default_factory=list)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")

    def is_definitive(self) -> bool:
        """Check if this hypothesis is definitive (high confidence, no contradictions)."""
        return (
            self.confidence >= 0.9 and
            not self.contradicting_evidence and
            len(self.differential_causes) == 0
        )

    def needs_review(self) -> bool:
        """Check if human review is recommended."""
        return self.confidence < 0.7 or bool(self.contradicting_evidence)


@dataclass
class DiagnosticSession:
    """A complete diagnostic session."""
    session_id: str
    equipment_id: EquipmentId
    signals: SignalCollection
    workflow_type: WorkflowType
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    hypothesis: Optional[FaultHypothesis] = None
    reasoning_chain: list[dict] = field(default_factory=list)
    recommendations: list[dict] = field(default_factory=list)

    status: str = "in_progress"
    errors: list[str] = field(default_factory=list)

    def complete(self, hypothesis: FaultHypothesis) -> None:
        """Complete the session with a hypothesis."""
        self.hypothesis = hypothesis
        self.completed_at = datetime.now(timezone.utc)
        self.status = "completed"

    def add_error(self, error: str) -> None:
        """Add an error to the session."""
        self.errors.append(error)
        self.status = "error"

    def add_reasoning_step(self, step: int, observation: str, inference: str, source: str) -> None:
        """Add a step to the reasoning chain."""
        self.reasoning_chain.append({
            "step": step,
            "observation": observation,
            "inference": inference,
            "source": source
        })


@dataclass
class TroubleshootingStep:
    """A step in the troubleshooting process."""
    step_number: int
    action: str  # measure, inspect, replace, verify
    target: str
    instruction: str
    expected_result: str
    priority: Severity = Severity.MEDIUM
    safety_warning: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "target": self.target,
            "instruction": self.instruction,
            "expected_result": self.expected_result,
            "priority": self.priority.value,
            "safety_warning": self.safety_warning
        }


# =============================================================================
# DOMAIN SERVICES (Pure business logic)
# =============================================================================

class SignalInterpreter:
    """Domain service for interpreting signals."""

    def __init__(self, thresholds: dict[str, ThresholdProfile]):
        self.thresholds = thresholds

    def interpret(self, signals: SignalCollection) -> tuple[list[SignalState], DiagnosticStatus]:
        """
        Interpret a collection of signals.

        Returns:
            Tuple of (interpreted_states, overall_status)
        """
        states = []
        has_critical = False
        has_warning = False

        for measurement in signals.measurements:
            # Find applicable threshold
            threshold = self._find_threshold(measurement, signals.equipment_id)
            if threshold:
                semantic = threshold.get_state(measurement.value)
                deviation = self._calculate_deviation(measurement, threshold)
            else:
                semantic = SemanticState.UNKNOWN
                deviation = None

            state = SignalState(
                measurement=measurement,
                semantic_state=semantic,
                deviation_percent=deviation
            )
            states.append(state)

            if semantic in (SemanticState.MISSING, SemanticState.SHORTED, SemanticState.OPEN_CIRCUIT):
                has_critical = True
            elif semantic in (SemanticState.OUT_OF_SPEC_LOW, SemanticState.OUT_OF_SPEC_HIGH):
                has_warning = True

        if has_critical:
            status = DiagnosticStatus.FAILED
        elif has_warning:
            status = DiagnosticStatus.DEGRADED
        else:
            status = DiagnosticStatus.NORMAL

        return states, status

    def _find_threshold(self, measurement: Measurement, equipment_id: EquipmentId) -> Optional[ThresholdProfile]:
        """Find the applicable threshold profile for a measurement."""
        # Look for exact parameter match
        key = f"{equipment_id.model}_{measurement.test_point.id}"
        return self.thresholds.get(key)

    def _calculate_deviation(self, measurement: Measurement, threshold: ThresholdProfile) -> Optional[float]:
        """Calculate percentage deviation from nominal."""
        if threshold.nominal_value == 0:
            return None
        return ((measurement.value - threshold.nominal_value) / threshold.nominal_value) * 100


class HypothesisGenerator:
    """Domain service for generating fault hypotheses."""

    def __init__(self, rule_engine: "DiagnosticRuleEngine"):
        self.rule_engine = rule_engine

    def generate(
        self,
        equipment_id: EquipmentId,
        signal_states: list[SignalState],
        evidence: list[str]
    ) -> FaultHypothesis:
        """
        Generate a fault hypothesis from signal states and evidence.

        This is a deterministic function based on rules - NOT freeform reasoning.
        """
        # Apply diagnostic rules to generate hypothesis
        matched_rules = self.rule_engine.evaluate(equipment_id, signal_states)

        if not matched_rules:
            return FaultHypothesis(
                cause="Unknown - no matching diagnostic rules",
                confidence=0.0
            )

        # Use highest-confidence matching rule
        best_rule = max(matched_rules, key=lambda r: r.confidence)

        return FaultHypothesis(
            cause=best_rule.cause,
            confidence=best_rule.confidence,
            component=best_rule.component,
            failure_mode=best_rule.failure_mode,
            supporting_evidence=evidence + [e.description for e in signal_states if e.is_anomaly()],
            differential_causes=[]
        )


@dataclass
class DiagnosticRule:
    """A deterministic diagnostic rule."""
    rule_id: str
    name: str
    cause: str
    confidence: float
    component: Optional[str] = None
    failure_mode: Optional[str] = None

    # Preconditions: signals that must match
    required_signals: list[dict] = field(default_factory=list)
    forbidden_signals: list[dict] = field(default_factory=list)

    def matches(self, signal_states: list[SignalState]) -> bool:
        """Check if this rule matches the given signal states."""
        # Check required signals
        for req in self.required_signals:
            if not self._matches_requirement(signal_states, req):
                return False

        # Check forbidden signals
        for forb in self.forbidden_signals:
            if self._matches_requirement(signal_states, forb):
                return False

        return True

    def _matches_requirement(self, signal_states: list[SignalState], requirement: dict) -> bool:
        """Check if a signal state matches a requirement."""
        tp_id = requirement.get("test_point_id")
        state = requirement.get("state")

        for ss in signal_states:
            if ss.measurement.test_point.id == tp_id:
                return ss.semantic_state.value == state

        return False


class DiagnosticRuleEngine:
    """Engine for evaluating diagnostic rules."""

    def __init__(self, rules: list[DiagnosticRule]):
        self.rules = rules

    def evaluate(self, equipment_id: EquipmentId, signal_states: list[SignalState]) -> list[DiagnosticRule]:
        """Evaluate all rules against signal states."""
        return [r for r in self.rules if r.matches(signal_states)]
