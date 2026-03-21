"""
Diagnostic State Management

Manages the state of a diagnostic session including:
- Current diagnostic step tracking
- Measurement recording and evaluation
- Hypothesis testing workflow
- Equipment configuration caching

This module provides the core state management for the diagnostic engine,
supporting pause/resume and LangGraph state persistence.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# DIAGNOSTIC STATE
# =============================================================================

class DiagnosticState(BaseModel):
    """
    Tracks the complete state of a diagnostic session.
    
    This is the central state object that persists across the diagnostic
    workflow and can be serialized for LangGraph state management.
    
    Attributes:
        equipment_model: Equipment model identifier (e.g., "cctv-psu-24w-v1")
        current_step: Current diagnostic step index (0-indexed)
        completed_steps: List of completed step indices
        measurements: Dictionary mapping test point names to measurement results
        current_hypothesis: Current fault hypothesis being tested
        hypothesis_list: Ordered list of hypotheses to test
        waiting_for_next: True if paused, waiting for user "Next"
        config_cached: True if equipment config has been loaded
        equipment_config: Cached equipment configuration (dict form for serialization)
        diagnosis_progress: Current progress status
        tested_points: Test points already measured
        eliminated_faults: Faults ruled out by measurements
        retrieved_context: RAG context for current hypothesis
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    equipment_model: str = Field(
        default="",
        description="Equipment model identifier (e.g., 'cctv-psu-24w-v1')"
    )
    current_step: int = Field(
        default=0,
        description="Current diagnostic step index (0-indexed)"
    )
    completed_steps: List[int] = Field(
        default_factory=list,
        description="List of completed step indices"
    )
    measurements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary mapping test point names to measurement results"
    )
    current_hypothesis: str = Field(
        default="",
        description="Current fault hypothesis being tested"
    )
    hypothesis_list: List[str] = Field(
        default_factory=list,
        description="Ordered list of hypotheses to test"
    )
    waiting_for_next: bool = Field(
        default=False,
        description="True if paused, waiting for user 'Next'"
    )
    config_cached: bool = Field(
        default=False,
        description="True if equipment config has been loaded"
    )
    equipment_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Cached equipment configuration (dict form for serialization)"
    )
    diagnosis_progress: Literal["in_progress", "completed", "fault_confirmed"] = Field(
        default="in_progress",
        description="Current progress status"
    )
    tested_points: List[str] = Field(
        default_factory=list,
        description="Test points already measured"
    )
    eliminated_faults: List[str] = Field(
        default_factory=list,
        description="Faults ruled out by measurements"
    )
    retrieved_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="RAG context for current hypothesis"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Unique session identifier"
    )
    symptoms: str = Field(
        default="",
        description="Initial symptoms description"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Session start timestamp"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Session completion timestamp"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiagnosticState":
        """Create state from dictionary."""
        return cls(**data)


# =============================================================================
# DIAGNOSTIC STEP
# =============================================================================

class DiagnosticStep(BaseModel):
    """
    Represents a single step in the diagnostic process.
    
    Each step corresponds to testing a specific test point to validate
    or eliminate a hypothesis.
    
    Attributes:
        step_number: Step index in the diagnostic sequence
        test_point_name: Name/ID of the test point to measure
        probe_placement_instructions: Instructions for probe placement
        image_url: URL to reference image showing test point location
        expected_value: Expected measurement value/range
        hypothesis_being_tested: Hypothesis this step is testing
        measurement_result: Actual measurement result (None if not yet measured)
        is_completed: Whether this step has been completed
        is_fault_confirmed: Whether this step confirmed the fault
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    step_number: int = Field(
        description="Step index in the diagnostic sequence"
    )
    test_point_name: str = Field(
        description="Name/ID of the test point to measure"
    )
    probe_placement_instructions: str = Field(
        default="",
        description="Instructions for probe placement"
    )
    image_url: str = Field(
        default="",
        description="URL to reference image showing test point location"
    )
    expected_value: str = Field(
        default="",
        description="Expected measurement value/range"
    )
    hypothesis_being_tested: str = Field(
        default="",
        description="Hypothesis this step is testing"
    )
    measurement_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Actual measurement result (None if not yet measured)"
    )
    is_completed: bool = Field(
        default=False,
        description="Whether this step has been completed"
    )
    is_fault_confirmed: bool = Field(
        default=False,
        description="Whether this step confirmed the fault"
    )
    signal_id: Optional[str] = Field(
        default=None,
        description="Signal ID for this test point"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiagnosticStep":
        """Create step from dictionary."""
        return cls(**data)


# =============================================================================
# MEASUREMENT RESULT
# =============================================================================

class MeasurementResult(BaseModel):
    """
    Represents a measurement result from a test point.
    
    Attributes:
        test_point: Test point identifier
        value: Measured value
        unit: Measurement unit
        timestamp: When the measurement was taken
        interpretation: Semantic interpretation of the value
        is_anomaly: Whether the value is anomalous
    """
    test_point: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    interpretation: Optional[str] = None
    is_anomaly: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_point": self.test_point,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "interpretation": self.interpretation,
            "is_anomaly": self.is_anomaly
        }


# =============================================================================
# DIAGNOSTIC ENGINE
# =============================================================================

class DiagnosticEngine:
    """
    Manages the diagnostic workflow.
    
    This engine orchestrates the diagnostic process by:
    1. Loading equipment configuration (once)
    2. Initializing diagnosis from symptoms
    3. Generating hypotheses to test
    4. Managing the step-by-step diagnostic process
    5. Evaluating measurement results
    6. Providing repair guidance when fault is confirmed
    
    The engine is designed to work with RAG for hypothesis generation
    and supports pause/resume via the waiting_for_next flag.
    """
    
    def __init__(
        self,
        equipment_config_loader=None,
        rag_repository=None,
        state: Optional[DiagnosticState] = None
    ):
        """
        Initialize the diagnostic engine.
        
        Args:
            equipment_config_loader: Optional EquipmentConfigLoader instance
            rag_repository: Optional RAGRepository instance for context retrieval
            state: Optional initial DiagnosticState
        """
        self._config_loader = equipment_config_loader
        self._rag_repo = rag_repository
        self._state = state or DiagnosticState()
        self._steps: List[DiagnosticStep] = []
    
    @property
    def state(self) -> DiagnosticState:
        """Get current diagnostic state."""
        return self._state
    
    def load_equipment_config(self, equipment_model: str) -> Dict[str, Any]:
        """
        Load and cache equipment configuration.
        
        This method should be called ONCE at the start of diagnosis.
        The configuration is cached in the state and never called again.
        
        Args:
            equipment_model: Equipment model identifier (e.g., "cctv-psu-24w-v1")
            
        Returns:
            Equipment configuration as dictionary
            
        Raises:
            FileNotFoundError: If equipment config doesn't exist
        """
        if self._state.config_cached and self._state.equipment_model == equipment_model:
            # Already cached, return cached config
            return self._state.equipment_config
        
        # Load from config loader
        if self._config_loader is None:
            from src.infrastructure.equipment_config import EquipmentConfigLoader
            self._config_loader = EquipmentConfigLoader()
        
        config = self._config_loader.load(equipment_model)
        
        # Cache in state as dict for serialization
        self._state.equipment_model = equipment_model
        self._state.equipment_config = self._config_to_dict(config)
        self._state.config_cached = True
        
        return self._state.equipment_config
    
    def _config_to_dict(self, config) -> Dict[str, Any]:
        """Convert EquipmentConfig to dictionary for caching."""
        return {
            "metadata": {
                "equipment_id": config.metadata.equipment_id,
                "name": config.metadata.name,
                "category": config.metadata.category,
                "manufacturer": config.metadata.manufacturer,
                "version": config.metadata.version,
                "created": config.metadata.created
            },
            "signals": {
                sid: {
                    "signal_id": s.signal_id,
                    "name": s.name,
                    "test_point": s.test_point,
                    "parameter": s.parameter,
                    "unit": s.unit,
                    "measurability": s.measurability,
                    "physical_description": s.physical_description,
                    "image_url": s.image_url,
                    "pro_tips": s.pro_tips
                }
                for sid, s in config.signals.items()
            },
            "thresholds": {
                tid: {
                    "signal_id": t.signal_id,
                    "states": {
                        name: {
                            "min": state.min_value,
                            "max": state.max_value,
                            "description": state.description
                        }
                        for name, state in t.states.items()
                    }
                }
                for tid, t in config.thresholds.items()
            },
            "faults": {
                fid: {
                    "fault_id": f.fault_id,
                    "name": f.name,
                    "description": f.description,
                    "priority": f.priority,
                    "signatures": f.signatures,
                    "hypotheses": [
                        {
                            "rank": h.rank,
                            "component": h.component,
                            "failure_mode": h.failure_mode,
                            "cause": h.cause,
                            "confidence": h.confidence
                        }
                        for h in f.hypotheses
                    ],
                    "recovery": [
                        {
                            "step": r.step,
                            "action": r.action,
                            "target": r.target,
                            "instruction": r.instruction,
                            "verification": r.verification,
                            "safety": r.safety,
                            "estimated_time": r.estimated_time,
                            "difficulty": r.difficulty,
                            "tools": r.tools
                        }
                        for r in f.recovery
                    ]
                }
                for fid, f in config.faults.items()
            },
            "images": {
                iid: {
                    "image_id": img.image_id,
                    "filename": img.filename,
                    "description": img.description,
                    "test_points": img.test_points,
                    "annotations": img.annotations
                }
                for iid, img in config.images.items()
            }
        }
    
    def initialize_diagnosis(self, symptoms: str) -> DiagnosticState:
        """
        Start a new diagnosis from symptoms.
        
        This initializes the diagnostic session and retrieves initial
        context from RAG if available.
        
        Args:
            symptoms: User-reported symptoms description
            
        Returns:
            Updated DiagnosticState
        """
        # Initialize session
        self._state.symptoms = symptoms
        self._state.started_at = datetime.now(timezone.utc)
        self._state.diagnosis_progress = "in_progress"
        
        # Generate hypotheses from symptoms
        if self._state.equipment_config:
            self._generate_hypotheses(symptoms)
        
        # Retrieve RAG context if available
        if self._rag_repo and self._state.equipment_model:
            context = self._rag_repo.retrieve(
                query=symptoms,
                equipment_model=self._state.equipment_model,
                top_k=5
            )
            self._state.retrieved_context = {
                "documents": [d.to_dict() for d in context],
                "query": symptoms
            }
        
        # Build initial steps
        self._build_diagnostic_steps()
        
        return self._state
    
    def _generate_hypotheses(self, symptoms: str) -> None:
        """Generate hypotheses from symptoms using equipment config."""
        config = self._state.equipment_config
        faults = config.get("faults", {})
        
        # Sort by priority and extract hypothesis list
        sorted_faults = sorted(
            faults.values(),
            key=lambda f: f.get("priority", 999)
        )
        
        self._state.hypothesis_list = [
            f"{f['fault_id']}: {f['name']}"
            for f in sorted_faults
        ]
        
        # Set initial hypothesis
        if self._state.hypothesis_list:
            self._state.current_hypothesis = self._state.hypothesis_list[0]
    
    def _build_diagnostic_steps(self) -> None:
        """Build diagnostic steps from current hypothesis."""
        self._steps = []
        
        if not self._state.current_hypothesis:
            return
        
        # Extract fault ID from hypothesis
        fault_id = self._state.current_hypothesis.split(":")[0]
        config = self._state.equipment_config
        fault = config.get("faults", {}).get(fault_id)
        
        if not fault:
            return
        
        # Get hypotheses for this fault
        hypotheses = fault.get("hypotheses", [])
        
        step_num = 0
        for hypothesis in hypotheses:
            # Get signal info for test point
            component = hypothesis.get("component", "")
            
            # Find signal for this component
            signals = config.get("signals", {})
            signal = None
            for sid, s in signals.items():
                if s.get("test_point") == component or s.get("name", "").lower() in component.lower():
                    signal = s
                    break
            
            if signal:
                step = DiagnosticStep(
                    step_number=step_num,
                    test_point_name=signal.get("test_point", component),
                    probe_placement_instructions=signal.get("physical_description", ""),
                    image_url=signal.get("image_url", ""),
                    expected_value=self._get_expected_value(signal),
                    hypothesis_being_tested=hypothesis.get("cause", ""),
                    signal_id=signal.get("signal_id")
                )
                self._steps.append(step)
                step_num += 1
        
        self._state.current_step = 0
    
    def _get_expected_value(self, signal: Dict[str, Any]) -> str:
        """Get expected value string from signal config."""
        thresholds = self._state.equipment_config.get("thresholds", {})
        signal_id = signal.get("signal_id")
        
        if signal_id and signal_id in thresholds:
            threshold = thresholds[signal_id]
            states = threshold.get("states", {})
            
            if "normal" in states:
                normal = states["normal"]
                parts = []
                if normal.get("min") is not None:
                    parts.append(f"min: {normal['min']}")
                if normal.get("max") is not None:
                    parts.append(f"max: {normal['max']}")
                return f"{signal.get('unit', '')} ({', '.join(parts)})"
        
        return signal.get("unit", "")
    
    def get_current_step(self) -> Optional[DiagnosticStep]:
        """
        Get the current step for display.
        
        Returns:
            Current DiagnosticStep or None if no more steps
        """
        if self._state.current_step < len(self._steps):
            return self._steps[self._state.current_step]
        return None
    
    def record_measurement(self, test_point: str, result: Dict[str, Any]) -> DiagnosticState:
        """
        Record a measurement result.
        
        Args:
            test_point: Test point identifier
            result: Measurement result dictionary
            
        Returns:
            Updated DiagnosticState
        """
        # Store measurement
        self._state.measurements[test_point] = result
        self._state.tested_points.append(test_point)
        
        # Update current step if it matches
        current = self.get_current_step()
        if current and current.test_point_name == test_point:
            current.measurement_result = result
            current.is_completed = True
            self._state.completed_steps.append(self._state.current_step)
        
        return self._state
    
    def evaluate_step_result(self, measurement: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate if the measurement confirms a fault or requires continuing.
        
        Args:
            measurement: Measurement result dictionary
            
        Returns:
            Evaluation result with 'continue' or 'fault_confirmed' status
        """
        current = self.get_current_step()
        
        if not current:
            return {
                "status": "no_more_steps",
                "message": "No more diagnostic steps available"
            }
        
        # Get signal threshold config
        signal_id = current.signal_id
        thresholds = self._state.equipment_config.get("thresholds", {})
        
        if signal_id and signal_id in thresholds:
            threshold = thresholds[signal_id]
            value = measurement.get("value")
            
            if value is not None:
                # Evaluate against thresholds
                state = threshold.get("state")(value)
                
                # Check if fault signature matches
                fault_id = self._state.current_hypothesis.split(":")[0]
                fault = self._state.equipment_config.get("faults", {}).get(fault_id)
                
                if fault:
                    signatures = fault.get("signatures", [])
                    for sig in signatures:
                        if sig.get("signal_id") == signal_id and sig.get("state") == state:
                            # Fault confirmed!
                            current.is_fault_confirmed = True
                            self._state.diagnosis_progress = "fault_confirmed"
                            self._state.completed_at = datetime.now(timezone.utc)
                            
                            return {
                                "status": "fault_confirmed",
                                "fault_id": fault_id,
                                "fault_name": fault.get("name"),
                                "hypothesis": current.hypothesis_being_tested,
                                "message": f"Fault confirmed: {fault.get('description')}"
                            }
        
        # No fault confirmed, continue to next step
        return {
            "status": "continue",
            "message": "Measurement recorded. Proceed to next step."
        }
    
    def advance_to_next_step(self) -> DiagnosticState:
        """
        Move to the next hypothesis or step.
        
        Returns:
            Updated DiagnosticState
        """
        # Mark current step as complete
        self._state.waiting_for_next = False
        
        # Move to next step in current hypothesis
        next_step = self._state.current_step + 1
        
        if next_step < len(self._steps):
            self._state.current_step = next_step
        else:
            # Move to next hypothesis
            current_idx = 0
            if self._state.current_hypothesis in self._state.hypothesis_list:
                current_idx = self._state.hypothesis_list.index(self._state.current_hypothesis)
            
            next_idx = current_idx + 1
            if next_idx < len(self._state.hypothesis_list):
                self._state.current_hypothesis = self._state.hypothesis_list[next_idx]
                self._state.current_step = 0
                self._build_diagnostic_steps()
            else:
                # No more hypotheses - diagnosis complete
                self._state.diagnosis_progress = "completed"
                self._state.completed_at = datetime.now(timezone.utc)
        
        return self._state
    
    def pause(self) -> DiagnosticState:
        """
        Pause the diagnosis, waiting for user to continue.
        
        Returns:
            Updated DiagnosticState with waiting_for_next=True
        """
        self._state.waiting_for_next = True
        return self._state
    
    def resume(self) -> DiagnosticState:
        """
        Resume from paused state.
        
        Returns:
            Updated DiagnosticState with waiting_for_next=False
        """
        self._state.waiting_for_next = False
        return self.advance_to_next_step()
    
    def is_complete(self) -> bool:
        """
        Check if diagnosis is complete.
        
        Returns:
            True if diagnosis is complete or fault confirmed
        """
        return self._state.diagnosis_progress in ("completed", "fault_confirmed")
    
    def get_repair_guidance(self) -> Dict[str, Any]:
        """
        Get repair steps if fault is confirmed.
        
        Returns:
            Dictionary with repair guidance or error message
        """
        if self._state.diagnosis_progress != "fault_confirmed":
            return {
                "error": "No fault confirmed",
                "message": "Cannot provide repair guidance until fault is confirmed"
            }
        
        # Extract fault ID from hypothesis
        fault_id = self._state.current_hypothesis.split(":")[0]
        config = self._state.equipment_config
        fault = config.get("faults", {}).get(fault_id)
        
        if not fault:
            return {
                "error": "Fault not found",
                "message": f"Could not find fault configuration for {fault_id}"
            }
        
        return {
            "fault_id": fault_id,
            "fault_name": fault.get("name"),
            "description": fault.get("description"),
            "recovery_steps": fault.get("recovery", []),
            "diagnosis_summary": {
                "symptoms": self._state.symptoms,
                "measurements": self._state.measurements,
                "tested_points": self._state.tested_points,
                "confirmed_hypothesis": self._state.current_hypothesis
            }
        }
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current diagnostic progress.
        
        Returns:
            Dictionary with progress information
        """
        return {
            "equipment_model": self._state.equipment_model,
            "progress": self._state.diagnosis_progress,
            "current_step": self._state.current_step,
            "total_steps": len(self._steps),
            "current_hypothesis": self._state.current_hypothesis,
            "hypothesis_list": self._state.hypothesis_list,
            "tested_points": self._state.tested_points,
            "eliminated_faults": self._state.eliminated_faults,
            "measurements_count": len(self._state.measurements),
            "waiting_for_next": self._state.waiting_for_next,
            "session_id": self._state.session_id,
            "started_at": self._state.started_at.isoformat() if self._state.started_at else None,
            "completed_at": self._state.completed_at.isoformat() if self._state.completed_at else None
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_diagnostic_engine(
    equipment_model: str,
    symptoms: str,
    equipment_config_loader=None,
    rag_repository=None
) -> DiagnosticEngine:
    """
    Create and initialize a diagnostic engine.
    
    This is the main factory function for creating a new diagnostic session.
    
    Args:
        equipment_model: Equipment model identifier
        symptoms: Initial symptoms description
        equipment_config_loader: Optional EquipmentConfigLoader
        rag_repository: Optional RAGRepository
        
    Returns:
        Initialized DiagnosticEngine
    """
    import uuid
    
    # Create state with session ID
    state = DiagnosticState(
        session_id=str(uuid.uuid4()),
        equipment_model=equipment_model,
        symptoms=symptoms,
        started_at=datetime.now(timezone.utc)
    )
    
    engine = DiagnosticEngine(
        equipment_config_loader=equipment_config_loader,
        rag_repository=rag_repository,
        state=state
    )
    
    # Load config and initialize
    engine.load_equipment_config(equipment_model)
    engine.initialize_diagnosis(symptoms)
    
    return engine


def load_diagnostic_engine(
    state_dict: Dict[str, Any],
    equipment_config_loader=None,
    rag_repository=None
) -> DiagnosticEngine:
    """
    Load a diagnostic engine from serialized state.
    
    Args:
        state_dict: Serialized state dictionary
        equipment_config_loader: Optional EquipmentConfigLoader
        rag_repository: Optional RAGRepository
        
    Returns:
        Restored DiagnosticEngine
    """
    state = DiagnosticState.from_dict(state_dict)
    
    return DiagnosticEngine(
        equipment_config_loader=equipment_config_loader,
        rag_repository=rag_repository,
        state=state
    )
