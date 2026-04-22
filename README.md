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
8. [Database](#8-database)
9. [Analytics](#9-analytics)
10. [Deployment](#10-deployment)
11. [Observability](#11-observability)
12. [Roadmap](#12-roadmap)

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
                  │   + checkpointer            │
                  │     Postgres if DATABASE_URL│
                  │     else MemorySaver        │
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

## 8. Database

Postgres is optional for local dev (the agent runs happily on YAML + in-memory
state) but required for any deployment where a single container instance isn't
the whole fleet. Three things live in the DB:

| Data | Written by | Read by |
|---|---|---|
| **LangGraph checkpoints** | `PostgresSaver` in `src/graph/builder.py` | The graph itself — resuming a `thread_id` across cold starts |
| **Diagnostic cases + measurements** | `record_case()` in `src/infrastructure/db/cases_repository.py` | `src/analytics/queries.py` |
| **Equipment knowledge base** (optional) | `scripts/seed_equipment.py` | `EquipmentConfigLoader(backend="postgres")` |

### Local Postgres (Docker Compose)

```bash
docker compose up -d postgres    # postgres:15-alpine on localhost:5432
```

Then point the app at it:

```bash
# .env
DATABASE_URL=postgresql://biomed:biomed@localhost:5432/biomed
EQUIPMENT_STORE=yaml              # "postgres" to serve equipment from DB
```

With `DATABASE_URL` **unset or empty** the code falls back to:
- `MemorySaver()` (in-process checkpoints — fine for Studio + unit tests)
- no-op case writes
- YAML-on-disk equipment loader

This means unit tests stay hermetic (`tests/conftest.py` pins `DATABASE_URL=""`)
and contributors don't need Docker to run the existing suite.

### Schema & migrations

Schema is managed via **Alembic** in `alembic/versions/`. The initial migration
(`0001_init.py`) creates six tables:

```
diagnostic_cases     -- one row per completed graph run
case_measurements    -- one row per multimeter reading
equipment            -- name + JSONB raw_config (source of truth)
signals              -- lightweight index on equipment.signals
faults               -- lightweight index on equipment.faults
signal_dependencies  -- edges in the signal dependency graph
```

The `equipment.raw_config` column is JSONB — we keep the authored YAML shape
verbatim and materialise scalar columns + index tables for query speed. The
YAML files under `data/equipment/` remain the authoring format; Postgres is the
runtime format.

Apply migrations:

```bash
alembic upgrade head
```

Seed equipment from YAML (idempotent — re-run after edits):

```bash
python scripts/seed_equipment.py
# or just one:
python scripts/seed_equipment.py --equipment-id test-psu-v1
```

### Why YAML stays

YAML diffs well in PRs and is the lingua franca for engineers adding equipment.
Postgres gives us queryable JSONB, atomic updates, and a consistent runtime
image across replicas. `seed_equipment.py` is the one-way bridge from authoring
format to runtime format — the same pattern Kubernetes uses (manifests → etcd).

---

## 9. Analytics

`src/analytics/queries.py` exposes eight canonical SQL-backed queries as plain
Python functions. Each returns a list of `@dataclass(frozen=True)` rows — no
FastAPI surface, no dashboard; the agent writes, SQL reads.

| Function | What it answers |
|---|---|
| `fault_frequency_by_equipment(equipment_id)` | Which signals fault most often on a given unit |
| `mean_time_to_diagnosis(equipment_id, since)` | p50 / p95 wall-clock to a confirmed diagnosis |
| `hypothesis_accuracy()` | % of resolved cases where the initial top-ranked hypothesis was the final diagnosis |
| `token_cost_per_case(outcome)` | Input/output token cost distribution, grouped by outcome |
| `measurement_reuse_rate()` | How often the same test-point appears across cases |
| `outcome_distribution_by_model()` | Opus vs. Groq performance comparison |
| `daily_case_volume(days=30)` | Time-series bucketed by day |
| `most_informative_measurements()` | Test-points that most often confirm / eliminate hypotheses |

Example:

```python
from src.analytics import queries as Q

rows = Q.fault_frequency_by_equipment("test-psu-v1")
for r in rows:
    print(f"{r.test_point:<30} {r.fault_count:>3}/{r.total_observations:>3}  ({r.fault_rate:.1%})")
```

Queries work against both Postgres and SQLite (the test suite pumps fixture
rows into an in-memory SQLite and exercises every query). `mean_time_to_diagnosis`
uses `EXTRACT(EPOCH FROM …)` on Postgres and the equivalent `julianday()` math
on SQLite.

---

## 10. Deployment

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

### Google Cloud Run + Cloud SQL (end-to-end)

This is the one-shot walkthrough for a fresh GCP project. Replace `$PROJECT_ID`
with your project and adjust region if needed.

```bash
# 0. Prerequisites
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
    secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# 1. Artifact Registry repo (one-time)
gcloud artifacts repositories create biomed \
    --repository-format=docker --location=us-central1

# 2. Cloud SQL for Postgres (one-time) — db-f1-micro is ~$10/mo
gcloud sql instances create biomed-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --storage-auto-increase
gcloud sql databases create biomed --instance=biomed-db
gcloud sql users create biomed --instance=biomed-db --password='<generated-pw>'

# 3. Secrets (one-time) — Unix socket form; Cloud Run attaches the socket at
#    /cloudsql/<instance-connection-name>
printf "postgresql://biomed:<pw>@/biomed?host=/cloudsql/$PROJECT_ID:us-central1:biomed-db" \
    | gcloud secrets create database-url --data-file=-
printf "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-
printf "$GROQ_API_KEY"      | gcloud secrets create groq-api-key      --data-file=-
printf "$LANGSMITH_API_KEY" | gcloud secrets create langsmith-api-key --data-file=-

# 4. Build + push via Cloud Build
IMAGE=us-central1-docker.pkg.dev/$PROJECT_ID/biomed/api:$(git rev-parse --short HEAD)
gcloud builds submit --tag $IMAGE

# 5. Run schema migrations once (Cloud Run Job)
gcloud run jobs create biomed-migrate \
    --image $IMAGE \
    --command python \
    --args -m,alembic,upgrade,head \
    --set-secrets DATABASE_URL=database-url:latest \
    --add-cloudsql-instances $PROJECT_ID:us-central1:biomed-db \
    --region us-central1 || true
gcloud run jobs execute biomed-migrate --region us-central1 --wait

# 6. Seed equipment (Cloud Run Job) — only needed if EQUIPMENT_STORE=postgres
gcloud run jobs create biomed-seed \
    --image $IMAGE \
    --command python --args scripts/seed_equipment.py \
    --set-secrets DATABASE_URL=database-url:latest \
    --add-cloudsql-instances $PROJECT_ID:us-central1:biomed-db \
    --region us-central1 || true
gcloud run jobs execute biomed-seed --region us-central1 --wait

# 7. Deploy the API
gcloud run deploy biomed-api \
    --image $IMAGE \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances $PROJECT_ID:us-central1:biomed-db \
    --set-secrets DATABASE_URL=database-url:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,GROQ_API_KEY=groq-api-key:latest,LANGCHAIN_API_KEY=langsmith-api-key:latest \
    --set-env-vars PRIMARY_LLM_PROVIDER=anthropic,FALLBACK_LLM_PROVIDER=groq,EQUIPMENT_STORE=postgres,LANGCHAIN_TRACING=true,LANGCHAIN_PROJECT=biomed-troubleshooter \
    --cpu 1 --memory 1Gi \
    --min-instances 0 --max-instances 5 \
    --timeout 300 --concurrency 10
```

Secrets are pulled from Secret Manager at cold-start; they're never baked into
the image or passed as `--set-env-vars`. The Cloud SQL connector injects a Unix
socket at `/cloudsql/<instance>` — the SQLAlchemy URL uses `host=/cloudsql/...`
rather than a TCP address, which is why no VPC connector is required.

### Verifying the deployment

```bash
# Health + readiness (readyz probes DB with SELECT 1)
curl https://biomed-api-<hash>.run.app/healthz
curl https://biomed-api-<hash>.run.app/readyz    # expects {"status":"ready","db":"ok"}

# Run a case and confirm it persisted
curl -X POST https://biomed-api-<hash>.run.app/run-agent \
  -H "Content-Type: application/json" \
  -d '{"message":"no output voltage","equipment_model":"test-psu-v1","session_id":"prod-smoke-1"}'

gcloud sql connect biomed-db --user=biomed --database=biomed \
  --quiet -- -c "SELECT outcome, measurement_count FROM diagnostic_cases ORDER BY completed_at DESC LIMIT 5;"
```

### CI/CD

`.github/workflows/ci.yml` runs on every push / PR to `main`:

1. Install deps on Python 3.11 and 3.12.
2. `ruff check` + `black --check` + `mypy` (informational).
3. `pytest` with coverage. A Postgres 15-alpine service container is provisioned
   and exposed as `TEST_DATABASE_URL` for any `@pytest.mark.integration` tests;
   the default unit run keeps `DATABASE_URL=""` (pinned in `conftest.py`) and
   exercises the SQLAlchemy models against in-memory SQLite.
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

## 11. Observability

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

When `DATABASE_URL` is set, the graph compiles with `PostgresSaver`, backed by
a `psycopg` connection pool created once per worker in the FastAPI lifespan.
This means conversation state survives Cloud Run replica rotation, rolling
deploys, and scale-to-zero cold starts — a user returning with the same
`thread_id` resumes exactly where they left off. When `DATABASE_URL` is empty
(Studio, unit tests, local prototyping) the graph silently falls back to
`MemorySaver` so there is no DB dependency on the hot path for dev work.

---

## 12. Roadmap

- [x] **Persistent checkpointer** — `PostgresSaver` is wired in; `MemorySaver`
  remains the fallback when `DATABASE_URL` is empty.
- [x] **Diagnostic-case analytics** — `diagnostic_cases` + `case_measurements`
  tables populated per run; eight canonical queries in `src/analytics/queries.py`.
- [x] **Equipment loader backend switch** — `EQUIPMENT_STORE=postgres` serves
  equipment from JSONB; `yaml` remains the authoring format and default.
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
