"""Decision node — deterministic routing based on diagnosis state."""

import logging

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.graph.state import ConversationalAgentState

logger = logging.getLogger(__name__)


# Map diagnosis_status → diagnostic_cases.outcome enum.
_OUTCOME_MAP = {
    "aborted_no_reading": "exhausted",
    "inconclusive": "inconclusive",
    "max_steps_reached": "max_steps",
    "no_more_tests": "exhausted",
    "confirmed_by_probability": "resolved",
}


def _record_terminal_case(
    state: ConversationalAgentState,
    config: RunnableConfig | None,
    outcome: str,
    final_diagnosis: str | None = None,
) -> None:
    """Fire-and-forget case write; swallows errors to protect the graph."""
    try:
        from src.infrastructure.db.cases_repository import case_from_state, record_case

        thread_id = ""
        if config and isinstance(config, dict):
            thread_id = (config.get("configurable") or {}).get("thread_id", "") or ""
        record = case_from_state(
            state,
            thread_id=thread_id,
            outcome=outcome,
            final_diagnosis=final_diagnosis,
        )
        record_case(record)
    except Exception:
        logger.debug("record_case skipped due to error", exc_info=True)


def _top_hypothesis_desc(state: ConversationalAgentState) -> str:
    """Return the description of the highest-probability non-eliminated hypothesis."""
    best_desc, best_prob = "Unknown", -1.0
    for h in state.hypotheses:
        h_id = h.get("id", "")
        if h_id not in state.eliminated_faults:
            p = state.hypothesis_probabilities.get(h_id, 0)
            if p > best_prob:
                best_prob, best_desc = p, h.get("description", h_id)
    return best_desc


def decision_node(state: ConversationalAgentState, config: RunnableConfig | None = None):
    """Evaluate termination conditions in order and set ``state.next_node``.

    1. confirmed_fault already set → repair
    2. step_result.decision == "fault_confirmed" → repair
    3. All hypotheses eliminated → END (inconclusive)
    4. current_step ≥ max_steps → END (max reached)
    5. current_step ≥ len(rankings) → END (no more tests)
    6. Otherwise → interrupt (continue loop)
    """
    if state.confirmed_fault:
        return {"next_node": "repair"}

    decision = state.step_result.get("decision", "continue_diagnosis")

    if decision == "retry_probe":
        return {"next_node": "instruction"}  # re-show same test point; current_step unchanged

    if decision == "abort_no_reading":
        _record_terminal_case(state, config, outcome=_OUTCOME_MAP["aborted_no_reading"])
        return {
            "next_node": "end",
            "diagnosis_complete": True,
            "diagnosis_status": "aborted_no_reading",
        }

    if decision == "fault_confirmed":
        return {"next_node": "repair"}

    active = [h for h in state.hypotheses if h.get("id") not in state.eliminated_faults]
    if not active:
        _record_terminal_case(state, config, outcome=_OUTCOME_MAP["inconclusive"])
        return {
            "next_node": "end",
            "diagnosis_status": "inconclusive",
            "diagnosis_complete": True,
            "messages": [
                AIMessage(
                    content=(
                        "## Diagnosis Complete -- Inconclusive\n\n"
                        "All fault hypotheses have been eliminated by measurements. "
                        "The fault may lie outside the modelled failure modes. "
                        "Consider a visual inspection or component-level tests."
                    )
                )
            ],
        }

    if state.current_step >= state.max_steps:
        _record_terminal_case(
            state,
            config,
            outcome=_OUTCOME_MAP["max_steps_reached"],
            final_diagnosis=_top_hypothesis_desc(state),
        )
        return {
            "next_node": "end",
            "diagnosis_status": "max_steps_reached",
            "diagnosis_complete": True,
            "messages": [
                AIMessage(
                    content=(
                        f"## Diagnosis Complete -- Step Limit Reached\n\n"
                        f"Completed {state.max_steps} diagnostic steps without a conclusive result. "
                        f"Most likely candidate: **{_top_hypothesis_desc(state)}**."
                    )
                )
            ],
        }

    if state.current_step >= len(state.test_point_rankings):
        best_id, best_prob = "", -1.0
        for h in state.hypotheses:
            h_id = h.get("id", "")
            if h_id not in state.eliminated_faults:
                p = state.hypothesis_probabilities.get(h_id, 0)
                if p > best_prob:
                    best_prob, best_id = p, h_id

        if best_prob >= 0.85 and best_id:
            return {
                "next_node": "repair",
                "current_hypothesis": best_id,
                "diagnosis_status": "confirmed_by_probability",
                "messages": [
                    AIMessage(
                        content=(
                            f"## Diagnosis Complete — High Confidence\n\n"
                            f"All planned tests exhausted. "
                            f"**{_top_hypothesis_desc(state)}** confirmed at {best_prob:.0%} probability. "
                            f"Proceeding to repair."
                        )
                    )
                ],
            }

        _record_terminal_case(
            state,
            config,
            outcome=_OUTCOME_MAP["no_more_tests"],
            final_diagnosis=_top_hypothesis_desc(state),
        )
        return {
            "next_node": "end",
            "diagnosis_status": "no_more_tests",
            "diagnosis_complete": True,
            "messages": [
                AIMessage(
                    content=(
                        "## Diagnosis Complete — All Tests Exhausted\n\n"
                        "No further test points available and no dominant hypothesis. "
                        f"Most likely candidate: **{_top_hypothesis_desc(state)}**."
                    )
                )
            ],
        }

    return {"next_node": "interrupt"}
