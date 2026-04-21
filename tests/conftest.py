"""Shared pytest fixtures for the biomed-troubleshooter test suite.

Conventions:
  * No test hits a real LLM. :func:`mock_llm` patches
    :func:`src.infrastructure.llm_manager.invoke_with_retry` at every callsite
    the graph nodes import it from.
  * No test opens a real serial port. :func:`mock_multimeter` patches
    :func:`src.studio.tools.read_multimeter.invoke`.
  * Tests run without live API keys — the fixture sets a fake one so that
    :class:`LLMManager` initialisation does not fail during import chains.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.messages import HumanMessage

# Ensure LLMManager initialisation never blows up due to missing env. Tests
# themselves mock out the invoke path, so these values are never used for I/O.
# Force Groq as primary in tests — avoids loading langchain-anthropic and
# keeps the test fleet deterministic regardless of developer .env files.
os.environ["PRIMARY_LLM_PROVIDER"] = "groq"
os.environ["FALLBACK_LLM_PROVIDER"] = "groq"
os.environ.setdefault("GROQ_API_KEYS", "test-key-not-real")
os.environ.setdefault("LLM_MODELS", "llama-3.3-70b-versatile")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key-not-real")

from src.graph.state import ConversationalAgentState  # noqa: E402

# ---------------------------------------------------------------------------
# Equipment fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_equipment_config() -> dict:
    """Minimal but complete equipment_config shaped like what rag_node produces.

    Covers: signals (with probe_placement, image_url), faults with recovery
    steps, signal_dependencies.
    """
    return {
        "metadata": {"equipment_id": "test-psu-v1", "name": "Test PSU"},
        "signals": [
            {
                "signal_id": "primary_mosfet",
                "name": "Primary MOSFET (Q1)",
                "parameter": "continuity",
                "unit": "ohm",
                "diagnostic_meaning": "Q1 drain-source short indicates blown MOSFET",
                "image_url": "https://example.com/q1.png",
                "physical_description": "TO-220 package, heatsinked",
                "pro_tips": ["Power OFF before testing"],
                "safety_warning": "Discharge caps first",
                "probe_placement": "Black probe to source, red to drain",
            },
            {
                "signal_id": "output_voltage",
                "name": "Output Voltage",
                "parameter": "voltage_dc",
                "unit": "V",
                "image_url": "https://example.com/out.png",
                "probe_placement": "Black probe to GND, red to +12V rail",
            },
        ],
        "faults": [
            {
                "fault_id": "F001",
                "name": "Shorted Primary MOSFET",
                "description": "Q1 drain-source shorted",
                "recovery": [
                    {
                        "step": 1,
                        "action": "Replace Q1",
                        "instruction": "Desolder Q1 and replace with equivalent",
                        "verification": "Verify 0 ohm reading is gone",
                        "safety": "Discharge bulk cap",
                        "estimated_time": "15 min",
                    }
                ],
            }
        ],
        "signal_dependencies": [
            {"upstream": "primary_mosfet", "downstream": "output_voltage",
             "relationship": "switch_to_load"},
        ],
    }


@pytest.fixture
def base_state(sample_equipment_config) -> ConversationalAgentState:
    """Minimal conversational state with one user message and config loaded."""
    return ConversationalAgentState(
        messages=[HumanMessage(content="Symptom: no output voltage on test-psu-v1")],
        equipment_model="test-psu-v1",
        config_cached=True,
        equipment_config=sample_equipment_config,
        test_points=sample_equipment_config["signals"],
        suspected_faults=sample_equipment_config["faults"],
        expected_values={
            "primary_mosfet": {"min": 50, "max": 999_999, "unit": "ohm"},
            "output_voltage": {"min": 11.0, "max": 13.0, "unit": "V"},
        },
        test_point_rankings=["primary_mosfet", "output_voltage"],
        hypotheses=[
            {"id": "HYPOTHESIS_1", "fault_id": "F001",
             "description": "Shorted primary MOSFET", "probability": 0.7},
            {"id": "HYPOTHESIS_2", "fault_id": "",
             "description": "Output capacitor ESR high", "probability": 0.3},
        ],
        hypothesis_probabilities={"HYPOTHESIS_1": 0.7, "HYPOTHESIS_2": 0.3},
        current_hypothesis="HYPOTHESIS_1",
    )


# ---------------------------------------------------------------------------
# LLM mocks
# ---------------------------------------------------------------------------

class _FakeLLMResponse:
    """Minimal stand-in for a langchain_core AIMessage-like response."""
    def __init__(self, content: str):
        self.content = content


@pytest.fixture
def llm_stub() -> Callable[[str], Any]:
    """Factory that returns a callable suitable for monkeypatching
    ``invoke_with_retry``. Feed it the canned LLM output string."""
    def _make(content: str) -> Callable[..., Any]:
        return lambda *_args, **_kwargs: _FakeLLMResponse(content)
    return _make


@pytest.fixture
def mock_llm(monkeypatch, llm_stub):
    """Patch :func:`invoke_with_retry` in every module that imports it.

    Usage:
        def test_x(mock_llm):
            mock_llm('{"hypotheses": [...], "test_point_rankings": [...]}')
    """
    def _apply(content: str) -> None:
        stub = llm_stub(content)
        # Patch in every node module that imports invoke_with_retry lazily.
        import src.infrastructure.llm_manager as llm_mod
        monkeypatch.setattr(llm_mod, "invoke_with_retry", stub, raising=True)
    return _apply


# ---------------------------------------------------------------------------
# Hardware mocks
# ---------------------------------------------------------------------------

class _FakeTool:
    """Stand-in for a LangChain StructuredTool.

    LangChain's tool objects are pydantic models, so ``setattr`` on ``invoke``
    is blocked. We substitute the whole tool reference instead.
    """
    def __init__(self, result: dict):
        self._result = result

    def invoke(self, *_args, **_kwargs) -> dict:
        return self._result


@pytest.fixture
def mock_multimeter(monkeypatch):
    """Replace :data:`src.studio.tools.read_multimeter` with a stand-in whose
    ``.invoke()`` returns a canned measurement dict.
    """
    def _apply(result: dict) -> None:
        from src.studio import tools as tools_mod
        monkeypatch.setattr(tools_mod, "read_multimeter", _FakeTool(result),
                            raising=True)
    return _apply
