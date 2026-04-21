"""FastAPI entry point for Cloud Run deployment.

Endpoints
---------
* ``GET  /healthz``    – readiness probe (no external calls).
* ``GET  /readyz``     – strict readiness: builds the graph on first call.
* ``POST /run-agent``  – run one turn of the diagnostic agent.

Contract
--------
Request JSON::

    {
      "message": "no output voltage on test-psu-v1",
      "equipment_model": "test-psu-v1",     # optional — can live inside message
      "session_id": "user-42-case-7",        # optional — enables multi-turn
      "thread_id": "<same as session_id>",   # optional alias
      "manual_reading": "12.3 V"             # optional — resume after probe_wait
    }

Response JSON::

    {
      "session_id": "...",
      "messages": [{"role": "assistant", "content": "..."}],
      "diagnosis_complete": true,
      "confirmed_fault": "Shorted Primary MOSFET",
      "next_node": null,
      "status": "ok"
    }

LangSmith tracing
-----------------
When ``LANGCHAIN_TRACING_V2=true`` (or the legacy ``LANGCHAIN_TRACING=true``) and
``LANGCHAIN_API_KEY`` are set, every request is automatically traced. The
endpoint adds a ``session_id`` tag to every run so operators can filter by case.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph bootstrap (module-scoped — compiled once per process)
# ---------------------------------------------------------------------------

_graph = None


def _get_graph():
    """Lazy-compile the graph so import time stays fast and unit-testable."""
    global _graph
    if _graph is None:
        from src.graph import create_conversational_graph
        _graph = create_conversational_graph()
        logger.info("LangGraph compiled and ready to serve requests.")
    return _graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the graph and LLM on cold start for faster first request.

    Failures here are non-fatal — the service still boots; the first request
    just pays the latency.
    """
    try:
        _get_graph()
    except Exception as exc:  # pragma: no cover — we don't want to kill the pod
        logger.warning("Graph prewarm failed (will retry on first request): %s", exc)
    yield


app = FastAPI(
    title="Biomedical Equipment Troubleshooter",
    description="LangGraph-backed diagnostic agent for biomedical equipment.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — explicitly configurable; default open so local dev and Cloud Run work
# out-of-the-box. Narrow this in production via API_ALLOWED_ORIGINS.
_origins_env = os.getenv("API_ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RunAgentRequest(BaseModel):
    message: str = Field(
        ...,
        description="User's symptom description or answer to a probe-wait prompt.",
        min_length=1,
        max_length=8000,
    )
    equipment_model: str | None = Field(
        default=None,
        description="Equipment identifier, e.g. 'mastech-ms8250d'. Optional if the "
                    "message mentions one.",
    )
    session_id: str | None = Field(
        default=None,
        description="Stable ID to thread multi-turn sessions. A new one is created "
                    "if omitted.",
    )
    thread_id: str | None = Field(
        default=None,
        description="Alias for session_id (accepted for convenience).",
    )
    manual_reading: str | None = Field(
        default=None,
        description="Raw multimeter reading when resuming after a probe-wait.",
    )


class AssistantMessage(BaseModel):
    role: str = "assistant"
    content: str


class RunAgentResponse(BaseModel):
    session_id: str
    messages: list[AssistantMessage]
    diagnosis_complete: bool = False
    confirmed_fault: str | None = None
    next_node: str | None = None
    status: str = "ok"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_assistant_messages(graph_output: dict[str, Any]) -> list[AssistantMessage]:
    """Pull out the assistant-visible messages from the graph's final state."""
    raw: list[BaseMessage] = graph_output.get("messages", []) or []
    out: list[AssistantMessage] = []
    for msg in raw:
        if isinstance(msg, AIMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            out.append(AssistantMessage(role="assistant", content=content))
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/healthz")
def healthz():
    """Liveness probe — returns 200 as long as the process is up."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness probe — ensures the graph compiles."""
    try:
        _get_graph()
        return {"status": "ready"}
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail=f"not ready: {exc}") from exc


@app.post("/run-agent", response_model=RunAgentResponse)
def run_agent(req: RunAgentRequest):
    """Run one turn of the diagnostic agent.

    Stateless-by-default: if you omit ``session_id`` we generate one. Supply the
    same ID on follow-up requests to preserve LangGraph checkpointer state
    (hypotheses, measurements, current_step, etc.).
    """
    session_id = req.session_id or req.thread_id or f"session-{uuid.uuid4().hex[:12]}"

    # Every trace emitted for this request carries the session_id tag — filter
    # by it in LangSmith to reconstruct a full case history.
    config = {
        "configurable": {"thread_id": session_id},
        "tags": [f"session:{session_id}"],
        "metadata": {"session_id": session_id},
    }

    # Compose the input message. Equipment model is passed in the state so
    # rag_node can skip the LLM-based extraction step when the caller knows it.
    graph_input: dict[str, Any] = {
        "messages": [HumanMessage(content=req.message)],
    }
    if req.equipment_model:
        graph_input["equipment_model"] = req.equipment_model
    if req.manual_reading is not None:
        graph_input["pending_manual_reading"] = req.manual_reading

    try:
        graph = _get_graph()
        result = graph.invoke(graph_input, config=config)
    except Exception as exc:
        logger.exception("Agent invocation failed for session %s", session_id)
        raise HTTPException(status_code=500, detail=f"agent error: {exc}") from exc

    messages = _extract_assistant_messages(result)
    if not messages:
        # Fallback: surface whatever terminal content we have so callers aren't
        # left with an empty body.
        messages = [AssistantMessage(role="assistant", content="(no assistant output)")]

    return RunAgentResponse(
        session_id=session_id,
        messages=messages,
        diagnosis_complete=bool(result.get("diagnosis_complete", False)),
        confirmed_fault=result.get("confirmed_fault"),
        next_node=result.get("next_node"),
        status="ok",
    )


# ---------------------------------------------------------------------------
# Local dev entry point — `python -m src.api.main`
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
