"""
LangGraph Studio Compatible Wrapper

This module provides a LangGraph-compatible interface for LangGraph Studio.
It wraps the existing agent functionality with the StateGraph API.

Usage with LangGraph Studio:
    langgraph dev
"""

from dotenv import load_dotenv
from pathlib import Path
from langgraph.graph import START, StateGraph

from src.application.agent import (
    validate_input,
    interpret_signals,
    retrieve_evidence,
    analyze_fault,
    generate_recommendations,
    generate_response,
    AgentState
)


def create_diagnostic_graph() -> "StateGraph":
    """
    Create a LangGraph StateGraph for the diagnostic workflow.
    
    This graph follows the contract:
    - validate_input -> interpret_signals -> retrieve_evidence -> 
      analyze_fault -> generate_recommendations -> generate_response
    """
    # Build the StateGraph
    builder = StateGraph(AgentState)
    
    # Add all nodes
    builder.add_node("validate_input", validate_input)
    builder.add_node("interpret_signals", interpret_signals)
    builder.add_node("retrieve_evidence", retrieve_evidence)
    builder.add_node("analyze_fault", analyze_fault)
    builder.add_node("generate_recommendations", generate_recommendations)
    builder.add_node("generate_response", generate_response)
    
    # Define edges
    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "interpret_signals")
    builder.add_edge("interpret_signals", "retrieve_evidence")
    builder.add_edge("retrieve_evidence", "analyze_fault")
    builder.add_edge("analyze_fault", "generate_recommendations")
    builder.add_edge("generate_recommendations", "generate_response")
    
    # Compile with checkpointer (for LangGraph Studio state persistence)
    graph = builder.compile()
    
    return graph


def graph(input_state: dict) -> dict:
    """
    Simple graph function for LangGraph Studio.
    
    Args:
        input_state: Dictionary with:
            - equipment_model: str
            - equipment_serial: str
            - trigger_type: str
            - trigger_content: str
            - measurements: list[dict] with test_point, value, unit
    
    Returns:
        Graph execution result
    """
    # Load environment variables
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Create the graph
    diagnostic_graph = create_diagnostic_graph()
    
    # Convert input to AgentState (using correct field names)
    state = AgentState(
        equipment_model=input_state.get("equipment_model", "CCTV-PSU-24W-V1"),
        equipment_serial=input_state.get("equipment_serial", ""),
        trigger_type=input_state.get("trigger_type", "symptom_report"),
        trigger_content=input_state.get("trigger_content", "Equipment malfunction"),
        raw_measurements=input_state.get("measurements", []),
    )
    
    # Invoke the graph
    result = diagnostic_graph.invoke(state)
    
    return result


if __name__ == "__main__":
    # Test the graph directly
    test_input = {
        "equipment_model": "CCTV-PSU-24W-V1",
        "equipment_serial": "TEST-001",
        "trigger_type": "symptom_report",
        "trigger_content": "Equipment not functioning properly",
        "measurements": [
            {"test_point": "TP1", "value": 230.0, "unit": "V"},
            {"test_point": "TP2", "value": 12.3, "unit": "V"},
            {"test_point": "TP3", "value": 0.52, "unit": "A"},
        ]
    }
    
    result = graph(test_input)
    print("Graph result:", result)
