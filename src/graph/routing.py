"""Conditional-edge routing functions for the diagnostic graph."""

from src.graph.state import ConversationalAgentState


def route_from_decision(state: ConversationalAgentState) -> str:
    next_node = state.next_node or "interrupt"
    if next_node == "repair":
        return "repair"
    if next_node == "end":
        return "end"
    if next_node == "instruction":
        return "instruction"
    return "interrupt"


def route_from_resume(state: ConversationalAgentState) -> str:
    """Route after resume: go to instruction (which leads to step) or end."""
    if state.current_step >= state.max_steps:
        return "end"
    if state.current_step >= len(state.test_point_rankings):
        return "end"
    return "instruction"
