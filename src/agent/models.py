"""
Pydantic Models for Biomedical Equipment Troubleshooting Agent

Covers:
- Signal Data Models
- Agent State Models  
- Equipment and Error Models
- Context and Configuration Models

Compatible with LangGraph state management.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# =============================================================================
# 1. ENUMS
# =============================================================================

class WorkflowType(Enum):
    """Workflow routing types."""
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    VERIFICATION = "verification"


class SignalParameter(Enum):
    """Types of signal measurements."""
    VOLTAGE_DC = "voltage_dc"
    VOLTAGE_AC = "voltage_ac"
    VOLTAGE_RMS = "voltage_rms"
    CURRENT = "current"
    RESISTANCE = "resistance"
    IMPEDANCE = "impedance"
    POWER_REAL = "power_real"
    POWER_APPARENT = "power_apparent"
    FREQUENCY = "frequency"
    DUTY_CYCLE = "duty_cycle"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    HUMIDITY = "humidity"


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


class ActionType(Enum):
    """Types of recommended actions."""
    MEASURE = "measure"
    INSPECT = "inspect"
    REPLACE = "replace"
    VERIFY = "verify"
    ESCALATE = "escalate"


class DifficultyLevel(Enum):
    """Difficulty level for repair actions."""
    EASY = "easy"
    MODERATE = "moderate"
    EXPERT = "expert"


class NodeStatus(Enum):
    """Status of a graph node."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ErrorCategory(Enum):
    """Categories of errors."""
    VALIDATION = "validation"
    RAG = "rag"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    HARDWARE = "hardware"
    UNKNOWN = "unknown"


# =============================================================================
# 2. SIGNAL DATA MODELS
# =============================================================================

class InstrumentMetadata(BaseModel):
    """Metadata about the measurement instrument."""
    model: str = Field(..., description="Instrument model name")
    id: Optional[str] = Field(None, description="Instrument identifier")
    calibration_date: Optional[datetime] = Field(None, description="Last calibration date")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MeasurementAccuracy(BaseModel):
    """Accuracy specification for a measurement."""
    tolerance: Optional[float] = Field(None, ge=0, le=100, description="Tolerance percentage")
    instrument_error: Optional[float] = Field(None, description="Instrument error in base unit")


class MeasurementConditions(BaseModel):
    """Conditions under which measurement was taken."""
    load_state: Optional[str] = Field(None, description="no_load, nominal_load, full_load, overload")
    power_state: Optional[str] = Field(None, description="off, standby, on, operating")
    ambient_temp: Optional[float] = Field(None, ge=-40, le=150, description="Ambient temperature in °C")


class TestPoint(BaseModel):
    """Location and metadata for a test point."""
    id: str = Field(..., description="Test point identifier (e.g., TP12)")
    name: str = Field(..., description="Human-readable name")
    location: Optional[str] = Field(None, description="Physical location on board")
    component_id: Optional[str] = Field(None, description="Associated component identifier")

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError(f'Invalid test point ID: {v}')
        return v


class RawSignal(BaseModel):
    """A raw measurement signal from instrumentation."""
    signal_id: str = Field(
        ...,
        pattern=r'^SIG-[A-Z0-9]{8}$',
        description="Unique signal identifier"
    )
    test_point: TestPoint = Field(..., description="Test point information")
    parameter: SignalParameter = Field(..., description="Type of measurement")
    value: float = Field(..., description="Measured value")
    unit: str = Field(..., description="Unit of measurement")
    accuracy: Optional[MeasurementAccuracy] = Field(None, description="Accuracy specification")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    instrument: Optional[InstrumentMetadata] = Field(None, description="Instrument information")
    measurement_conditions: Optional[MeasurementConditions] = Field(None, description="Measurement context")

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: str) -> str:
        valid_units = ['V', 'mV', 'A', 'mA', 'Ω', 'kΩ', 'W', 'mW', 'Hz', 'kHz', '°C', '%RH']
        if v not in valid_units:
            raise ValueError(f'Invalid unit: {v}. Must be one of {valid_units}')
        return v


