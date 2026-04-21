"""Decision node — deterministic routing based on diagnosis state."""

from langchain_core.messages import AIMessage

from src.graph.state import ConversationalAgentState


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


def decision_node(state: ConversationalAgentState):
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
        return {"next_node": "instruction"}   # re-show same test point; current_step unchanged

    if decision == "abort_no_reading":
        return {
            "next_node": "end",
            "diagnosis_complete": True,
            "diagnosis_status": "aborted_no_reading",
        }

    if decision == "fault_confirmed":
        return {"next_node": "repair"}

    active = [h for h in state.hypotheses if h.get("id") not in state.eliminated_faults]
    if not active:
        return {
            "next_node": "end",
            "diagnosis_status": "inconclusive",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=(
                "## Diagnosis Complete -- Inconclusive\n\n"
                "All fault hypotheses have been eliminated by measurements. "
                "The fault may lie outside the modelled failure modes. "
                "Consider a visual inspection or component-level tests."
            ))]
        }

    if state.current_step >= state.max_steps:
        return {
            "next_node": "end",
            "diagnosis_status": "max_steps_reached",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=(
                f"## Diagnosis Complete -- Step Limit Reached\n\n"
                f"Completed {state.max_steps} diagnostic steps without a conclusive result. "
                f"Most likely candidate: **{_top_hypothesis_desc(state)}**."
            ))]
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
                "messages": [AIMessage(content=(
                    f"## Diagnosis Complete — High Confidence\n\n"
                    f"All planned tests exhausted. "
                    f"**{_top_hypothesis_desc(state)}** confirmed at {best_prob:.0%} probability. "
                    f"Proceeding to repair."
                ))]
            }

        return {
            "next_node": "end",
            "diagnosis_status": "no_more_tests",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=(
                "## Diagnosis Complete — All Tests Exhausted\n\n"
                "No further test points available and no dominant hypothesis. "
                f"Most likely candidate: **{_top_hypothesis_desc(state)}**."
            ))]
        }

    return {"next_node": "interrupt"}
