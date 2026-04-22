"""Unit tests for the ``hypotheses`` node with the LLM mocked."""

import json

import pytest
from langchain_core.messages import HumanMessage

from src.graph.nodes.hypotheses import _extract_confirmed_findings, hypotheses_node
from src.graph.state import ConversationalAgentState


class TestExtractConfirmedFindings:
    def test_detects_confirmed_ok_phrase(self):
        tps = [{"signal_id": "input_fuse", "name": "Input Fuse"}]
        out = _extract_confirmed_findings("input_fuse is okay and intact", tps)
        assert "CONFIRMED WORKING" in out
        assert "input_fuse" in out

    def test_detects_already_replaced(self):
        tps = [{"signal_id": "primary_mosfet", "name": "MOSFET Q1"}]
        out = _extract_confirmed_findings("I already replaced primary_mosfet", tps)
        assert "ALREADY REPLACED" in out

    def test_detects_catastrophic_failure(self):
        tps = []
        out = _extract_confirmed_findings("the fuse blew again", tps)
        assert "CATASTROPHIC FAILURE" in out

    def test_returns_none_extracted_for_benign_symptom(self):
        tps = [{"signal_id": "x", "name": "X"}]
        assert _extract_confirmed_findings("strange noise from the unit", tps) == "None extracted"


class TestHypothesesNode:
    @pytest.fixture
    def seed_state(self, sample_equipment_config):
        return ConversationalAgentState(
            messages=[HumanMessage(content="no output, fuse blew again")],
            equipment_model="test-psu-v1",
            equipment_config=sample_equipment_config,
            test_points=sample_equipment_config["signals"],
            suspected_faults=sample_equipment_config["faults"],
            rag_knowledge=[{"content": "Q1 failure is the #1 cause of blown fuses"}],
        )

    def test_llm_json_is_parsed_into_state(self, seed_state, mock_llm):
        canned = json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "HYPOTHESIS_1",
                        "fault_id": "F001",
                        "description": "Q1 short",
                        "probability": 0.8,
                    },
                    {
                        "id": "HYPOTHESIS_2",
                        "fault_id": "",
                        "description": "Startup issue",
                        "probability": 0.2,
                    },
                ],
                "test_point_rankings": ["primary_mosfet", "output_voltage"],
            }
        )
        mock_llm(canned)

        result = hypotheses_node(seed_state)

        assert len(result["hypotheses"]) == 2
        assert result["hypotheses"][0]["id"] == "HYPOTHESIS_1"
        assert result["test_point_rankings"] == ["primary_mosfet", "output_voltage"]
        assert result["current_hypothesis"] == "HYPOTHESIS_1"
        # Probabilities should be normalised to sum to 1.0 (already do here)
        assert abs(sum(result["hypothesis_probabilities"].values()) - 1.0) < 1e-6

    def test_invalid_signal_ids_are_filtered_out(self, seed_state, mock_llm):
        # LLM returns a bogus signal_id → must fall back to the valid set
        mock_llm(
            json.dumps(
                {
                    "hypotheses": [{"id": "H1", "description": "x", "probability": 1.0}],
                    "test_point_rankings": ["primary_mosfet", "does_not_exist", "output_voltage"],
                }
            )
        )
        result = hypotheses_node(seed_state)
        assert "does_not_exist" not in result["test_point_rankings"]
        assert set(result["test_point_rankings"]) <= {"primary_mosfet", "output_voltage"}

    def test_llm_failure_falls_back_to_faults_list(self, seed_state, mock_llm):
        mock_llm("NOT JSON AT ALL")
        result = hypotheses_node(seed_state)
        # Fallback path populates from suspected_faults; must still produce rankings
        assert result["test_point_rankings"]  # non-empty
        assert result["current_step"] == 0
