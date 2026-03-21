# Project Architecture

> How the system works - technical implementation details

---

## Tech Stack Breakdown

### Core Framework
| Component | Technology | Version |
|-----------|------------|---------|
| Agent Framework | LangGraph | ≥0.0.20 |
| LLM Framework | LangChain | ≥0.1.0 |
| Language | Python | ≥3.10 |
| Type Safety | Pydantic | ≥2.0.0 |

### Data & Storage
| Component | Technology | Purpose |
|-----------|------------|---------|
| Vector Database | ChromaDB (embedded) | RAG knowledge base - no server needed |
| Configuration | YAML | Equipment-specific thresholds, faults |
| Knowledge Docs | Markdown | Equipment diagnostics documentation |

### AI/ML
| Component | Technology | Purpose |
|-----------|------------|---------|
| Primary LLM | Groq (Llama 3.3 70B) | Diagnostic reasoning |
| Fallback LLM | Ollama (local) | Offline capability |
| Embeddings | sentence-transformers | Local embedding (all-MiniLM-L6-v2) |
| Observability | LangSmith | Full run tracing |

### Hardware Integration
| Component | Technology | Purpose |
|-----------|------------|---------|
| Serial Communication | pyserial | Mastech MS8250D multimeter |
| Protocol | UART @ 2400 baud | CP210x USB-to-Serial adapter |

---

## Folder Structure

```
ai-agent/
├── .coding-agent/              # AI project memory system
│   ├── AGENTS.md               # Entry point (READ THIS FIRST)
│   ├── STATUS.md               # Current state
│   ├── SPEC.md                 # Product spec
│   ├── ARCHITECTURE.md         # Technical details (YOU ARE HERE)
│   └── sessions/               # Session history
│
├── src/
│   ├── application/            # LangGraph workflow definition
│   │   ├── agent.py            # Main diagnostic workflow (legacy)
│   │   ├── diagnostic_agent.py # NEW: Step-by-step LangGraph workflow
│   │   └── conversational_agent.py  # Conversational variant
│   │
│   ├── domain/                 # Business logic (no framework dependencies)
│   │   ├── models.py           # Domain models & services
│   │   └── diagnostic_state.py # NEW: Diagnostic state management
│   │
│   ├── infrastructure/         # External integrations
│   │   ├── config.py           # Centralized configuration
│   │   ├── chromadb_client.py  # ChromaDB (embedded mode)
│   │   ├── llm_client.py       # Groq/Ollama LLM wrapper
│   │   ├── llm_manager.py      # LLM provider management
│   │   ├── usb_multimeter.py   # Serial communication
│   │   ├── equipment_config.py # YAML loader
│   │   ├── rag_repository.py   # RAG operations
│   │   └── multimeter_stabilizer.py # NEW: Stabilization engine
│   │
│   ├── interfaces/             # User-facing interfaces
│   │   ├── cli.py              # Command-line interface
│   │   └── mode_router.py      # Mock/USB mode selection
│   │
│   └── studio/                 # LangGraph Studio integration
│       ├── langgraph_studio.py # Studio entry point
│       ├── tools.py            # LangGraph tools (RAG + measurement)
│       ├── conversational_agent.py # Studio agent
│       └── background_usb_reader.py # Async USB reading
│
├── data/
│   ├── equipment/              # Equipment configurations (YAML)
│   │   └── cctv-psu-24w-v1.yaml
│   ├── knowledge/              # RAG documentation
│   │   └── cctv-psu-24w-v1-diagnostics.md
│   └── mock_signals/           # Test scenarios (JSON)
│       └── scenarios.json
│
├── docs/                       # Project documentation
├── tests/                      # Unit tests
├── pyproject.toml              # Python dependencies
└── langgraph.json             # LangGraph Studio config
```

---

## System Architecture Diagram

