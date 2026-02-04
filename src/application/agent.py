"""
LangGraph Agent Implementation

Deterministic agent control flow using LangGraph.
Each node is a pure function with explicit inputs/outputs.

NOTE: All equipment-specific knowledge comes from equipment config files.
NO hard-coded equipment logic exists in this file.
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
    WorkflowType,
    ReasoningStep,
)
from src.infrastructure.rag_repository import RAGRepository, EvidenceAggregator
from src.infrastructure.equipment_config import (
    EquipmentConfigLoader,
    get_equipment_config,
)


# =============================================================================
# AGENT STATE (LangGraph state)
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
    workflow_type: str = WorkflowType.INITIAL

    # === INTERPRETATION ===
    signal_states: dict = field(default_factory=dict)  # signal_id -> state
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
# NODES (Data-driven, no equipment-specific logic)
# =============================================================================

def validate_input(state: AgentState) -> AgentState:
    """
    Node: Validate incoming request.

    Contract:
        Input: Raw user input with trigger and measurements
        Output: Validated state with workflow type
        Errors: Sets is_valid=False with error message
    """
    print(f"\n[NODE] validate_input | session={state.session_id[:8] if state.session_id else 'none'}")

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

    print(f"  [OK] Validated: workflow={state.workflow_type}")
    return state


def interpret_signals(state: AgentState) -> AgentState:
    """
    Node: Interpret raw measurements into semantic states.

    Contract:
        Input: Validated measurements
        Output: Signal states with semantic interpretation
                (states come from equipment config, NOT hard-coded)
    """
    print(f"\n[NODE] interpret_signals | count={len(state.raw_measurements)}")
    state.node_history.append("interpret_signals")

    # Load equipment configuration
    try:
        config = get_equipment_config(state.equipment_model)
    except FileNotFoundError:
        print(f"  [WARN] Equipment config not found: {state.equipment_model}")
        config = None

    # Build threshold configs from equipment file
    threshold_configs = {}
    if config:
        for signal_id, threshold in config.thresholds.items():
            threshold_configs[signal_id] = threshold

    # Use interpreter with equipment-specific thresholds
    interpreter = SignalInterpreter(threshold_configs)

    # Build signal collection
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

    # Interpret using equipment-specific thresholds
    signal_states, status = interpreter.interpret(signal_collection)

    # Serialize state: signal_id -> semantic state
    state.signal_states = {
        s.measurement.test_point.id: s.state
        for s in signal_states
    }

    state.overall_status = status
    state.anomaly_count = sum(1 for s in signal_states if s.is_anomaly())

    print(f"  [OK] Status: {state.overall_status} | anomalies: {state.anomaly_count}")
    return state


def retrieve_evidence(state: AgentState) -> AgentState:
    """
    Node: Retrieve evidence from RAG and equipment config.

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

    state.retrieved_evidence = evidence

    print(f"  [OK] Retrieved {len(evidence.get('documents', []))} documents")
    return state


def analyze_fault(state: AgentState) -> AgentState:
    """
    Node: Analyze fault using equipment configuration.

    Contract:
        Input: Signal states and evidence
        Output: Hypothesis from equipment config fault definitions
                (NOT hard-coded logic)
    """
    print(f"\n[NODE] analyze_fault")
    state.node_history.append("analyze_fault")

    # Load equipment configuration
    try:
        config = get_equipment_config(state.equipment_model)
    except FileNotFoundError:
        print(f"  [WARN] Equipment config not found")
        config = None

    # Build fault configs from equipment file
    fault_configs = {}
    if config:
        for fault_id, fault in config.faults.items():
            fault_configs[fault_id] = {
                "fault_id": fault.fault_id,
                "name": fault.name,
                "description": fault.description,
                "signatures": fault.signatures,
                "hypotheses": [
                    {
                        "rank": h.rank,
                        "component": h.component,
                        "failure_mode": h.failure_mode,
                        "cause": h.cause,
                        "confidence": h.confidence
                    }
                    for h in fault.hypotheses
                ]
            }

    # Generate hypothesis using equipment-specific fault definitions
    generator = HypothesisGenerator(fault_configs)

    evidence = [
        f"{signal_id}: {state}"
        for signal_id, state in state.signal_states.items()
    ]

    hypothesis = generator.generate(
        equipment_id=state.equipment_model,
        signal_states=state.signal_states,
        evidence=evidence
    )

    state.hypothesis = hypothesis

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
            "observation": f"Found {len(fault_configs)} fault definitions in equipment config",
            "inference": f"Matched fault: {hypothesis.get('cause', 'None')[:50]}...",
            "source": "config"
        }
    ]

    print(f"  [OK] Hypothesis: {hypothesis.get('cause', 'Unknown')[:50]}... | confidence: {hypothesis.get('confidence', 0.0)}")
    return state


