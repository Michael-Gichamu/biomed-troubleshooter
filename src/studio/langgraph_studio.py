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

# Load environment variables at module level (before async context)
# Use Path(__file__).parent without .resolve() to avoid blocking os.getcwd() call
_env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=_env_path)

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


def graph():
    """
    Return the compiled diagnostic graph for LangGraph Studio.
    
    This is a factory function that returns the graph definition.
    LangGraph Studio calls this to get the graph for visualization.
    Invocation happens separately when users run the graph from Studio.
    
    Returns:
        Compiled StateGraph for the diagnostic workflow
    """
    # Environment variables are loaded at module level
    
    # Build and return the graph (don't invoke it)
    return create_diagnostic_graph()


if __name__ == "__main__":
    # Test the graph factory
    compiled_graph = graph()
    print("Graph compiled successfully!")
    print(f"Graph nodes: {list(compiled_graph.nodes.keys())}")