```mermaid
graph TB
    subgraph "Input Sources"
        MOCK[Mock Mode<br/>JSON Scenarios]
        USB[USB Mode<br/>Mastech MS8250D<br/>via CP210x]
    end

    subgraph "CLI Interface"
        CLI[src/interfaces/cli.py]
        ROUTE[Mode Router]
    end

    subgraph "LangGraph Workflow<br/>src/application/diagnostic_agent.py"
        RAG[RAG_NODE<br/>Retrieve diagnostic knowledge]
        PLAN[PLAN_NODE<br/>Select hypothesis]
        STEP[STEP_NODE<br/>Atomic diagnostic step<br/>Show → Measure → Evaluate → Reason → Explain]
        DECISION[DECISION_NODE<br/>Determine next action]<n    INTERRUPT[INTERRUPT_NODE<br/>Wait for user "Next"]
        REPAIR[REPAIR_NODE<br/>Output repair steps]
    end

    subgraph "Domain Layer<br/>src/domain/"
        DIAG_STATE[DiagnosticState<br/>diagnostic_state.py]
        DIAG_ENGINE[DiagnosticEngine<br/>diagnostic_state.py]
        MODELS[Models & Services]
    end

    subgraph "Infrastructure<br/>src/infrastructure/"
        CONFIG[Configuration]
        CHROMA[ChromaDB<br/>(embedded)]
        LLM[LLM Client (Groq)]
        EQUIP[Equipment Config]
        STABILIZER[MultimeterStabilizer<br/>multimeter_stabilizer.py]
    end

    MOCK --> ROUTE
    USB --> ROUTE
    ROUTE --> CLI
    CLI --> RAG

    RAG --> PLAN
    PLAN --> STEP
    STEP --> DECISION
    DECISION -->|Fault confirmed| REPAIR
    DECISION -->|More tests needed| INTERRUPT
    INTERRUPT -->|NEXT pressed| STEP

    RAG -.-> CHROMA
    PLAN -.-> EQUIP
    STEP -.-> STABILIZER
    STEP -.-> EQUIP
    DECISION -.-> CHROMA
    DIAG_STATE -.-> MODELS
    DIAG_ENGINE -.-> EQUIP
```

---

## Key Components

### LangGraph Workflow Nodes

The diagnostic agent uses an 8-node LangGraph workflow with interrupt-based step control:

| Node | File | Responsibility |
|------|------|----------------|
| [`rag_node`](src/application/diagnostic_agent.py:85) | diagnostic_agent.py | Query ChromaDB for diagnostic guidance |
| [`plan_node`](src/application/diagnostic_agent.py:141) | diagnostic_agent.py | Generate hypothesis list from RAG + config |
| [`instruction_node`](src/application/diagnostic_agent.py:273) | diagnostic_agent.py | Display test point, image, probe instructions |
| [`interrupt_node`](src/application/diagnostic_agent.py:314) | diagnostic_agent.py | **CRITICAL**: Pause workflow, wait for user |
| [`measure_node`](src/application/diagnostic_agent.py:356) | diagnostic_agent.py | Take stabilized measurement |
| [`evaluate_node`](src/application/diagnostic_agent.py:439) | diagnostic_agent.py | Compare against expected values |
| [`reason_node`](src/application/diagnostic_agent.py:529) | diagnostic_agent.py | Decide: continue or repair |
| [`repair_node`](src/application/diagnostic_agent.py:620) | diagnostic_agent.py | Output repair guidance |

### Workflow Diagram (CORRECTED)

```mermaid
graph TD
    RAG[RAG_NODE<br/>Retrieve diagnostic knowledge] --> PLAN[PLAN_NODE<br/>Select hypothesis]
    PLAN --> STEP[STEP_NODE<br/>Atomic diagnostic step<br/>Show test point → Show image → Measure → Stabilize → Evaluate → Reason → Explain]
    STEP --> DECISION[DECISION_NODE<br/>Determine next action]
    DECISION -->|Fault confirmed| REPAIR[REPAIR_NODE<br/>Output repair steps]
    DECISION -->|More tests needed| INTERRUPT[INTERRUPT_NODE<br/>Wait for user "Next"]
    INTERRUPT -->|NEXT pressed| STEP
    REPAIR --> END

    style RAG fill:#e3f2fd
    style PLAN fill:#e3f2fd
    style STEP fill:#fff3e0
    style DECISION fill:#f3e5f5
    style INTERRUPT fill:#ffcdd2
    style REPAIR fill:#c8e6c9
```

**Node Responsibilities:**

