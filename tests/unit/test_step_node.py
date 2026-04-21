"""Unit tests for the ``step`` node with the multimeter tool mocked."""

from src.graph.nodes.step import step_node


def test_success_reading_evaluates_as_fault_when_out_of_range(base_state, mock_multimeter):
    # primary_mosfet expects 50–999999 ohm. Zero = shorted → FAULT.
    mock_multimeter({
        "status": "success",
        "value": 0.3,
        "unit": "ohm",
        "measurement_type": "CONTINUITY",
        "test_point": "primary_mosfet",
    })
    base_state.current_step = 0

    result = step_node(base_state)

    rec = result["step_result"]["measurement"]
    assert rec["evaluation"] == "fault"
    assert rec["test_point"] == "primary_mosfet"
    assert result["current_test_point"] == "primary_mosfet"
    # Measurement appended to history
    assert result["measurements"][-1]["value"] == 0.3


def test_success_reading_within_range_is_normal(base_state, mock_multimeter):
    mock_multimeter({
        "status": "success",
        "value": 12.1,
        "unit": "V",
        "measurement_type": "DC_VOLTAGE",
        "test_point": "output_voltage",
    })
    base_state.current_step = 1

    result = step_node(base_state)

    assert result["step_result"]["measurement"]["evaluation"] == "normal"


def test_timeout_marks_measurement_unavailable(base_state, mock_multimeter):
    mock_multimeter({
        "status": "timeout",
        "value": None,
        "message": "no stable reading",
        "test_point": "primary_mosfet",
    })
    base_state.current_step = 0

    result = step_node(base_state)
    assert result["step_result"]["measurement"]["evaluation"] == "measurement_unavailable"


def test_manual_reading_overrides_multimeter(base_state, mock_multimeter):
    """If pending_manual_reading is present, the USB path must not be called."""
    # If the USB path IS called it returns 999 (out of range) — so a manual
    # "normal" value confirms we took the manual branch.
    mock_multimeter({"status": "success", "value": 999.0, "unit": "V",
                     "test_point": "output_voltage"})
    base_state.current_step = 1
    base_state.pending_manual_reading = {
        "value": 12.0, "unit": "V", "measurement_type": "manual"
    }

    result = step_node(base_state)

    rec = result["step_result"]["measurement"]
    assert rec["value"] == 12.0  # manual took precedence
    assert result["pending_manual_reading"] is None  # consumed


def test_no_more_test_points_returns_early(base_state, mock_multimeter):
    base_state.current_step = len(base_state.test_point_rankings)  # past end

    result = step_node(base_state)
    assert result["step_result"]["decision"] == "no_more_tests"