class SignalStateMapping(BaseModel):
    """Mapping from raw signal to semantic state."""
    signal_id: str = Field(...)
    raw_value: float = Field(...)
    semantic_state: SemanticState = Field(...)
    confidence: float = Field(default=1.0, ge=0, le=1)


class SignalAnomaly(BaseModel):
    """Anomaly detected in signal measurement."""
    test_point: str = Field(...)
    expected: str = Field(..., description="Expected value/range")
    measured: str = Field(..., description="Measured value")
    deviation: Optional[str] = Field(None, description="Percentage deviation")
    severity: Severity = Field(..., description="Anomaly severity")


class ObservedSignals(BaseModel):
    """Interpreted signal data with semantic states."""
    interpretation: str = Field(..., description="Human-readable summary")
    anomalies: List[SignalAnomaly] = Field(default_factory=list)
    status: DiagnosticStatus = Field(default=DiagnosticStatus.UNKNOWN)
    state_mapping: List[SignalStateMapping] = Field(default_factory=list)


# =============================================================================
# 3. AGENT STATE MODELS
# =============================================================================

class Trigger(BaseModel):
    """User trigger for the diagnostic session."""
    type: str = Field(..., description="symptom_report, signal_submission, follow_up, verification_request")
    content: str = Field(..., description="User question or description")
    urgency: str = Field(default="normal", description="low, normal, high, critical")


class RawInput(BaseModel):
    """Raw input from the user."""
    trigger: Trigger = Field(...)
    signals: dict = Field(default_factory=dict, description="Signal data payload")
    context: dict = Field(default_factory=dict, description="Additional context")


class ValidationResult(BaseModel):
    """Result of input validation."""
    is_valid: bool = Field(default=True)
    error_message: Optional[str] = Field(None)
    workflow_type: WorkflowType = Field(default=WorkflowType.INITIAL)


class NodeHistoryEntry(BaseModel):
    """Record of node execution."""
    node_name: str = Field(...)
    status: NodeStatus = Field(default=NodeStatus.COMPLETED)
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class AgentMetadata(BaseModel):
    """Metadata for the agent session."""
    version: str = Field(default="1.0")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    equipment_id: str = Field(default="")
    processing_time_ms: int = Field(default=0)
    node_history: List[NodeHistoryEntry] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# 4. FAULT ANALYSIS MODELS
# =============================================================================

class SupportingEvidence(BaseModel):
    """Evidence supporting a hypothesis."""
    evidence: str = Field(...)
    source: str = Field(..., description="signal, documentation, logic")
    relevance_score: float = Field(default=0.5, ge=0, le=1)


class DifferentialDiagnosis(BaseModel):
    """Alternative diagnosis possibility."""
    cause: str = Field(...)
    probability: float = Field(ge=0, le=1)
    key_differentiator: str = Field(..., description="What test distinguishes this from primary")


class FaultHypothesis(BaseModel):
    """Primary fault hypothesis with evidence."""
    primary_cause: str = Field(...)
    confidence: float = Field(default=0.0, ge=0, le=1)
    component: Optional[str] = Field(None)
    failure_mode: Optional[str] = Field(None)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    differential_diagnoses: List[DifferentialDiagnosis] = Field(default_factory=list)


class ReasoningStep(BaseModel):
    """Step in the reasoning chain."""
    step: int = Field(...)
    observation: str = Field(...)
    inference: str = Field(...)
    source: str = Field(..., description="signal, documentation, logic")


class NextAction(BaseModel):
    """Recommended next diagnostic action."""
    action: ActionType = Field(...)
    target: str = Field(..., description="Test point or component")
    instruction: str = Field(..., description="Detailed instruction")
    expected_result: str = Field(..., description="Expected outcome if hypothesis correct")
    priority: Severity = Field(default=Severity.MEDIUM)
    safety_warning: Optional[str] = Field(None)


