"""Integration: verify the ``reason → decision → repair`` transition wires
up correctly when the LLM confirms a hypothesis.

We call the nodes in sequence (not through the compiled graph invocation,
which would require a full checkpointer setup and input resolution) and
assert that the state updates propagate so that decision_node routes to
repair and repair_node produces a complete diagnosis message.
"""

import json

import pytest

from src.graph.nodes.decision import decision_node
from src.graph.nodes.reason import reason_node
from src.graph.nodes.repair import repair_node


pytestmark = pytest.mark.integration


def _merge(state, delta):
    """Apply a node's return dict onto the dataclass state."""
    for k, v in delta.items():
        if k == "messages":
            continue  # skip — not needed for flow assertions
        if hasattr(state, k):
            setattr(state, k, v)
    return state


def test_confirmed_hypothesis_flows_to_repair(base_state, mock_llm):
    # A FAULT measurement has been taken.
    base_state.measurements = [{
        "test_point": "primary_mosfet",
        "signal_name": "Primary MOSFET (Q1)",
        "value": 0.3,
        "unit": "ohm",
        "measurement_type": "CONTINUITY",
        "evaluation": "fault",
        "status": "success",
    }]

    # 1) reason_node — LLM confirms HYPOTHESIS_1.
    mock_llm(json.dumps({
        "reasoning": "Q1 shorted — cascade failure confirmed.",
        "probability_updates": {"HYPOTHESIS_1": 1.0, "HYPOTHESIS_2": 0.0},
        "eliminated_faults": ["HYPOTHESIS_2"],
        "confirmed_hypothesis": "HYPOTHESIS_1",
        "updated_remaining_test_plan": [],
    }))
    _merge(base_state, reason_node(base_state))
    assert base_state.step_result["decision"] == "fault_confirmed"

    # 2) decision_node — routes to repair.
    _merge(base_state, decision_node(base_state))
    assert base_state.next_node == "repair"

    # 3) repair_node — emits the repair plan.
    repair_result = repair_node(base_state)
    assert repair_result["diagnosis_complete"] is True
    content = repair_result["messages"][0].content
    assert "Shorted Primary MOSFET" in content
    assert "Replace Q1" in content
