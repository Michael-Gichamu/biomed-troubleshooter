"""State schema and small helpers shared by every node."""

from dataclasses import dataclass, field
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.infrastructure.input_sanitizer import normalise_user_text


def _text(content) -> str:
    """Extract plain text from a string or a LangGraph content-block list.

    Output is run through :func:`normalise_user_text` so downstream prompts and
    logs never see control chars, non-normalised Unicode, or oversized inputs.
    """
    if isinstance(content, str):
        raw = content
    elif isinstance(content, list):
        raw = " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    else:
        raw = ""
    return normalise_user_text(raw)


@dataclass
class ConversationalAgentState:
    """All state for the hypothesis-driven diagnostic workflow.

    Populated in ``rag_node`` once and carried forward. Nodes return dicts with
    only the keys they change — LangGraph merges them into state.
    """

    # ── Messaging ────────────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)

    # ── Equipment (set in rag_node, never mutated again) ─────────────────────
    equipment_model: str = ""
    config_cached: bool = False
    equipment_config: dict = field(default_factory=dict)
    # test_points: basic list from "all" config → used for LLM prompts
    test_points: list = field(default_factory=list)
    # expected_values: {signal_id: {min, max, unit, description}}
    expected_values: dict = field(default_factory=dict)

    # ── RAG knowledge ────────────────────────────────────────────────────────
    rag_knowledge: list = field(default_factory=list)

    # ── Hypothesis tracking ──────────────────────────────────────────────────
    hypotheses: list = field(default_factory=list)
    hypothesis_probabilities: dict = field(default_factory=dict)
    eliminated_faults: list = field(default_factory=list)
    current_hypothesis: str = ""
    test_point_rankings: list = field(default_factory=list)
    diagnostic_reasoning: list = field(default_factory=list)

    # ── Diagnostic plan (kept for routing logic) ─────────────────────────────
    diagnostic_plan: list = field(default_factory=list)
    current_step: int = 0  # index into test_point_rankings
    completed_steps: list = field(default_factory=list)

    # ── Measurements & faults ────────────────────────────────────────────────
    measurements: list = field(default_factory=list)
    suspected_faults: list = field(default_factory=list)
    confirmed_fault: str = ""

    # ── Step execution state ─────────────────────────────────────────────────
    next_test_point: str = ""
    current_test_point: str = ""
    step_result: dict = field(default_factory=dict)

    # ── Control flags ────────────────────────────────────────────────────────
    waiting_for_next: bool = False
    diagnosis_complete: bool = False
    diagnosis_status: str = ""

    # ── Safety limits ────────────────────────────────────────────────────────
    iteration_count: int = 0
    max_steps: int = 9

    # ── Measurement failure tracking ─────────────────────────────────────────
    consecutive_failures: int = 0  # resets to 0 on any successful/fault reading

    # ── Manual reading entered by engineer at probe interrupt ────────────────
    pending_manual_reading: dict | None = None

    # ── Routing (set by decision_node) ───────────────────────────────────────
    next_node: str = ""
