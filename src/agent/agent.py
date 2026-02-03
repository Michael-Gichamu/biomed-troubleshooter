"""
LangGraph Agent Skeleton

Minimal implementation to verify graph flow.
Logic is stubbed - nodes log inputs and return dummy outputs.
Uses Pydantic models from models.py for type safety.
"""

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import StateGraph, END

from src.agent.models import (
    AgentState,
    WorkflowType,
    AgentOutput,
    ObservedSignals,
    FaultHypothesis,
    ReasoningStep,
    NextAction,
    Severity,
    create_error_response,
)


# =============================================================================
# 1. NODES (LOGIC STUBBED - JUST LOGGING AND DUMMY OUTPUTS)
# =============================================================================

def validate_input(state: AgentState) -> AgentState:
    """
    Node 1: Validate incoming request.
    - Checks required fields
    - Routes to workflow type
    """
    print(f"\n[NODE] validate_input")
    print(f"  Input: equipment_id='{state.equipment_id}', trigger='{state.trigger_type}'")

    # Stub: Assume valid for now
    state.is_valid = True
    state.workflow_type = WorkflowType.INITIAL
    state.error_message = ""

    # Add to node history
    state.node_history.append("validate_input")

    print(f"  Output: is_valid={state.is_valid}, workflow={state.workflow_type.value}")
    return state


def interpret_signals(state: AgentState) -> AgentState:
    """
    Node 2: Interpret raw measurements.
    - Maps to semantic states (stubbed)
    """
    print(f"\n[NODE] interpret_signals")
    print(f"  Input: {len(state.measurements)} measurements")

    # Stub: Return dummy semantic interpretation
    observed = ObservedSignals(
        interpretation=f"Processed {len(state.measurements)} signals from {state.equipment_id}",
        anomalies=[],
        status="normal",
        state_mapping=[]
    )

    state.observed_signals = observed.model_dump()
    state.node_history.append("interpret_signals")

    print(f"  Output: status='{state.observed_signals['status']}'")
    return state


def analyze_fault(state: AgentState) -> AgentState:
    """
    Node 3: Generate fault hypothesis.
    - Core reasoning (stubbed)
    """
    print(f"\n[NODE] analyze_fault")
    print(f"  Input: signals_status='{state.observed_signals.get('status', 'unknown')}'")

    # Stub: Return dummy diagnosis
    hypothesis = FaultHypothesis(
        primary_cause="Pending analysis - fault hypothesis generation stubbed",
        confidence=0.0,
        supporting_evidence=[],
        contradicting_evidence=[],
        differential_diagnoses=[]
    )

    reasoning = ReasoningStep(
        step=1,
        observation="Signal interpretation complete",
        inference="Awaiting full implementation",
        source="signal"
    )

    action = NextAction(
        action="measure",
        target="To be determined",
        instruction="Awaiting full implementation",
        expected_result="Awaiting full implementation",
        priority=Severity.MEDIUM
    )

    state.fault_hypothesis = hypothesis.model_dump()
    state.reasoning_chain = [reasoning.model_dump()]
    state.next_action = action.model_dump()
    state.node_history.append("analyze_fault")

    print(f"  Output: confidence={hypothesis.confidence}")
    return state


def generate_response(state: AgentState) -> AgentState:
    """
    Node 4: Format final output.
    - Assembles structured response using AgentOutput model
    """
    print(f"\n[NODE] generate_response")
    print(f"  Input: hypothesis='{state.fault_hypothesis.get('primary_cause', 'none')[:50]}...'")

    # Build response using Pydantic model
    diagnosis_data = state.fault_hypothesis
    next_action_data = state.next_action

    output = AgentOutput(
        timestamp=datetime.now(timezone.utc),
        equipment_context={
            "model": state.equipment_id,
            "serial": "UNKNOWN"
        },
        diagnosis={
            "primary_cause": diagnosis_data.get("primary_cause", "Unknown"),
            "confidence_score": diagnosis_data.get("confidence", 0.0),
            "contributing_factors": diagnosis_data.get("contributing_factors", []),
            "signal_evidence": {
                "matching_signals": [],
                "conflicting_signals": []
            }
        },
        recommendations=[
            {
                "action": next_action_data.get("action", "inspect"),
                "priority": next_action_data.get("priority", "low"),
                "verification_step": "Awaiting implementation",
                "estimated_difficulty": "easy"
            }
        ],
        citations=[],
        reasoning_chain=state.reasoning_chain,
        limitations={
            "missing_information": ["Full reasoning not yet implemented"],
            "uncertainty_factors": ["Stub implementation"],
            "recommended_expert_review": True
        }
    )

    state.output = output.model_dump()
    state.node_history.append("generate_response")

    print(f"  Output: response generated")
    return state


def return_error(state: AgentState) -> AgentState:
    """
    Node X: Error handler.
    - Returns user-friendly error
    """
    print(f"\n[NODE] return_error")
    print(f"  Input: error='{state.error_message}'")

    state.output = create_error_response(
        message=state.error_message or "Unknown validation error"
    )

    state.node_history.append("return_error")
    return state


# =============================================================================
# 2. GRAPH CONSTRUCTION
# =============================================================================

def build_graph() -> StateGraph:
    """
    Build the LangGraph state machine.
    """
    # Create graph with state schema
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("validate_input", validate_input)
    builder.add_node("interpret_signals", interpret_signals)
    builder.add_node("analyze_fault", analyze_fault)
    builder.add_node("generate_response", generate_response)
    builder.add_node("return_error", return_error)

    # Set entry point
    builder.set_entry_point("validate_input")

    # Define edges (basic routing)
    builder.add_edge("validate_input", "interpret_signals")
    builder.add_edge("interpret_signals", "analyze_fault")
    builder.add_edge("analyze_fault", "generate_response")
    builder.add_edge("generate_response", END)

    # Conditional edge for validation failure
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


# =============================================================================
# 3. RUNNER (FOR TESTING)
# =============================================================================

def run_dummy_session():
    """
    Run a dummy session to verify graph flow.
    """
    import time

    # Initialize state with dummy input
    initial_state = AgentState(
        trigger_type="signal_submission",
        trigger_content="CCTV power supply not working",
        equipment_id="CCTV-PSU-24W-V1",
        measurements=[
            {"test_point": "TP1", "value": 12.0, "unit": "V"},
            {"test_point": "TP2", "value": 5.0, "unit": "V"}
        ],
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    print("=" * 60)
    print("STARTING LANGGRAPH SESSION")
    print("=" * 60)

    start_time = time.time()

    # Build and run graph
    builder = build_graph()
    graph = builder.compile()

    result = graph.invoke(initial_state)

    elapsed_ms = int((time.time() - start_time) * 1000)

    print("\n" + "=" * 60)
    print(f"SESSION COMPLETE ({elapsed_ms}ms)")
    print("=" * 60)
    print(f"Nodes visited: {' → '.join(result.node_history)}")
    print(f"Final status: {'error' if result.output.get('error') else 'success'}")

    if not result.output.get('error'):
        print(f"\nDiagnosis: {result.output.get('diagnosis', {}).get('primary_cause', 'N/A')}")
        print(f"Confidence: {result.output.get('diagnosis', {}).get('confidence_score', 0.0)}")


if __name__ == "__main__":
    run_dummy_session()
