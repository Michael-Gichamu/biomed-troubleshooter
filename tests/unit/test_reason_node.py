"""Unit tests for the ``reason`` node with the LLM mocked."""

import json

from src.graph.nodes.reason import reason_node


def _with_last_measurement(state, *, test_point, value, evaluation):
    state.measurements = state.measurements + [{
        "test_point": test_point,
        "signal_name": test_point,
        "value": value,
        "unit": "ohm" if evaluation == "fault" else "V",
        "evaluation": evaluation,
        "status": "success",
    }]
    return state


def test_measurement_unavailable_first_failure_triggers_retry(base_state):
    state = _with_last_measurement(
        base_state, test_point="primary_mosfet", value=None,
        evaluation="measurement_unavailable",
    )
    state.consecutive_failures = 0

    result = reason_node(state)
    assert result["step_result"]["decision"] == "retry_probe"
    assert result["consecutive_failures"] == 1


def test_measurement_unavailable_second_failure_aborts(base_state):
    state = _with_last_measurement(
        base_state, test_point="primary_mosfet", value=None,
        evaluation="measurement_unavailable",
    )
    state.consecutive_failures = 1

    result = reason_node(state)
    assert result["step_result"]["decision"] == "abort_no_reading"
    assert result["diagnosis_complete"] is True


def test_llm_confirmed_hypothesis_bubbles_up(base_state, mock_llm):
    state = _with_last_measurement(
        base_state, test_point="primary_mosfet", value=0.3, evaluation="fault",
    )
    mock_llm(json.dumps({
        "reasoning": "Q1 shorted and D3 also shorted — cascade confirmed.",
        "probability_updates": {"HYPOTHESIS_1": 1.0, "HYPOTHESIS_2": 0.0},
        "eliminated_faults": ["HYPOTHESIS_2"],
        "confirmed_hypothesis": "HYPOTHESIS_1",
        "updated_remaining_test_plan": [],
    }))

    result = reason_node(state)

    assert result["step_result"]["decision"] == "fault_confirmed"
    assert result["current_hypothesis"] == "HYPOTHESIS_1"
    assert "HYPOTHESIS_2" in result["eliminated_faults"]
    assert result["current_step"] == state.current_step + 1


def test_llm_failure_keeps_probabilities_unchanged(base_state, mock_llm):
    state = _with_last_measurement(
        base_state, test_point="primary_mosfet", value=500, evaluation="normal",
    )
    mock_llm("not a json response")

    result = reason_node(state)
    # Probabilities carried forward unchanged (no-op reasoning)
    # Values are re-normalised; verify the RATIO is preserved (approximately).
    probs = result["hypothesis_probabilities"]
    assert abs(probs["HYPOTHESIS_1"] - 0.7) < 1e-6
    assert abs(probs["HYPOTHESIS_2"] - 0.3) < 1e-6
    assert result["step_result"]["decision"] == "continue_diagnosis"


def test_all_eliminated_decision(base_state, mock_llm):
    state = _with_last_measurement(
        base_state, test_point="primary_mosfet", value=500, evaluation="normal",
    )
    mock_llm(json.dumps({
        "reasoning": "Both ruled out.",
        "probability_updates": {"HYPOTHESIS_1": 0.0, "HYPOTHESIS_2": 0.0},
        "eliminated_faults": ["HYPOTHESIS_1", "HYPOTHESIS_2"],
        "confirmed_hypothesis": None,
        "updated_remaining_test_plan": [],
    }))

    result = reason_node(state)
    assert result["step_result"]["decision"] == "all_eliminated"
