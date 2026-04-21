# Biomedical Equipment Troubleshooting Agent

A LangGraph-powered AI agent that guides engineers through hypothesis-driven
diagnosis of biomedical equipment faults — from symptom description to a
confirmed root cause and a verified repair plan. Claude Opus is the primary
reasoning engine with Groq as an automatic rate-limit fallback; measurements
come from a Mastech MS8250D digital multimeter over USB, or from simulated
scenarios when hardware is not available.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-green.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [How It Works](#3-how-it-works)
4. [Setup](#4-setup)
5. [Environment Variables](#5-environment-variables)
6. [Running Locally](#6-running-locally)
7. [Testing](#7-testing)
8. [Deployment](#8-deployment)
9. [Observability](#9-observability)
10. [Roadmap](#10-roadmap)

---

## 1. Overview

Biomedical equipment — ventilators, infusion pumps, imaging power supplies —
fails in ways a generic chat model cannot reason about safely. This project
turns an LLM into a structured diagnostician that:

- Asks the engineer for the equipment model and symptom.
- Retrieves the equipment's signal map, fault catalogue, and dependency graph
  from a ChromaDB vector store (RAG).
- Generates a ranked set of fault hypotheses and a minimal sequence of
  multimeter test points to disambiguate between them.
- Streams human-readable probe instructions, reads the multimeter, and updates
  Bayesian probabilities after each measurement.
- Stops as soon as evidence confirms one fault (or all are eliminated).
- Emits a full repair procedure pulled from the equipment's recovery steps,
  with a post-repair verification checklist.

The agent runs behind either a LangGraph Studio UI, a CLI, or a FastAPI HTTP
endpoint (intended for Cloud Run).

### Key capabilities

| Capability | Notes |
|---|---|
| **Hypothesis-driven diagnosis** | Ranked faults + probability updates, not free-form chat |
| **Claude Opus primary** | `claude-opus-4-6` via `langchain-anthropic` |
| **Groq fallback** | Automatic failover on rate limit / 5xx — existing LLM fleet preserved |
| **USB multimeter** | Mastech MS8250D (CP210x bridge) at 2400 baud |
| **Path-safe config loader** | Equipment IDs validated against a strict regex; traversal blocked |
| **Input sanitation** | NFKC normalisation + control-char strip + 8000-char cap |
| **Test suite** | 128 pytest cases (unit + integration, LLM & hardware mocked) |
| **Stateless HTTP API** | FastAPI `/run-agent` with session-id tracing tags |
| **Observability** | LangSmith trace per session_id, emoji-tagged structured logs |

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Interfaces                                         │
│  ┌───────────────┐    ┌──────────────────┐    ┌───────────────────────┐    │
│  │ LangGraph     │    │ CLI              │    │ FastAPI  /run-agent   │    │
│  │ Studio        │    │ (src/interfaces) │    │ (src/api/main.py)     │    │
│  └──────┬────────┘    └────────┬─────────┘    └──────────┬────────────┘    │
└─────────┼──────────────────────┼──────────────────────────┼────────────────┘
          └──────────────────────┴──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │   Compiled LangGraph        │
                  │   (src/graph/builder.py)    │
                  │   + MemorySaver checkpointer│
                  └──────────────┬──────────────┘
                                 │
    ┌────────────────────────────┴──────────────────────────────┐
    │                                                           │
    ▼                                                           ▼
┌─────────────────────┐                           ┌─────────────────────────┐
│  LLMManager         │                           │  Equipment RAG          │
│  (self-healing)     │                           │  ChromaDB + equipment   │
│                     │                           │  configs (YAML/JSON)    │
│  primary: Anthropic │                           │                         │
│  fallback: Groq     │                           │  Path-safe loader       │
│  (→ OpenAI slot)    │                           │                         │
└─────────────────────┘                           └─────────────────────────┘
                                                              │
                                                              ▼
                                                  ┌───────────────────────┐
                                                  │  Hardware / Mock      │
                                                  │  MS8250D read tool    │
                                                  └───────────────────────┘
```

### Project layout

```
src/
├── api/                    # FastAPI HTTP layer (Cloud Run entry point)
│   └── main.py             # POST /run-agent, /healthz, /readyz
├── graph/                  # LangGraph StateGraph — the agent brain
│   ├── state.py            # ConversationalAgentState (dataclass + reducer)
│   ├── builder.py          # create_conversational_graph() + prewarm
│   ├── helpers.py          # _parse_manual_reading, small utilities
│   ├── routing.py          # route_from_decision, route_from_resume
│   └── nodes/              # One file per node (rag, hypotheses, reason, …)
├── infrastructure/         # Cross-cutting concerns
│   ├── llm_manager.py      # Multi-provider self-healing LLM router
│   ├── equipment_config.py # Path-safe YAML loader
│   ├── input_sanitizer.py  # NFKC + control-char defense
│   └── log_parser.py       # Classifies LLM errors as retryable / not
├── studio/                 # LangGraph Studio shim + multimeter tools
├── interfaces/             # CLI / mode router
└── domain/                 # Domain models (outside active graph path)
```

---

## 3. How It Works

### The 10-node state machine

```
 START
   │
   ▼
 ┌──────────┐   load equipment config, build test-point list,
 │  rag     │── pull relevant knowledge via RAG, set expected ranges
 └────┬─────┘
      ▼
 ┌──────────┐   LLM proposes ranked fault hypotheses +
 │hypotheses│── minimal test-point ordering
 └────┬─────┘
      ▼
 ┌───────────┐  emits "Place probes at … and report the reading"
 │instruction│  in natural language with image + safety notes
 └────┬──────┘
      ▼
 ┌──────────┐   pauses the graph; resumes when the user supplies
 │probe_wait│── a `pending_manual_reading` string
 └────┬─────┘
      ▼
 ┌──────────┐   parses "12.3 V", "OL", "short", "healthy",
 │  step    │── classifies normal / fault / measurement_unavailable
 └────┬─────┘
      ▼
 ┌──────────┐   LLM updates probabilities, eliminates faults,
 │  reason  │── optionally confirms a hypothesis
 └────┬─────┘
      ▼
 ┌──────────┐   routes on step_result.decision:
 │ decision │── fault_confirmed → repair
 └────┬─────┘   retry_probe    → interrupt → resume
      │        abort_no_reading → END
      │        all_eliminated   → END
      │        continue_diagnosis → instruction (next test point)
      │
      ├──────────► repair ─────► END       (emits full repair plan)
      └──────────► interrupt ─► resume ─► instruction | END
```

State lives in `ConversationalAgentState` (a `@dataclass`), with
`messages: Annotated[list[BaseMessage], add_messages]` wired to LangGraph's
message reducer — every node that emits a new assistant message appends rather
than replaces.

### Self-healing LLM routing

`src/infrastructure/llm_manager.py` wraps all LLM calls behind
`invoke_with_retry()`. The rotation ladder, when an API call fails with a
retryable error:

1. **Next key** in the current provider (`ANTHROPIC_API_KEYS` can be a
   comma-separated list).
2. **Next model** in the current provider (e.g. fall from `claude-opus-4-6`
   to a cheaper Claude model).
3. **Fallback provider** (Groq, with its own key + model list) — the graph
   keeps running uninterrupted.

Backoff is exponential (1 s, 2 s, 4 s, …, capped at 16 s by default).

### Safety measures

- **Path traversal defence**: equipment IDs are regex-validated
  (`^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$`); resolved paths must live inside the
  configured equipment root.
- **Input sanitation**: every user string is NFKC-normalised, stripped of
  control characters, and capped at 8 000 chars before reaching any prompt.
- **Prompt-override heuristics**: obvious jailbreak patterns are logged.

---

## 4. Setup

### Prerequisites

| Tool | Min version | Install |
|------|-------------|---------|
| Python | 3.10 | https://python.org |
| Git | any | https://git-scm.com |
| Docker (optional, for Cloud Run build) | 24.x | https://docs.docker.com |

### Install

```bash
git clone <repo-url>
cd ai-agent

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
# Dev extras (pytest, black, mypy, ruff):
pip install -e ".[dev]"

cp .env.example .env      # macOS/Linux
copy .env.example .env    # Windows
# …then fill in your keys (see section 5)
```

---

## 5. Environment Variables

Only the two API keys are strictly required. Every other variable has a
sensible default.

### LLM providers

| Variable | Default | Purpose |
|---|---|---|
| `PRIMARY_LLM_PROVIDER` | `anthropic` | `anthropic` / `groq` / `openai` |
| `FALLBACK_LLM_PROVIDER` | `groq` | Second provider tried when primary is exhausted |
| `ANTHROPIC_API_KEY` | — | Single key (or use `ANTHROPIC_API_KEYS` for rotation) |
| `ANTHROPIC_API_KEYS` | — | Comma-separated list for rotation |
| `ANTHROPIC_MODELS` | `claude-opus-4-6` | Comma-separated — falls through on failure |
| `GROQ_API_KEY` / `GROQ_API_KEYS` | — | Groq key(s) |
| `LLM_MODELS` | `llama-3.3-70b-versatile` | Groq models |
| `OPENAI_API_KEY` / `OPENAI_MODELS` | — | Optional third provider slot |

### Retry / rotation tuning

| Variable | Default | Purpose |
|---|---|---|
| `MAX_RETRIES_PER_KEY` | `2` | How many retries against a single key |
| `MAX_RETRIES_PER_MODEL` | `2` | How many retries on a single model |
| `BACKOFF_BASE_SECONDS` | `1.0` | Start of exponential backoff |
| `BACKOFF_MAX_SECONDS` | `16.0` | Backoff cap |

### Hardware / mode

| Variable | Default | Purpose |
|---|---|---|
| `APP_MODE` | `mock` | `mock` \| `usb` |
| `MOCK_SCENARIO` | `cctv-psu-output-rail` | Name of the mock scenario file |
| `USB_PORT` | auto-detect | Override COM port if auto-detect fails |
| `USB_BAUD_RATE` | `2400` | MS8250D fixed baud |
| `USB_TIMEOUT` | `2.0` | Read timeout in seconds |

### RAG / storage

| Variable | Default |
|---|---|
| `EMBEDDING_PROVIDER` | `local` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` |
| `CHROMADB_COLLECTION` | `biomed_equipment` |

### Observability

| Variable | Default | Purpose |
|---|---|---|
| `LANGCHAIN_API_KEY` | — | LangSmith key — trace automatically when set |
| `LANGCHAIN_PROJECT` | `biomed-troubleshooter` | LangSmith project name |
| `LANGCHAIN_TRACING` | `true` | Turn tracing on/off |
| `LOG_LEVEL` | `INFO` | Python logger threshold |

### HTTP API

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Cloud Run injects this automatically |
| `API_ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |

---

## 6. Running Locally

### LangGraph Studio

```bash
langgraph dev
```

Open the URL that LangGraph prints (typically `http://localhost:2024`). The
graph is defined in `langgraph.json`; it points at
`src.graph.builder:graph`, which compiles the workflow and pre-warms the LLM
in a background thread.

### CLI

```bash
python -m src.interfaces.cli
```

### FastAPI HTTP server

```bash
python -m src.api.main
# …or explicitly via uvicorn:
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
```

Smoke test:

```bash
curl http://localhost:8080/healthz
# → {"status":"ok"}

curl -X POST http://localhost:8080/run-agent \
  -H "Content-Type: application/json" \
  -d '{
        "message": "no output voltage on test-psu-v1",
        "equipment_model": "test-psu-v1",
        "session_id": "case-001"
      }'
```

Follow-up turns (providing a measurement) simply re-POST with the same
`session_id` and a `manual_reading` field:

```bash
curl -X POST http://localhost:8080/run-agent \
  -H "Content-Type: application/json" \
  -d '{
        "message": "taken reading",
        "session_id": "case-001",
        "manual_reading": "0.3 ohm"
      }'
```

---

## 7. Testing

```bash
pytest tests/ -ra --strict-markers
```

* **Unit tests** (`tests/unit/`) isolate each node. LLM calls are mocked via
  the `mock_llm` fixture which patches `invoke_with_retry` in place. The
  multimeter is replaced with a `_FakeTool` object.
* **Integration tests** (`tests/integration/`) compile the full graph and
  assert wiring (node set, edges, conditional routes) without hitting any
  external service.

Fixtures live in `tests/conftest.py`. Tests run with the Groq provider pinned
as primary (to avoid importing `langchain-anthropic` on a laptop without the
extra) — in production both providers are available.

Current status: **128 tests, all passing, in ~11 s.**

---

## 8. Deployment

### Docker

```bash
docker build -t biomed-troubleshooter:latest .
docker run --rm -p 8080:8080 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e GROQ_API_KEY=gsk-... \
  -e LANGCHAIN_API_KEY=ls-... \
  biomed-troubleshooter:latest
```

The image is a slim Python 3.12 base, runs as a non-root user, and honours the
platform-injected `PORT`. Health endpoint is `/healthz`.

### Google Cloud Run

```bash
# 1. Build & push
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/$PROJECT/agents/biomed-troubleshooter:latest .
docker push     us-central1-docker.pkg.dev/$PROJECT/agents/biomed-troubleshooter:latest

# 2. Deploy
gcloud run deploy biomed-troubleshooter \
  --image=us-central1-docker.pkg.dev/$PROJECT/agents/biomed-troubleshooter:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --cpu=1 \
  --memory=1Gi \
  --min-instances=0 \
  --max-instances=5 \
  --timeout=300 \
  --concurrency=10 \
  --set-env-vars="PRIMARY_LLM_PROVIDER=anthropic,FALLBACK_LLM_PROVIDER=groq,APP_MODE=mock,LANGCHAIN_TRACING=true,LANGCHAIN_PROJECT=biomed-troubleshooter" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest,GROQ_API_KEY=groq-api-key:latest,LANGCHAIN_API_KEY=langsmith-api-key:latest"
```

Secrets should be stored in Secret Manager — never baked into the image or
passed as `--set-env-vars`.

### CI/CD

`.github/workflows/ci.yml` runs on every push / PR to `main`:

1. Install deps on Python 3.11 and 3.12.
2. `ruff check` + `black --check` + `mypy` (informational).
3. `pytest` with coverage.
4. `docker build` smoke test.

`.pre-commit-config.yaml` provides local hooks:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Hooks enforce: trailing whitespace, EOF newlines, YAML/TOML validity, **gitleaks
secret scan**, black, ruff.

---

## 9. Observability

### LangSmith

Set `LANGCHAIN_API_KEY` and `LANGCHAIN_TRACING=true` — every graph invocation
is traced automatically because LangChain picks those env vars up at import
time.

The FastAPI layer tags every trace with `session:<session_id>`:

```python
config = {
    "configurable": {"thread_id": session_id},
    "tags": [f"session:{session_id}"],
    "metadata": {"session_id": session_id},
}
graph.invoke(graph_input, config=config)
```

Filter by `tags: session:case-001` in the LangSmith UI to pull every turn of
one case into a single timeline.

### Structured logs

Every node logs its entry with an emoji tag (🧠 reason, 🔧 repair, 📏 step,
etc.) so raw container logs are still readable. LLM rotation events are
logged at `INFO` from `src.infrastructure.llm_manager`:

```
LLMManager initialized: primary=anthropic, fallback=groq
  anthropic: 1 key(s), models=['claude-opus-4-6']
  groq:      2 key(s), models=['llama-3.3-70b-versatile']
Active LLM: provider=anthropic, model=claude-opus-4-6, key_index=0
```

### Checkpointer

`MemorySaver` keeps per-`thread_id` state in-process. For multi-pod Cloud Run
deployments replace it with a persistent checkpointer (Postgres / Redis) when
cross-replica session continuity becomes a requirement.

---

## 10. Roadmap

- [ ] **Persistent checkpointer** — swap `MemorySaver` for a Postgres-backed
  one so Cloud Run replicas share session state.
- [ ] **Prompt caching on Anthropic calls** — apply `cache_control: ephemeral`
  to the large system prompt that carries equipment config, shaving latency
  and cost on multi-turn sessions.
- [ ] **Cloud Run authentication** — require IAM-authenticated traffic and
  issue short-lived ID tokens to the frontend instead of `--allow-unauthenticated`.
- [ ] **Real-hardware CI** — a nightly job that runs the `usb` mode against a
  rack-mounted MS8250D to catch driver regressions.
- [ ] **Broader equipment catalogue** — current bundle ships `test-psu-v1` and
  a CCTV PSU scenario; add real biomedical units (infusion pump, ventilator).
- [ ] **Confidence calibration** — log per-hypothesis probability trajectories
  and back-test against historical outcomes.

---

## License

MIT — see `LICENSE`.
