"""
LangGraph Agent Implementation

Deterministic agent control flow using LangGraph.
Each node is a pure function with explicit inputs/outputs.

Observability:
- LangSmith tracing for debugging and monitoring
- Configurable via environment variables or explicit configuration
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.domain.models import (
    SignalCollection,
    EquipmentId,
    SignalInterpreter,
    HypothesisGenerator,
    TroubleshootingStep,
    WorkflowType,
    Severity,
    SemanticState,
)
from src.infrastructure.rag_repository import RAGRepository, EvidenceAggregator
from src.infrastructure.langsmith_client import (
    get_langsmith_client,
    configure_langsmith,
    LangSmithConfig,
)


# =============================================================================
# LANGSMITH CONFIGURATION
# =============================================================================

def initialize_observability(
    api_key: str = None,
    project_name: str = "biomed-troubleshooter",
    enabled: bool = True
) -> None:
    """
    Initialize LangSmith observability.

    Environment variables:
        LANGCHAIN_API_KEY: LangSmith API key
        LANGCHAIN_PROJECT: Project name (default: biomed-troubleshooter)
        LANGCHAIN_TRACING: Enable tracing (default: true)
    """
    configure_langsmith(
        api_key=api_key,
        project_name=project_name,
        enabled=enabled
    )


# =============================================================================
# AGENT STATE (Strict Pydantic-like dataclass for LangGraph)
# =============================================================================

@dataclass
class AgentState:
    """
    Immutable state passed between LangGraph nodes.

    Design Principles:
    - All fields explicitly typed
    - No hidden state or implicit dependencies
    - Serializable for debugging/replay
    """

    # === INPUT ===
    trigger_type: str = ""
    trigger_content: str = ""
    equipment_model: str = ""
    equipment_serial: str = ""
    raw_measurements: list[dict] = field(default_factory=list)

    # === VALIDATION ===
    is_valid: bool = True
    validation_error: str = ""
    workflow_type: WorkflowType = WorkflowType.INITIAL

    # === INTERPRETATION ===
    signal_states: list[dict] = field(default_factory=list)
    overall_status: str = "unknown"
    anomaly_count: int = 0

    # === EVIDENCE RETRIEVAL ===
    retrieved_evidence: dict = field(default_factory=dict)

    # === ANALYSIS ===
    hypothesis: dict = field(default_factory=dict)
    reasoning_chain: list[dict] = field(default_factory=list)

    # === OUTPUT ===
    recommendations: list[dict] = field(default_factory=list)
    response: dict = field(default_factory=dict)

    # === METADATA ===
    session_id: str = ""
    node_history: list[str] = field(default_factory=list)
    timestamp: str = ""
    processing_time_ms: int = 0


# =============================================================================
# NODES (Pure functions with explicit contracts)
# =============================================================================

def validate_input(state: AgentState) -> AgentState:
    """
    Node: Validate incoming request.

    Contract:
        Input: Raw user input with trigger and measurements
        Output: Validated state with workflow type
        Errors: Sets is_valid=False with error message
    """
    print(f"\n[NODE] validate_input | session={state.session_id[:8]}")

    # Track node
    state.node_history.append("validate_input")

    # Validate required fields
    if not state.equipment_model:
        state.is_valid = False
        state.validation_error = "Equipment model is required"
        return state

    if not state.raw_measurements:
        state.is_valid = False
        state.validation_error = "At least one measurement is required"
        return state

    # Determine workflow type from trigger
    if state.trigger_type in ("follow_up", "verification"):
        state.workflow_type = WorkflowType.FOLLOW_UP
    else:
        state.workflow_type = WorkflowType.INITIAL

    print(f"  [OK] Validated: workflow={state.workflow_type.value}")
    return state


def interpret_signals(state: AgentState) -> AgentState:
    """
    Node: Interpret raw measurements into semantic states.

    Contract:
        Input: Validated measurements
        Output: Signal states with semantic interpretation
    """
    print(f"\n[NODE] interpret_signals | count={len(state.raw_measurements)}")
    state.node_history.append("interpret_signals")

    # Build signal collection from raw measurements
    equipment_id = EquipmentId(model=state.equipment_model, serial=state.equipment_serial)
    signal_collection = SignalCollection(
        equipment_id=equipment_id,
        collected_at=datetime.now(timezone.utc)
    )

    for m in state.raw_measurements:
        from src.domain.models import TestPoint, Measurement

        tp = TestPoint(
            id=m["test_point"],
            name=m.get("name", m["test_point"]),
            location=m.get("location"),
            component_id=m.get("component")
        )

        measurement = Measurement(
            test_point=tp,
            value=m["value"],
            unit=m["unit"],
            nominal_value=m.get("nominal"),
            tolerance_percent=m.get("tolerance")
        )
        signal_collection.add_measurement(measurement)

    # Use signal interpreter (domain service)
    interpreter = SignalInterpreter(thresholds={})
    signal_states, status = interpreter.interpret(signal_collection)

    # Serialize for state
    state.signal_states = [
        {
            "test_point_id": s.measurement.test_point.id,
            "value": s.measurement.value,
            "unit": s.measurement.unit,
            "semantic_state": s.semantic_state.value,
            "confidence": s.confidence,
            "deviation_percent": s.deviation_percent
        }
        for s in signal_states
    ]

    state.overall_status = status.value
    state.anomaly_count = sum(1 for s in signal_states if s.is_anomaly())

    print(f"  [OK] Status: {state.overall_status} | anomalies: {state.anomaly_count}")
    return state


def retrieve_evidence(state: AgentState) -> AgentState:
    """
    Node: Retrieve evidence from RAG and static rules.

    Contract:
        Input: Signal states and query
        Output: Evidence from knowledge base
    """
    print(f"\n[NODE] retrieve_evidence")
    state.node_history.append("retrieve_evidence")

    # Build query from trigger content
    query = state.trigger_content or "troubleshoot power supply"

    # Initialize RAG repository
    rag = RAGRepository()
    try:
        rag.initialize()
    except RuntimeError as e:
        print(f"  [WARN] RAG unavailable: {e}")
        state.retrieved_evidence = {"documents": [], "rules": [], "error": str(e)}
        return state

    # Retrieve evidence
    evidence = rag.retrieve(
        query=query,
        equipment_model=state.equipment_model,
        top_k=5
    )

    # Extract signal patterns for rule matching
    signal_patterns = [
        {"test_point_id": s["test_point_id"], "state": s["semantic_state"]}
        for s in state.signal_states
    ]

    from src.infrastructure.rag_repository import EvidenceAggregator, StaticRuleRepository
    static = StaticRuleRepository()
    aggregator = EvidenceAggregator(rag, static)

    all_evidence = aggregator.retrieve_evidence(
        query=query,
        equipment_model=state.equipment_model,
        signal_patterns=signal_patterns
    )

    state.retrieved_evidence = all_evidence

    print(f"  [OK] Retrieved {len(all_evidence.get('documents', []))} docs, {len(all_evidence.get('rules', []))} rules")
    return state


def analyze_fault(state: AgentState) -> AgentState:
    """
    Node: Analyze fault using deterministic rules.

    Contract:
        Input: Signal states and evidence
        Output: Hypothesis with reasoning chain
    """
    print(f"\n[NODE] analyze_fault")
    state.node_history.append("analyze_fault")

    # Build signal states for rule matching
    from src.domain.models import SignalState, SemanticState, DiagnosticRule

    states = []
    for s in state.signal_states:
        ss = SignalState(
            measurement=None,  # Not needed for matching
            semantic_state=SemanticState(s["semantic_state"]),
            confidence=s["confidence"]
        )
        states.append(ss)

    # Get evidence
    evidence = state.retrieved_evidence
    rules = evidence.get("rules", [])

    # Evaluate rules
    from src.domain.models import DiagnosticRuleEngine

    diagnostic_rules = [
        DiagnosticRule(
            rule_id=r.get("rule_id", "unknown"),
            name=r.get("name", "Unknown"),
            cause=r.get("cause", "Unknown"),
            confidence=r.get("confidence", 0.0),
            component=r.get("component"),
            failure_mode=r.get("failure_mode"),
            required_signals=r.get("required_signals", [])
        )
        for r in rules
    ]

    engine = DiagnosticRuleEngine(diagnostic_rules)
    matched = engine.evaluate(
        EquipmentId(model=state.equipment_model),
        states
    )

    # Generate hypothesis
    if matched:
        best = matched[0]
        state.hypothesis = {
            "primary_cause": best.cause,
            "confidence": best.confidence,
            "component": best.component,
            "failure_mode": best.failure_mode,
            "supporting_evidence": [r.description for r in matched],
            "contradicting_evidence": []
        }
    else:
        state.hypothesis = {
            "primary_cause": "No matching diagnostic rule - manual inspection required",
            "confidence": 0.0,
            "component": None,
            "failure_mode": None,
            "supporting_evidence": [],
            "contradicting_evidence": []
        }

    # Build reasoning chain
    state.reasoning_chain = [
        {
            "step": 1,
            "observation": f"Received {len(state.signal_states)} signal measurements",
            "inference": f"Overall status: {state.overall_status}",
            "source": "signal"
        },
        {
            "step": 2,
            "observation": f"Retrieved {len(rules)} diagnostic rules",
            "inference": f"Matched {len(matched)} rules to signal patterns",
            "source": "documentation"
        }
    ]

    print(f"  [OK] Hypothesis: {state.hypothesis['primary_cause'][:50]}... | confidence: {state.hypothesis['confidence']}")
    return state


def generate_recommendations(state: AgentState) -> AgentState:
    """
    Node: Generate troubleshooting recommendations.

    Contract:
        Input: Hypothesis and evidence
        Output: Prioritized recommendations
    """
    print(f"\n[NODE] generate_recommendations")
    state.node_history.append("generate_recommendations")

    hypothesis = state.hypothesis
    confidence = hypothesis.get("confidence", 0.0)

    # Determine priority based on confidence and status
    if state.overall_status == "failed" or confidence >= 0.8:
        priority = Severity.CRITICAL
    elif state.overall_status == "degraded" or confidence >= 0.5:
        priority = Severity.HIGH
    else:
        priority = Severity.MEDIUM

    # Generate recommendation based on hypothesis
    cause = hypothesis.get("primary_cause", "Unknown")

    if "output" in cause.lower() and "voltage" in cause.lower():
        action = "replace"
        target = "Output capacitor or regulator"
    elif "short" in cause.lower() or "shorted" in cause.lower():
        action = "inspect"
        target = "Shorted component"
    elif "open" in cause.lower() or "missing" in cause.lower():
        action = "replace"
        target = "Failed component"
    else:
        action = "measure"
        target = "Suspicious test points"

    state.recommendations = [
        {
            "action": action,
            "priority": priority.value,
            "target": target,
            "instruction": f"Verify {target} according to service manual",
            "expected_result": "Confirmation of root cause",
            "estimated_difficulty": "moderate",
            "safety_warning": "Ensure power is disconnected before internal inspection"
        }
    ]

    print(f"  [OK] Generated {len(state.recommendations)} recommendation(s)")
    return state


def generate_response(state: AgentState) -> AgentState:
    """
    Node: Generate final response.

    Contract:
        Input: Complete analysis
        Output: Structured response per I/O contract
    """
    print(f"\n[NODE] generate_response")
    state.node_history.append("generate_response")

    # Build response
    state.response = {
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": state.session_id,
        "equipment_context": {
            "model": state.equipment_model,
            "serial": state.equipment_serial
        },
        "diagnosis": {
            "primary_cause": state.hypothesis.get("primary_cause", "Unknown"),
            "confidence_score": state.hypothesis.get("confidence", 0.0),
            "contributing_factors": [],
            "signal_evidence": {
                "matching_signals": state.signal_states,
                "conflicting_signals": []
            }
        },
        "recommendations": state.recommendations,
        "citations": [],
        "reasoning_chain": state.reasoning_chain,
        "limitations": {
            "missing_information": [],
            "uncertainty_factors": ["Static rule-based analysis - may miss edge cases"],
            "recommended_expert_review": state.hypothesis.get("confidence", 1.0) < 0.7
        },
        "metadata": {
            "processing_time_ms": state.processing_time_ms,
            "nodes_executed": len(state.node_history)
        }
    }

    print(f"  [OK] Response generated")
    return state


def return_error(state: AgentState) -> AgentState:
    """Node: Return error response."""
    print(f"\n[NODE] return_error | {state.validation_error}")
    state.node_history.append("return_error")

    state.response = {
        "error": True,
        "message": state.validation_error or "Validation failed",
        "session_id": state.session_id
    }

    return state


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def build_graph() -> StateGraph:
    """Build the LangGraph state machine."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("validate_input", validate_input)
    builder.add_node("interpret_signals", interpret_signals)
    builder.add_node("retrieve_evidence", retrieve_evidence)
    builder.add_node("analyze_fault", analyze_fault)
    builder.add_node("generate_recommendations", generate_recommendations)
    builder.add_node("generate_response", generate_response)
    builder.add_node("return_error", return_error)

    # Entry point
    builder.set_entry_point("validate_input")

    # Define flow
    builder.add_edge("validate_input", "interpret_signals")
    builder.add_edge("interpret_signals", "retrieve_evidence")
    builder.add_edge("retrieve_evidence", "analyze_fault")
    builder.add_edge("analyze_fault", "generate_recommendations")
    builder.add_edge("generate_recommendations", "generate_response")
    builder.add_edge("generate_response", END)

    # Conditional routing for validation
    def route_validation(state: AgentState) -> str:
        if state.is_valid:
            return "interpret_signals"
        return "return_error"

    builder.add_conditional_edges(
        "validate_input",
        route_validation,
        {
            "interpret_signals": "interpret_signals",
            "return_error": "return_error"
        }
    )

    return builder