def generate_recommendations(state: AgentState) -> AgentState:
    """
    Node: Generate troubleshooting recommendations from equipment config.

    Contract:
        Input: Hypothesis and equipment config
        Output: Recommendations from equipment fault recovery steps
                (NOT hard-coded actions)
    """
    print(f"\n[NODE] generate_recommendations")
    state.node_history.append("generate_recommendations")

    # Load equipment configuration
    try:
        config = get_equipment_config(state.equipment_model)
    except FileNotFoundError:
        config = None

    # Build fault configs
    fault_configs = {}
    if config:
        for fault_id, fault in config.faults.items():
            fault_configs[fault_id] = {
                "fault_id": fault.fault_id,
                "recovery": [
                    {
                        "step": r.step,
                        "action": r.action,
                        "target": r.target,
                        "instruction": r.instruction,
                        "verification": r.verification,
                        "safety": r.safety,
                        "difficulty": r.difficulty,
                        "estimated_time": r.estimated_time
                    }
                    for r in fault.recovery
                ]
            }

    # Generate recommendations using equipment-specific recovery steps
    generator = RecommendationGenerator(fault_configs)

    fault_id = state.hypothesis.get("fault_id")
    recommendations = generator.generate(fault_id or "unknown", state.signal_states)

    if not recommendations:
        # Fallback generic recommendation
        recommendations = [
            {
                "action": "inspect",
                "target": "Equipment",
                "instruction": "Perform visual inspection for obvious damage",
                "verification_step": "Note any damage found",
                "estimated_difficulty": "easy",
                "safety_warning": "Ensure power is disconnected"
            }
        ]

    state.recommendations = recommendations

    print(f"  [OK] Generated {len(recommendations)} recommendation(s)")
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
            "primary_cause": state.hypothesis.get("cause", "Unknown"),
            "confidence_score": state.hypothesis.get("confidence", 0.0),
            "contributing_factors": state.hypothesis.get("supporting_evidence", []),
            "signal_evidence": {
                "matching_signals": [
                    {"signal_id": k, "state": v}
                    for k, v in state.signal_states.items()
                ],
                "conflicting_signals": []
            }
        },
        "recommendations": state.recommendations,
        "citations": state.retrieved_evidence.get("documents", []),
        "reasoning_chain": state.reasoning_chain,
        "limitations": {
            "missing_information": [],
            "uncertainty_factors": ["Analysis based on equipment config"],
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
    """
    import time

    # Initialize state
    state = AgentState(
        trigger_type=trigger_type,
        trigger_content=trigger_content,
        equipment_model=equipment_model,
        equipment_serial=equipment_serial,
        raw_measurements=measurements,
        session_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    print("=" * 60)
    print("BIOMEDICAL EQUIPMENT TROUBLESHOOTING AGENT")
    print("=" * 60)
    print(f"Session ID: {state.session_id}")
    print(f"Equipment: {equipment_model}")
    print(f"Measurements: {len(measurements)}")

    start = time.time()

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

    return result.response


if __name__ == "__main__":
    # Demo run with data-driven equipment config
    run_diagnostic(
        trigger_type="signal_submission",
        trigger_content="CCTV power supply not outputting 12V",
        equipment_model="cctv-psu-24w-v1",
        equipment_serial="",
        measurements=[
            {"test_point": "TP2", "value": 0.05, "unit": "V"},
            {"test_point": "TP3", "value": 0.0, "unit": "V"}
        ]
    )
