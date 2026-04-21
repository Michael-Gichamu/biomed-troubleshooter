"""Unit tests for the simple control-flow nodes: instruction, probe_wait, resume."""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage

from src.graph.nodes.instruction import instruction_node
from src.graph.nodes.resume import resume_node


class TestResumeNode:
    def test_clears_waiting_flag(self, base_state):
        base_state.waiting_for_next = True
        assert resume_node(base_state) == {"waiting_for_next": False}


class TestInstructionNode:
    def test_emits_probe_placement_for_current_step(self, base_state):
        base_state.current_step = 0  # → primary_mosfet
        result = instruction_node(base_state)
        assert "messages" in result
        assert len(result["messages"]) == 1
        content = result["messages"][0].content
        assert "Primary MOSFET" in content
        assert "Black probe to source" in content
        assert "TO-220 package" in content
        assert "https://example.com/q1.png" in content

    def test_mentions_safety_warning_when_present(self, base_state):
        base_state.current_step = 0
        content = instruction_node(base_state)["messages"][0].content
        assert "Discharge caps first" in content

    def test_voltage_hint_for_voltage_test_point(self, base_state):
        base_state.current_step = 1  # → output_voltage (voltage_dc)
        content = instruction_node(base_state)["messages"][0].content
        assert "280 V DC" in content or "V DC" in content  # numeric hint

    def test_continuity_hint_mentions_beep(self, base_state):
        base_state.current_step = 0  # → primary_mosfet (continuity)
        content = instruction_node(base_state)["messages"][0].content
        assert "beep" in content.lower()

    def test_completion_message_when_no_more_steps(self, base_state):
        base_state.current_step = len(base_state.test_point_rankings)
        content = instruction_node(base_state)["messages"][0].content
        assert "complete" in content.lower()


class TestProbeWaitNode:
    def test_parses_numeric_manual_reading(self, base_state):
        """``probe_wait_node`` calls langgraph.types.interrupt which yields back
        the engineer's typed value. We stub it to return a numeric string and
        verify the helper parses it into pending_manual_reading.
        """
        # Import inside the test so the patch target matches the import in
        # probe_wait.py.
        with patch("src.graph.nodes.probe_wait.interrupt", return_value="12.5 V"):
            from src.graph.nodes.probe_wait import probe_wait_node
            result = probe_wait_node(base_state)
        assert result == {
            "pending_manual_reading": {
                "value": 12.5, "unit": "V", "measurement_type": "manual",
            }
        }

    def test_unparseable_resume_yields_none(self, base_state):
        with patch("src.graph.nodes.probe_wait.interrupt", return_value="resume"):
            from src.graph.nodes.probe_wait import probe_wait_node
            assert probe_wait_node(base_state) == {"pending_manual_reading": None}