| Node | Purpose | Key Behavior |
|------|---------|--------------|
| RAG_NODE | Query ChromaDB for fault hypotheses | Retrieves top-3 relevant docs |
| PLAN_NODE | Select next hypothesis from RAG results | Builds ordered hypothesis list |
| STEP_NODE | **ATOMIC**: Complete diagnostic step | 1)Show test point 2)Show probe placement 3)Show ONE image 4)Call read_multimeter 5)Stabilize 6)Evaluate 7)Reason 8)Explain to user 9)Decide next action |
| DECISION_NODE | **CRITICAL**: Determine next action | FAULT CONFIRMED → REPAIR, or MORE TESTS → INTERRUPT |
| INTERRUPT_NODE | **CRITICAL**: Pause AFTER step completes | Uses `langgraph.types.interrupt()` - user presses "Next" to continue |
| REPAIR_NODE | Terminal node | Outputs confirmed fault + repair steps |

**Key Correction:** INTERRUPT happens AFTER the full STEP completes, NOT before measurement. This ensures the user sees the test instructions and image before the system pauses for confirmation.

---

## New Components

### MultimeterStabilizer

File: [`src/infrastructure/multimeter_stabilizer.py`](src/infrastructure/multimeter_stabilizer.py:21)

Provides stable reading extraction using statistical algorithms:

```python
class MultimeterStabilizer:
    def __init__(
        self,
        max_samples: int = 50,
        min_samples: int = 5,
        max_duration: float = 180.0,
        window_size: int = 10,
        stability_threshold: float = 0.01,
        cluster_tolerance: float = 0.05,
        zero_threshold: float = 0.01
    ):
        """Initialize stabilizer with statistical parameters."""
```

**Stabilization Algorithm:**
1. Maintain rolling window of 10 samples
2. Check stability: std_dev < 1% of mean
3. If stable → return mean of window
4. If unstable → apply trimmed mean (10% top/bottom)
5. Apply cluster detection → select largest cluster within ±5%
6. Validate zero readings with majority rule

### DiagnosticState

File: [`src/domain/diagnostic_state.py`](src/domain/diagnostic_state.py:23)

Tracks complete state of diagnostic session:

```python
class DiagnosticState(BaseModel):
    equipment_model: str
    current_step: int
    completed_steps: List[int]
    measurements: Dict[str, Any]
    current_hypothesis: str
    hypothesis_list: List[str]
    waiting_for_next: bool  # Key: indicates paused state
    diagnosis_progress: Literal["in_progress", "completed", "fault_confirmed"]
    tested_points: List[str]
    eliminated_faults: List[str]
    retrieved_context: Dict[str, Any]
```

### DiagnosticEngine

File: [`src/domain/diagnostic_state.py`](src/domain/diagnostic_state.py:238)

Manages diagnostic workflow orchestration:

```python
class DiagnosticEngine:
    def load_equipment_config(self, equipment_model: str) -> Dict:
        """Load ONCE at start, cache in state."""

    def initialize_diagnosis(self, symptoms: str) -> DiagnosticState:
        """Start new diagnosis, retrieve RAG context."""

    def _build_diagnostic_steps(self) -> None:
        """Build steps from current hypothesis."""
```

---

## Data Flow

### Phase 1: Initialization

```
User Input (symptoms) → RAG Query → Hypothesis List → First Test Point
```

### Phase 2: Step-by-Step Execution (Repeats)

```
PLAN → STEP → DECISION
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
FAULT CONFIRMED    MORE TESTS NEEDED
    │                   │
    ▼                   ▼
REPAIR (end)      INTERRUPT (wait for NEXT)
                       │
                       ▼
                   STEP (next)
```

**STEP is atomic - performs all 9 operations in sequence:**
1. Show test point name
2. Show probe placement instructions
3. Show exactly ONE image
4. Call read_multimeter
5. Stabilize measurement
6. Evaluate against expected values
7. Reason about the result
8. Explain to user: measured value, expected value, interpretation, conclusion
9. Decide next action (passes to DECISION node)

```
INSTRUCTION → INTERRUPT (wait) → MEASURE → EVALUATE → REASON
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
             More tests needed          Fault confirmed           Uncertain
                    │                         │                         │
                    ▼                         ▼                         ▼
               RAG (next)              REPAIR (end)             RAG (retry)
```

### Phase 3: Repair (Terminal)

```
REPAIR → Recovery Steps → END
```

---

## Infrastructure Components

