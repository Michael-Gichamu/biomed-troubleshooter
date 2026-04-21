"""LangGraph-based diagnostic agent — orchestration package.

Public entry points:
  * :func:`graph` — builds the compiled state graph used by LangGraph Studio
    (referenced from ``langgraph.json``).
  * :class:`ConversationalAgentState` — state schema passed between nodes.
"""

from src.graph.state import ConversationalAgentState, _text
from src.graph.builder import create_conversational_graph, graph

__all__ = [
    "ConversationalAgentState",
    "create_conversational_graph",
    "graph",
    "_text",
]
