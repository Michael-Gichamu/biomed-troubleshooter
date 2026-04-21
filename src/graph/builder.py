"""Graph construction and the LangGraph Studio factory entry point."""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.studio.tools import get_tools  # noqa -- keeps tool registration alive
from src.graph.state import ConversationalAgentState
from src.graph.nodes import (
    rag_node,
    hypotheses_node,
    instruction_node,
    probe_wait_node,
    step_node,
    reason_node,
    decision_node,
    repair_node,
    interrupt_node,
    resume_node,
)
from src.graph.routing import route_from_decision, route_from_resume


def create_conversational_graph():
    """Build and compile the hypothesis-driven diagnostic workflow.

    Flow:
      START → rag → hypotheses → instruction → probe_wait → step → reason → decision
                                      ↑                                         |
                                      ←────────── resume ← interrupt ───────────┘  (if no fault)
      decision → repair → END
      decision → END  (inconclusive / max steps / exhausted)
    """
    builder = StateGraph(ConversationalAgentState)

    builder.add_node("rag",         rag_node)
    builder.add_node("hypotheses",  hypotheses_node)
    builder.add_node("instruction", instruction_node)
    builder.add_node("step",        step_node)
    builder.add_node("reason",      reason_node)
    builder.add_node("decision",    decision_node)
    builder.add_node("repair",      repair_node)
    builder.add_node("interrupt",   interrupt_node)
    builder.add_node("resume",      resume_node)
    builder.add_node("probe_wait",  probe_wait_node)

    builder.add_edge(START,        "rag")
    builder.add_edge("rag",        "hypotheses")
    builder.add_edge("hypotheses",  "instruction")
    builder.add_edge("instruction", "probe_wait")
    builder.add_edge("probe_wait",  "step")
    builder.add_edge("step",       "reason")
    builder.add_edge("reason",     "decision")

    builder.add_conditional_edges(
        "decision",
        route_from_decision,
        {"repair": "repair", "interrupt": "interrupt", "end": END, "instruction": "instruction"}
    )

    builder.add_edge("interrupt", "resume")

    builder.add_conditional_edges(
        "resume",
        route_from_resume,
        {"instruction": "instruction", "end": END}
    )

    builder.add_edge("repair", END)

    return builder.compile(checkpointer=MemorySaver())


def graph():
    """Return the compiled graph for LangGraph Studio.

    Also fires a fire-and-forget background thread that pre-warms:
      1. The Groq LLM (first API call is slow on a cold server cache)
      2. The SentenceTransformer embedding model (40–70 s cold-start)

    By the time the engineer types their first message the warm-up is
    already underway (or complete), cutting initialisation from 60–90 s
    down to 2–5 s.
    """
    import threading

    def _prewarm():
        try:
            from src.infrastructure.llm_manager import get_llm_manager
            mgr = get_llm_manager()
            mgr.current_llm.invoke([{"role": "user", "content": "hi"}])
            print("[PREWARM] LLM warm-up complete.")
        except Exception as exc:
            print(f"[PREWARM] LLM warm-up skipped: {exc}")

        try:
            from src.infrastructure.chromadb_client import _get_embedding_function
            _get_embedding_function()
            print("[PREWARM] Embedding model warm-up complete.")
        except Exception as exc:
            print(f"[PREWARM] Embedding warm-up skipped: {exc}")

    t = threading.Thread(target=_prewarm, daemon=True, name="startup-prewarm")
    t.start()

    return create_conversational_graph()
