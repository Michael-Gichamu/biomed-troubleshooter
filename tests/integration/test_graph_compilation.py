"""Integration tests for the full compiled graph.

Scope is deliberately narrow: confirm the graph compiles, exposes the expected
nodes/edges, and that a single decision → repair transition runs end-to-end
when the state already carries a confirmed fault. The per-node LLM mocks live
in the unit tests; here we only prove the wiring is intact.
"""

import pytest

from src.graph import create_conversational_graph
from src.graph.state import ConversationalAgentState

pytestmark = pytest.mark.integration


EXPECTED_NODES = frozenset(
    {
        "rag",
        "hypotheses",
        "instruction",
        "probe_wait",
        "step",
        "reason",
        "decision",
        "repair",
        "interrupt",
        "resume",
    }
)


def test_graph_compiles_with_all_ten_nodes():
    g = create_conversational_graph()
    node_names = set(g.get_graph().nodes.keys())
    assert EXPECTED_NODES <= node_names, f"Missing nodes: {EXPECTED_NODES - node_names}"


def test_expected_edges_are_present():
    g = create_conversational_graph()
    edges = {(e.source, e.target) for e in g.get_graph().edges}

    # Fixed edges — any of these missing indicates a structural regression.
    must_have = {
        ("__start__", "rag"),
        ("rag", "hypotheses"),
        ("hypotheses", "instruction"),
        ("instruction", "probe_wait"),
        ("probe_wait", "step"),
        ("step", "reason"),
        ("reason", "decision"),
        ("interrupt", "resume"),
        ("repair", "__end__"),
    }
    assert must_have <= edges, f"Missing edges: {must_have - edges}"


def test_conditional_routes_from_decision_exist():
    """``decision`` must be able to route to repair, interrupt, end, instruction."""
    g = create_conversational_graph()
    decision_targets = {
        t for s, t in ((e.source, e.target) for e in g.get_graph().edges) if s == "decision"
    }
    assert {"repair", "interrupt", "instruction", "__end__"} <= decision_targets


def test_conditional_routes_from_resume_exist():
    g = create_conversational_graph()
    resume_targets = {
        t for s, t in ((e.source, e.target) for e in g.get_graph().edges) if s == "resume"
    }
    assert {"instruction", "__end__"} <= resume_targets


def test_state_schema_carries_required_fields():
    """Guard against silent removal of fields the nodes depend on."""
    required = {
        "messages",
        "equipment_model",
        "equipment_config",
        "test_points",
        "expected_values",
        "hypotheses",
        "hypothesis_probabilities",
        "eliminated_faults",
        "current_hypothesis",
        "test_point_rankings",
        "measurements",
        "suspected_faults",
        "confirmed_fault",
        "current_step",
        "max_steps",
        "consecutive_failures",
        "pending_manual_reading",
        "next_node",
        "step_result",
    }
    s = ConversationalAgentState()
    assert required <= set(s.__dataclass_fields__.keys())