def compile_graph() -> Any:
    """Compile the graph with checkpointing."""
    builder = build_graph()
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


# =============================================================================
# ENTRY POINT
# =============================================================================

def run_diagnostic(
    trigger_type: str,
    trigger_content: str,
    equipment_model: str,
    equipment_serial: str,
    measurements: list[dict],
    enable_tracing: bool = True
) -> dict:
    """
    Run a complete diagnostic session.

    This is the main entry point for the agent.

    Args:
        trigger_type: Type of trigger (symptom_report, signal_submission, etc.)
        trigger_content: Description of the problem
        equipment_model: Equipment model identifier
        equipment_serial: Equipment serial number (optional)
        measurements: List of measurement dicts
        enable_tracing: Enable LangSmith tracing (default: True)

    Returns:
        Diagnostic response dict
    """
    import time

    # Initialize LangSmith if enabled
    if enable_tracing:
        initialize_observability()

    langsmith = get_langsmith_client()

    # Create parent trace run
    session_id = str(uuid.uuid4())
    run_id = None

    if langsmith.is_enabled():
        run_id = langsmith.create_run(
            name="diagnostic_session",
            run_type="chain",
            inputs={
                "trigger_type": trigger_type,
                "trigger_content": trigger_content,
                "equipment_model": equipment_model,
                "equipment_serial": equipment_serial,
                "measurement_count": len(measurements)
            }
        )

    # Initialize state
    state = AgentState(
        trigger_type=trigger_type,
        trigger_content=trigger_content,
        equipment_model=equipment_model,
        equipment_serial=equipment_serial,
        raw_measurements=measurements,
        session_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    print("=" * 60)
    print("BIOMEDICAL EQUIPMENT TROUBLESHOOTING AGENT")
    print("=" * 60)
    print(f"Session ID: {state.session_id}")
    print(f"Equipment: {equipment_model}")
    print(f"Measurements: {len(measurements)}")
    if langsmith.is_enabled():
        print("[LangSmith] Tracing enabled")

    start = time.time()

    try:
        # Run graph
        graph = compile_graph()
        result = graph.invoke(state)

        elapsed_ms = int((time.time() - start) * 1000)
        result.processing_time_ms = elapsed_ms

        print("\n" + "=" * 60)
        print(f"COMPLETE ({elapsed_ms}ms)")
        print("=" * 60)
        print(f"Nodes: {' → '.join(result.node_history)}")
        print(f"Status: {'error' if result.response.get('error') else 'success'}")

        # End trace run
        if run_id:
            langsmith.end_run(
                run_id,
                outputs={
                    "status": result.response.get("error", "success"),
                    "processing_time_ms": elapsed_ms,
                    "nodes_executed": len(result.node_history),
                    "hypothesis": result.response.get("diagnosis", {}).get("primary_cause", "N/A")
                }
            )

        return result.response

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)

        if run_id:
            langsmith.end_run(run_id, outputs={}, error=str(e))

        raise


if __name__ == "__main__":
    # Demo run
    run_diagnostic(
        trigger_type="signal_submission",
        trigger_content="CCTV power supply not outputting 12V",
        equipment_model="CCTV-PSU-24W-V1",
        equipment_serial="",
        measurements=[
            {"test_point": "TP1", "value": 232.0, "unit": "V", "nominal": 230.0, "tolerance": 10},
            {"test_point": "TP2", "value": 0.05, "unit": "V", "nominal": 12.0, "tolerance": 5}
        ]
    )