class DiagnosticLimitations(BaseModel):
    """Limitations of the current diagnosis."""
    missing_information: List[str] = Field(default_factory=list)
    uncertainty_factors: List[str] = Field(default_factory=list)
    recommended_expert_review: bool = Field(default=False)


# =============================================================================
# 5. EQUIPMENT AND ERROR MODELS
# =============================================================================

class EquipmentProfile(BaseModel):
    """Profile for a specific equipment model."""
    model_id: str = Field(...)
    name: str = Field(...)
    manufacturer: Optional[str] = None
    category: str = Field(default="power_supply")
    specifications: dict = Field(default_factory=dict)


class ThresholdRange(BaseModel):
    """Acceptable range for a signal."""
    min: Optional[float] = Field(None)
    max: Optional[float] = Field(None)


class ThresholdProfile(BaseModel):
    """Threshold configuration for signal interpretation."""
    parameter: SignalParameter = Field(...)
    nominal_value: float = Field(...)
    unit: str = Field(...)
    thresholds: dict = Field(..., description="State -> range mapping")
    hysteresis: float = Field(default=0.05, description="Hysteresis as fraction of range")


class ErrorCode(BaseModel):
    """Defined error code with details."""
    code: str = Field(..., description="e.g., ERR-001")
    category: ErrorCategory = Field(...)
    severity: Severity = Field(...)
    message: str = Field(..., description="User-facing message")
    description: str = Field(..., description="Technical description")
    resolution: Optional[str] = Field(None, description="Suggested resolution")


class TroubleshootingStep(BaseModel):
    """Individual troubleshooting step."""
    step_number: int = Field(...)
    action: str = Field(...)
    expected_result: str = Field(...)
    verification_method: str = Field(...)
    safety_notes: Optional[str] = None


class Recommendation(BaseModel):
    """Repair recommendation."""
    action: str = Field(..., description="What to do")
    priority: Severity = Field(...)
    verification_step: str = Field(..., description="How to verify")
    estimated_difficulty: DifficultyLevel = Field(default=DifficultyLevel.EASY)
    estimated_time_minutes: Optional[int] = None
    required_parts: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ResolutionTracking(BaseModel):
    """Track resolution progress."""
    recommendation: Recommendation = Field(...)
    status: str = Field(default="pending", description="pending, in_progress, completed, failed")
    completed_at: Optional[datetime] = None
    result_verified: bool = Field(default=False)
    notes: Optional[str] = None


# =============================================================================
# 6. CONTEXT AND CONFIGURATION MODELS
# =============================================================================

class RAGConfig(BaseModel):
    """RAG retrieval configuration."""
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.5, ge=0, le=1)
    namespace: Optional[str] = Field(None, description="ChromaDB namespace")
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class RetryConfig(BaseModel):
    """Retry behavior configuration."""
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_factor: float = Field(default=1.0)
    retry_on_statuses: List[str] = Field(default_factory=lambda: ["500", "503", "429"])


class TimeoutConfig(BaseModel):
    """Timeout configuration."""
    node_timeout_seconds: int = Field(default=60, ge=1, le=300)
    overall_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    rag_timeout_seconds: int = Field(default=30, ge=5, le=120)


class AgentBehaviorConfig(BaseModel):
    """Agent behavior parameters."""
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    max_differential_diagnoses: int = Field(default=3, ge=1, le=10)
    require_signal_evidence: bool = Field(default=True)
    auto_escalate_confidence_below: float = Field(default=0.3)


class GraphConfig(BaseModel):
    """LangGraph configuration."""
    rag: RAGConfig = Field(default_factory=RAGConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    behavior: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)


class ToolInput(BaseModel):
    """Input to a LangGraph tool/node."""
    tool_name: str = Field(...)
    parameters: dict = Field(default_factory=dict)
    context: Optional[dict] = Field(None)


