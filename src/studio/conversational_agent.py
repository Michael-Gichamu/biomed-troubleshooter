"""Backward-compatible re-export shim.

The diagnostic graph has moved to :mod:`src.graph`. This module stays in place
so that ``langgraph.json``, historical imports, and third-party tooling that
referenced ``src.studio.conversational_agent:graph`` keep working.

Prefer importing from :mod:`src.graph` in new code.
"""

from dotenv import load_dotenv

load_dotenv()

from src.graph import ConversationalAgentState, _text, create_conversational_graph, graph
from src.graph.helpers import _parse_manual_reading
from src.graph.nodes import (
    decision_node,
    hypotheses_node,
    instruction_node,
    interrupt_node,
    probe_wait_node,
    rag_node,
    reason_node,
    repair_node,
    resume_node,
    step_node,
)
from src.graph.routing import route_from_decision, route_from_resume

__all__ = [
    "ConversationalAgentState",
    "_text",
    "_parse_manual_reading",
    "create_conversational_graph",
    "graph",
    "route_from_decision",
    "route_from_resume",
    "rag_node",
    "hypotheses_node",
    "instruction_node",
    "probe_wait_node",
    "step_node",
    "reason_node",
    "decision_node",
    "repair_node",
    "interrupt_node",
    "resume_node",
]
