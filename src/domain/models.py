"""
Domain Models

Pure business entities with no framework dependencies.
All validation and business rules encapsulated here.
NOTHING equipment-specific should exist in this file.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


# =============================================================================
# ENUMS - Generic only, no equipment-specific values
# =============================================================================

class WorkflowType:
    """Workflow routing types - generic, no equipment-specific values."""
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    VERIFICATION = "verification"

    @classmethod
    def from_string(cls, value: str) -> str:
        valid = {cls.INITIAL, cls.FOLLOW_UP, cls.VERIFICATION}
        return value if value in valid else cls.INITIAL


# =============================================================================
# VALUE OBJECTS
# =============================================================================

@dataclass(frozen=True, slots=True)
class TestPoint:
    """
    Location and metadata for a test point.

    NOTE: Signal IDs and parameters come from equipment config, not hard-coded here.
    """
    id: str
    name: str
    location: Optional[str] = None
    component_id: Optional[str] = None

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("Test point ID cannot be empty")


@dataclass(frozen=True, slots=True)
class Measurement:
    """
    A single measurement value.

    NOTE: Thresholds come from equipment config, not hard-coded here.
    """
    test_point: TestPoint
    value: float
    unit: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional expected range from equipment config
    nominal_value: Optional[float] = None
    tolerance_percent: Optional[float] = None

    def __post_init__(self):
        if not self.unit or not self.unit.strip():
            raise ValueError("Unit cannot be empty")

    @property
    def expected_range(self) -> tuple[Optional[float], Optional[float]]:
        """Calculate expected min/max based on nominal and tolerance."""
        if self.nominal_value is None or self.tolerance_percent is None:
            return (None, None)
        tolerance = self.nominal_value * (self.tolerance_percent / 100)
        return (self.nominal_value - tolerance, self.nominal_value + tolerance)


@dataclass(frozen=True, slots=True)
class SignalState:
    """
    Semantic interpretation of a signal.

    NOTE: Semantic states come from equipment config thresholds, not hard-coded here.
    The state string is data-driven, not an enum.
    """
    measurement: Measurement
    state: str  # e.g., "normal", "missing", "over_voltage" - from config
    confidence: float = 1.0
    deviation_percent: Optional[float] = None

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")

    def is_anomaly(self) -> bool:
        """
        Check if this signal represents an anomaly.

        NOTE: "Normal" state definition comes from equipment config, not hard-coded.
        """
        return self.state != "normal"


@dataclass(frozen=True, slots=True)
class EquipmentId:
    """
    Equipment identifier.

    NOTE: Model names come from data files, not hard-coded here.
    """
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


@dataclass
class DiagnosticSession:
    """
    A complete diagnostic session.

    NOTE: All fault knowledge comes from equipment config files, not hard-coded.
    """
    session_id: str
    equipment_id: EquipmentId
    signals: SignalCollection
    workflow_type: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    hypothesis: Optional[dict] = None  # From equipment config fault definition
    reasoning_chain: list[dict] = field(default_factory=list)
    recommendations: list[dict] = field(default_factory=list)

    status: str = "in_progress"
    errors: list[str] = field(default_factory=list)

    def complete(self, hypothesis: dict) -> None:
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
class ReasoningStep:
    """A step in the troubleshooting reasoning process."""
    step: int
    observation: str
    inference: str
    source: str  # "signal", "documentation", "config"

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "observation": self.observation,
            "inference": self.inference,
            "source": self.source
        }


# =============================================================================
# DOMAIN SERVICES (Generic, data-driven)
# =============================================================================

class SignalInterpreter:
    """
    Domain service for interpreting signals.

    NOTE: Threshold logic is data-driven from equipment config files.
    """

    def __init__(self, threshold_configs: dict):
        """
        Initialize with threshold configurations from equipment file.

        Args:
            threshold_configs: Dict mapping signal_id to threshold config
        """
        self.threshold_configs = threshold_configs

    def interpret(self, signals: SignalCollection) -> tuple[list[SignalState], str]:
        """
        Interpret a collection of signals using equipment thresholds.

        Args:
            signals: Collection of measurements

        Returns:
            Tuple of (signal_states, overall_status)
        """
        states = []
        has_critical = False
        has_warning = False

        for measurement in signals.measurements:
            threshold = self.threshold_configs.get(measurement.test_point.id)

            if threshold:
                state = threshold.get_state(measurement.value)
                deviation = self._calculate_deviation(measurement, threshold)
            else:
                state = "unknown"
                deviation = None

            signal_state = SignalState(
                measurement=measurement,
                state=state or "unknown",
                deviation_percent=deviation
            )
            states.append(signal_state)

            if state in ("missing", "shorted", "open_circuit"):
                has_critical = True
            elif state in ("under_voltage", "over_voltage", "failed"):
                has_warning = True

        if has_critical:
            status = "failed"
        elif has_warning:
            status = "degraded"
        else:
            status = "normal"

        return states, status

    def _calculate_deviation(self, measurement: Measurement, threshold) -> Optional[float]:
        """Calculate percentage deviation from nominal."""
        nominal = getattr(threshold, 'nominal_value', None) or measurement.nominal_value
        if nominal is None or nominal == 0:
            return None
        return ((measurement.value - nominal) / nominal) * 100


class FaultMatcher:
    """
    Domain service for matching faults based on signal states.

    NOTE: Fault definitions come from equipment config files, not hard-coded.
    """

    def __init__(self, fault_configs: dict):
        """
        Initialize with fault configurations from equipment file.

        Args:
            fault_configs: Dict mapping fault_id to fault config
        """
        self.fault_configs = fault_configs

    def find_matching_fault(self, signal_states: dict) -> Optional[dict]:
        """
        Find a fault that matches the observed signal states.

        Args:
            signal_states: Dict mapping signal_id to semantic state

        Returns:
            Matching fault config or None
        """
        for fault in self.fault_configs.values():
            if self._matches_fault(fault, signal_states):
                return fault
        return None

    def _matches_fault(self, fault: dict, signal_states: dict) -> bool:
        """Check if fault signatures match observed signal states."""
        signatures = fault.get("signatures", [])
        for sig in signatures:
            sig_signal_id = sig.get("signal_id")
            sig_state = sig.get("state")
            observed_state = signal_states.get(sig_signal_id)
            if observed_state != sig_state:
                return False
        return True


class RecommendationGenerator:
    """
    Domain service for generating recommendations from fault definitions.

    NOTE: Recovery actions come from equipment config files, not hard-coded.
    """

    def __init__(self, fault_configs: dict):
        """
        Initialize with fault configurations.

        Args:
            fault_configs: Dict mapping fault_id to fault config
        """
        self.fault_configs = fault_configs

    def generate(self, fault_id: str, signal_states: dict) -> list[dict]:
        """
        Generate recovery recommendations for a fault.

        Args:
            fault_id: The fault ID
            signal_states: Observed signal states

        Returns:
            List of recovery step dicts
        """
        fault = self.fault_configs.get(fault_id)
        if not fault:
            return []

        recovery = fault.get("recovery", [])

        # Transform recovery steps to recommendations
        recommendations = []
        for step in recovery:
            recommendations.append({
                "action": step.get("action", "inspect"),
                "target": step.get("target", "Unknown"),
                "instruction": step.get("instruction", ""),
                "verification_step": step.get("verification", ""),
                "estimated_difficulty": step.get("difficulty", "moderate"),
                "safety_warning": step.get("safety", ""),
                "estimated_time": step.get("estimated_time", "")
            })

        return recommendations


class HypothesisGenerator:
    """
    Domain service for generating fault hypotheses.

    NOTE: All hypothesis generation uses data from equipment config files.
    """

    def __init__(self, fault_configs: dict):
        """
        Initialize with fault configurations.

        Args:
            fault_configs: Dict mapping fault_id to fault config
        """
        self.fault_configs = fault_configs

    def generate(
        self,
        equipment_id: str,
        signal_states: dict,
        evidence: list[str]
    ) -> dict:
        """
        Generate a fault hypothesis from signal states and evidence.

        Args:
            equipment_id: The equipment model
            signal_states: Dict of signal_id -> semantic state
            evidence: List of evidence descriptions

        Returns:
            Hypothesis dict with cause, confidence, etc.
        """
        # Find matching fault
        fault = self._find_matching_fault(signal_states)

        if not fault:
            return {
                "cause": "Unknown - no matching fault pattern",
                "confidence": 0.0,
                "component": None,
                "failure_mode": None,
                "supporting_evidence": evidence,
                "contradicting_evidence": [],
                "fault_id": None
            }

        # Get best hypothesis from fault
        hypotheses = fault.get("hypotheses", [])
        if not hypotheses:
            return {
                "cause": fault.get("description", "Unknown fault"),
                "confidence": 0.5,
                "component": None,
                "failure_mode": None,
                "supporting_evidence": evidence,
                "contradicting_evidence": [],
                "fault_id": fault.get("fault_id")
            }

        # Get highest-ranked hypothesis
        best = min(hypotheses, key=lambda h: h.get("rank", 99))

        return {
            "cause": best.get("cause", fault.get("description", "Unknown")),
            "confidence": best.get("confidence", 0.5),
            "component": best.get("component"),
            "failure_mode": best.get("failure_mode"),
            "supporting_evidence": evidence,
            "contradicting_evidence": [],
            "fault_id": fault.get("fault_id")
        }

    def _find_matching_fault(self, signal_states: dict) -> Optional[dict]:
        """Find fault matching observed signal states."""
        matcher = FaultMatcher(self.fault_configs)
        return matcher.find_matching_fault(signal_states)


# =============================================================================
# SIGNAL BATCH MODELS (For CLI and Mock Mode)
# =============================================================================

@dataclass
class Signal:
    """A signal measurement with test point and value."""
    test_point: TestPoint
    value: float
    unit: str
    measurement_type: str = "voltage"
    accuracy: float = 0.1
    timestamp: str = ""
    anomaly: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_point": {
                "id": self.test_point.id,
                "name": self.test_point.name,
                "location": self.test_point.location
            },
            "value": self.value,
            "unit": self.unit,
            "measurement_type": self.measurement_type,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp,
            "anomaly": self.anomaly
        }


@dataclass
class SignalBatch:
    """A batch of signals from equipment."""
    timestamp: str = ""
    equipment_id: str = ""
    signals: list[Signal] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "SignalBatch":
        """Create SignalBatch from dictionary (JSON data)."""
        signals = []
        for sig_data in data.get("signals", []):
            tp_data = sig_data.get("test_point", {})
            test_point = TestPoint(
                id=tp_data.get("id", "TP1"),
                name=tp_data.get("name", "Unknown"),
                location=tp_data.get("location")
            )
            signal = Signal(
                test_point=test_point,
                value=sig_data.get("value", 0.0),
                unit=sig_data.get("unit", "V"),
                measurement_type=sig_data.get("measurement_type", "voltage"),
                accuracy=sig_data.get("accuracy", 0.1),
                timestamp=sig_data.get("timestamp", ""),
                anomaly=sig_data.get("anomaly")
            )
            signals.append(signal)

        return cls(
            timestamp=data.get("timestamp", ""),
            equipment_id=data.get("equipment_id", data.get("scenario_name", "")),
            signals=signals
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "equipment_id": self.equipment_id,
            "signals": [s.to_dict() for s in self.signals]
        }
