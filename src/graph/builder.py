"""Graph construction and the LangGraph Studio factory entry point."""

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

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
from src.graph.state import ConversationalAgentState


def _route_after_rag(state: ConversationalAgentState) -> str:
    """Short-circuit the graph when ``rag_node`` could not bootstrap a session.

    ``rag_node`` emits a clarifying ``AIMessage`` and returns without populating
    ``equipment_config`` in three failure modes:

      * No ``equipment_model`` could be resolved from state or message history.
      * The equipment YAML was not found (``FileNotFoundError``).
      * The YAML loaded but parsing raised an unexpected exception.

    Before this conditional edge existed the graph would still march through
    ``hypotheses → instruction → probe_wait → step → reason → decision`` with
    empty test-points and expected-values, producing several junk AI turns
    before control eventually returned to the user. That was a UX bug — the
    user had already been told to supply the model ID at the ``rag`` step.

    Returning ``"end"`` here terminates the run cleanly after the one
    clarifying message, so the next user turn re-enters ``rag`` with the new
    input.
    """
    if not getattr(state, "equipment_model", None):
        return "end"
    cfg = getattr(state, "equipment_config", None) or {}
    if cfg.get("error") or not cfg.get("test_points"):
        return "end"
    return "continue"
from src.infrastructure.config import get_database_config
from src.studio.tools import get_tools  # noqa -- keeps tool registration alive

logger = logging.getLogger(__name__)


def _make_checkpointer() -> Any:
    """Pick a checkpointer backend based on configuration.

    Returns a ``PostgresSaver`` when ``DATABASE_URL`` is set — this is what we
    want in Cloud Run where replicas rotate and in-process dicts evaporate.
    Falls back to ``MemorySaver`` otherwise, which keeps LangGraph Studio,
    unit tests, and zero-infra local dev loops fast and dependency-free.

    The Postgres saver builds its own ``psycopg`` connection pool; we deliberately
    don't share the SQLAlchemy engine here because LangGraph's saver has its own
    lifecycle (``.setup()`` to create tables on first use) and its own
    transaction semantics that don't line up cleanly with SQLAlchemy sessions.
    """
    cfg = get_database_config()
    if not cfg.is_configured:
        logger.info("No DATABASE_URL — using in-memory MemorySaver checkpointer.")
        return MemorySaver()

    try:
        # Import lazily so the memory-only path doesn't require the package
        # to be installed (useful for LangGraph Studio & editable dev installs).
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool
    except ImportError as exc:  # pragma: no cover — install-time configuration issue
        logger.warning(
            "DATABASE_URL is set but langgraph-checkpoint-postgres/psycopg-pool "
            "isn't installed (%s). Falling back to MemorySaver — conversations "
            "WILL NOT persist across replicas.",
            exc,
        )
        return MemorySaver()

    # kwargs matching langgraph-checkpoint-postgres >= 2.0 expectations.
    # Cloud Run workers stay warm for a while but can idle; pre-ping avoids
    # serving a request on a half-closed socket.
    pool = ConnectionPool(
        conninfo=cfg.url,
        min_size=1,
        max_size=max(cfg.pool_size, 2),
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=True,
    )
    saver = PostgresSaver(pool)
    saver.setup()  # idempotent — CREATE TABLE IF NOT EXISTS for checkpoint tables
    logger.info("PostgresSaver checkpointer ready (pool min=1 max=%d).", max(cfg.pool_size, 2))
    return saver


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

    builder.add_node("rag", rag_node)
    builder.add_node("hypotheses", hypotheses_node)
    builder.add_node("instruction", instruction_node)
    builder.add_node("step", step_node)
    builder.add_node("reason", reason_node)
    builder.add_node("decision", decision_node)
    builder.add_node("repair", repair_node)
    builder.add_node("interrupt", interrupt_node)
    builder.add_node("resume", resume_node)
    builder.add_node("probe_wait", probe_wait_node)

    builder.add_edge(START, "rag")
    # Short-circuit to END when rag couldn't resolve an equipment_model or the
    # equipment config failed to load. Without this edge, five downstream nodes
    # would execute against empty state before the user saw a response.
    builder.add_conditional_edges(
        "rag",
        _route_after_rag,
        {"continue": "hypotheses", "end": END},
    )
    builder.add_edge("hypotheses", "instruction")
    builder.add_edge("instruction", "probe_wait")
    builder.add_edge("probe_wait", "step")
    builder.add_edge("step", "reason")
    builder.add_edge("reason", "decision")

    builder.add_conditional_edges(
        "decision",
        route_from_decision,
        {"repair": "repair", "interrupt": "interrupt", "end": END, "instruction": "instruction"},
    )

    builder.add_edge("interrupt", "resume")

    builder.add_conditional_edges(
        "resume", route_from_resume, {"instruction": "instruction", "end": END}
    )

    builder.add_edge("repair", END)

    return builder.compile(checkpointer=_make_checkpointer())


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
