"""Interrupt node — pause ONLY (no probe info) after a full step cycle.

Filename uses a trailing underscore to avoid shadowing :func:`langgraph.types.interrupt`.
"""

from langgraph.types import interrupt

from src.graph.state import ConversationalAgentState


def interrupt_node(state: ConversationalAgentState):
    """Pause execution after a complete measurement cycle so the engineer can
    review the result before continuing.

    The probe instructions for the NEXT test point will be shown by
    instruction_node after the engineer presses resume — not here.
    """
    interrupt(
        "**Measurement cycle complete.**\n\n"
        "Review the result above, then type anything and press **Enter** "
        "to continue to the next test point."
    )
    return {"waiting_for_next": True}