| Component | File | Purpose |
|-----------|------|---------|
| [`AppConfig`](src/infrastructure/config.py:18) | config.py | Centralized configuration dataclass |
| [`ChromaDBClient`](src/infrastructure/chromadb_client.py:15) | chromadb_client.py | ChromaDB embedded client |
| [`LLMClient`](src/infrastructure/llm_client.py:20) | llm_client.py | Groq/Ollama LLM abstraction |
| [`LLMManager`](src/infrastructure/llm_manager.py:30) | llm_manager.py | Multi-provider LLM management |
| [`USBMultimeter`](src/infrastructure/usb_multimeter.py:40) | usb_multimeter.py | Serial communication with MS8250D |
| [`EquipmentConfigLoader`](src/infrastructure/equipment_config.py:20) | equipment_config.py | YAML parsing for equipment |
| [`MultimeterStabilizer`](src/infrastructure/multimeter_stabilizer.py:21) | multimeter_stabilizer.py | **NEW**: Stabilization engine |
| [`RAGRepository`](src/infrastructure/rag_repository.py:25) | rag_repository.py | RAG operations |
| [`DiagnosticState`](src/domain/diagnostic_state.py:23) | diagnostic_state.py | **NEW**: State management |
| [`DiagnosticEngine`](src/domain/diagnostic_state.py:238) | diagnostic_state.py | **NEW**: Workflow orchestration |

---

## Configuration System

### Environment Variables

```python
# src/infrastructure/config.py
@dataclass
class AppConfig:
    mode: str = "mock"          # "mock" or "usb"

    llm: LLMConfig              # Provider: "groq" or "ollama"
                                # Model: "llama-3.3-70b-versatile"
                                # Temperature: 0.0-1.0

    embedding: EmbeddingConfig  # Provider: "sentence-transformers"
                                # Model: "all-MiniLM-L6-v2"

    usb: USBConfig              # Port: "COM3" (auto-detect)
                                # Baud: 2400

    mock: MockConfig            # Default scenario name
```

### Equipment YAML Schema

```yaml
# data/equipment/cctv-psu-24w-v1.yaml
equipment_model: CCTV-PSU-24W-V1
manufacturer: Generic CCTV
power_output: 24W

test_points:
  output_rail:
    nominal_voltage: 24.0
    tolerance: 0.10
    unit: V

faults:
  overvoltage_output:
    signature:
      - test_point: output_rail
        state: over_voltage
    hypothesis: "Zener diode failure"
    confidence_weight: 0.9
    hypotheses:
      - rank: 1
        component: zener_diode
        cause: Zener voltage regulator failure
        confidence: high

recovery:
  overvoltage_output:
    - priority: 1
      action: "Replace Zener diode"
      instruction: |
        1. Disconnect power
        2. Locate Zener on PCB
        ...
```

---

## Design Principles

### 1. Step-by-Step Control (NOT Conversational)
- Each diagnostic step is atomic: show → measure → evaluate → decide
- Interrupt between steps using `langgraph.types.interrupt()`
- User must confirm "Next" before measurement proceeds

### 2. RAG-Grounded Evidence
- ALL diagnostic guidance comes from ChromaDB
- No free-form LLM responses without RAG context
- Prevents hallucinations in fault diagnosis

### 3. Stabilized Measurements
- Multimter readings stabilized before interpretation
- Rolling window + cluster detection algorithm
- Confidence levels: HIGH / MEDIUM / LOW

### 4. Deterministic + Probabilistic
- **Deterministic**: Rule-based matching for known fault patterns
- **Probabilistic**: LLM reasoning for ambiguous cases
- **Fallback chain**: Rules first → LLM for edge cases

### 5. Embedded Dependencies
ChromaDB runs in embedded mode - no Docker or server required

---

## Running the System

### LangGraph Studio Mode
```bash
pip install -r requirements.txt
langgraph dev --port 2024
# Open browser to interact with agent
```

### Mock Mode (No Hardware)
```bash
python -m src.interfaces.cli --mock
# Uses scenarios from data/mock_signals/
```

---

## Key Differences from Old System

| Old System | New System |
|------------|------------|
| Conversational flow | Step-by-step workflow |
| Continuous measurement | Interrupt between steps |
| Raw multimeter readings | Stabilized readings |
| Ad-hoc hypothesis testing | RAG-driven ordered hypotheses |
| No state persistence | DiagnosticState with serialization |
| Single-pass workflow | Loop until fault confirmed |

---

## Memory Stewardship

This file is part of the `.coding-agent/` memory system. Any architectural changes must be reflected here.

**Last Updated**: 2026-03-21
**Key Changes**: Added step-by-step diagnostic engine with interrupt-based workflow
