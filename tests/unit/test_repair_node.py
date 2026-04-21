"""Unit tests for the ``repair`` node."""

from src.graph.nodes.repair import repair_node


def test_emits_confirmed_fault_and_recovery_steps(base_state):
    # Mark the fault as confirmed and add a fault measurement.
    base_state.confirmed_fault = "Shorted Primary MOSFET"
    base_state.current_hypothesis = "HYPOTHESIS_1"
    base_state.measurements = [{
        "test_point": "primary_mosfet",
        "signal_name": "Primary MOSFET (Q1)",
        "value": 0.3,
        "unit": "ohm",
        "measurement_type": "CONTINUITY",
        "evaluation": "fault",
    }]

    result = repair_node(base_state)

    assert result["diagnosis_complete"] is True
    assert result["confirmed_fault"] == "Shorted Primary MOSFET"
    content = result["messages"][0].content
    assert "Repair Procedure" in content
    assert "Replace Q1" in content              # recovery step action
    assert "Desolder Q1" in content             # recovery step instruction
    assert "primary_mosfet" in content or "Primary MOSFET" in content


def test_evidence_table_uses_ol_display_for_continuity_sentinel(base_state):
    base_state.confirmed_fault = "Open D3"
    base_state.current_hypothesis = "HYPOTHESIS_1"
    base_state.measurements = [{
        "test_point": "primary_mosfet",
        "signal_name": "Primary MOSFET (Q1)",
        "value": 999_999.0,  # OL sentinel
        "unit": "ohm",
        "measurement_type": "CONTINUITY",
        "evaluation": "fault",
    }]

    content = repair_node(base_state)["messages"][0].content
    assert "OL (open)" in content


def test_post_repair_verification_mentions_output_voltage(base_state):
    base_state.confirmed_fault = "Shorted Q1"
    base_state.current_hypothesis = "HYPOTHESIS_1"
    base_state.measurements = []

    content = repair_node(base_state)["messages"][0].content
    assert "Post-repair verification" in content
    # Falls back to generic message when no expected range configured for output
    assert "Output Voltage" in content or "output" in content.lower()
