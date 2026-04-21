"""Resume node — clear the waiting flag after the engineer confirms continuation."""

from src.graph.state import ConversationalAgentState


def resume_node(state: ConversationalAgentState):
    """Clear the waiting flag. current_step is NOT changed here — it was
    already incremented by reason_node. step_node reads current_step as-is
    and measures test_point_rankings[current_step].
    """
    return {"waiting_for_next": False}