class ToolOutput(BaseModel):
    """Output from a LangGraph tool/node."""
    tool_name: str = Field(...)
    success: bool = Field(default=True)
    result: Optional[dict] = Field(None)
    error: Optional[str] = None
    execution_time_ms: int = Field(default=0)


# =============================================================================
# 7. OUTPUT MODELS (I/O CONTRACT)
# =============================================================================

class EquipmentContext(BaseModel):
    """Equipment identification in output."""
    model: str = Field(...)
    serial: Optional[str] = Field(None)


class SignalEvidence(BaseModel):
    """Evidence from signal measurements."""
    matching_signals: List[dict] = Field(default_factory=list)
    conflicting_signals: List[dict] = Field(default_factory=list)


class Diagnosis(BaseModel):
    """Diagnosis section of output."""
    primary_cause: str = Field(...)
    confidence_score: float = Field(ge=0, le=1)
    contributing_factors: List[str] = Field(default_factory=list)
    signal_evidence: SignalEvidence = Field(default_factory=SignalEvidence)


class Citation(BaseModel):
    """Citation to knowledge base document."""
    document_id: str = Field(...)
    title: str = Field(...)
    relevant_section: Optional[str] = None
    relevance_score: float = Field(default=0.0, ge=0, le=1)


class AgentOutput(BaseModel):
    """
    Complete agent output conforming to I/O contract.
    This is the final response structure.
    """
    version: str = Field(default="1.0")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    equipment_context: EquipmentContext = Field(...)
    diagnosis: Diagnosis = Field(...)
    recommendations: List[Recommendation] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    reasoning_chain: List[ReasoningStep] = Field(default_factory=list)
    limitations: DiagnosticLimitations = Field(default_factory=DiagnosticLimitations)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# 8. SCENARIO MODELS (FOR MOCK DATA)
# =============================================================================

class ScenarioMetadata(BaseModel):
    """Metadata for a test scenario."""
    version: str = Field(default="1.0")
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    equipment_model: str = Field(default="CCTV-PSU-24W-V1")
    description: Optional[str] = None


class ExpectedDiagnosis(BaseModel):
    """Expected diagnosis for a scenario."""
    primary_cause: str = Field(...)
    confidence: float = Field(ge=0, le=1)
    supporting_evidence: List[str] = Field(default_factory=list)
    recommended_action: str = Field(...)
    verification_step: str = Field(...)


class FaultScenario(BaseModel):
    """
    Complete fault scenario for testing.
    Matches structure in data/mock_signals/scenarios.json
    """
    scenario_id: str = Field(..., pattern=r'^FAULT-[0-9]{3}$')
    name: str = Field(...)
    category: str = Field(...)
    difficulty: str = Field(default="medium")
    description: str = Field(...)
    signals: List[RawSignal] = Field(default_factory=list)
    expected_diagnosis: ExpectedDiagnosis = Field(default_factory=ExpectedDiagnosis)


class ScenarioCollection(BaseModel):
    """Collection of fault scenarios."""
    metadata: ScenarioMetadata = Field(default_factory=ScenarioMetadata)
    scenarios: List[FaultScenario] = Field(default_factory=list)


# =============================================================================
# 9. HELPER FUNCTIONS
# =============================================================================

def create_error_response(message: str, category: ErrorCategory = ErrorCategory.UNKNOWN) -> dict:
    """Create a standardized error response."""
    return {
        "error": True,
        "message": message,
        "category": category.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def validate_equipment_id(equipment_id: str) -> bool:
    """Validate equipment identifier format."""
    return bool(re.match(r'^[A-Za-z0-9_-]+$', equipment_id))


def calculate_confidence_interval(value: float, tolerance: float) -> tuple:
    """Calculate confidence interval from tolerance."""
    lower = value * (1 - tolerance / 100)
    upper = value * (1 + tolerance / 100)
    return (lower, upper)
