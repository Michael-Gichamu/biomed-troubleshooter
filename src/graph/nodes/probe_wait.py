"""Probe-wait node — pause AFTER probe instructions and BEFORE measurement fires."""

from langgraph.types import interrupt

from src.graph.helpers import _parse_manual_reading
from src.graph.state import ConversationalAgentState


def probe_wait_node(state: ConversationalAgentState) -> dict:
    """Pause after probe placement instructions are shown so the engineer can
    read the instructions and place the probes before the measurement starts.

    instruction_node already emitted all the probe details and the image.
    This node calls interrupt() so LangGraph Studio renders that message and
    shows the Resume button. When the engineer presses Resume (or types a
    manual reading and presses Enter), probe_wait_node captures the resume
    value, parses it as a manual reading if possible, and stores it in state
    so step_node can use it instead of the USB reader.
    """
    resume_value = interrupt("probes_ready")
    manual = _parse_manual_reading(resume_value)
    return {"pending_manual_reading": manual}
