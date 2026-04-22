"""Unit tests for the ``decision`` node (pure — no LLM, no I/O)."""

from langchain_core.messages import AIMessage

from src.graph.nodes.decision import decision_node
from src.graph.state import ConversationalAgentState


def _state(**kwargs) -> ConversationalAgentState:
    """Build a decision-ready state with sensible defaults."""
    return ConversationalAgentState(
        hypotheses=kwargs.pop(
            "hypotheses",
            [
                {"id": "H1", "description": "a"},
                {"id": "H2", "description": "b"},
            ],
        ),
        hypothesis_probabilities=kwargs.pop("probs", {"H1": 0.5, "H2": 0.5}),
        test_point_rankings=kwargs.pop("rankings", ["tp1", "tp2", "tp3"]),
        step_result=kwargs.pop("step_result", {"decision": "continue_diagnosis"}),
        **kwargs,
    )


def test_confirmed_fault_short_circuits_to_repair():
    s = _state(confirmed_fault="Shorted Q1")
    assert decision_node(s) == {"next_node": "repair"}


def test_fault_confirmed_decision_routes_to_repair():
    s = _state(step_result={"decision": "fault_confirmed"})
    assert decision_node(s) == {"next_node": "repair"}


def test_retry_probe_loops_back_to_instruction():
    s = _state(step_result={"decision": "retry_probe"})
    assert decision_node(s) == {"next_node": "instruction"}


def test_abort_no_reading_ends_diagnosis():
    s = _state(step_result={"decision": "abort_no_reading"})
    result = decision_node(s)
    assert result["next_node"] == "end"
    assert result["diagnosis_complete"] is True
    assert result["diagnosis_status"] == "aborted_no_reading"


def test_all_hypotheses_eliminated_ends_inconclusive():
    s = _state(eliminated_faults=["H1", "H2"])
    result = decision_node(s)
    assert result["next_node"] == "end"
    assert result["diagnosis_status"] == "inconclusive"
    assert any(isinstance(m, AIMessage) for m in result["messages"])


def test_max_steps_reached_ends():
    s = _state(current_step=10, max_steps=10)
    result = decision_node(s)
    assert result["next_node"] == "end"
    assert result["diagnosis_status"] == "max_steps_reached"


def test_exhausted_rankings_with_dominant_hypothesis_triggers_repair():
    # current_step beyond rankings + probability ≥ 0.85 → high-confidence repair
    s = _state(
        current_step=3,
        rankings=["tp1", "tp2", "tp3"],
        probs={"H1": 0.9, "H2": 0.1},
    )
    result = decision_node(s)
    assert result["next_node"] == "repair"
    assert result["current_hypothesis"] == "H1"
    assert result["diagnosis_status"] == "confirmed_by_probability"


def test_exhausted_rankings_without_dominant_hypothesis_ends():
    s = _state(current_step=3, rankings=["tp1", "tp2", "tp3"], probs={"H1": 0.5, "H2": 0.5})
    result = decision_node(s)
    assert result["next_node"] == "end"
    assert result["diagnosis_status"] == "no_more_tests"


def test_default_path_continues_to_interrupt():
    s = _state(current_step=1, rankings=["tp1", "tp2", "tp3"])
    assert decision_node(s) == {"next_node": "interrupt"}
