# AI-Powered Troubleshooting Agent - Project Documentation

> **Purpose**: This document provides comprehensive context for AI & AI agents working with or maintaining this project.
> **Last Updated**: 2026-02-28
> **Project**: Biomedical/CCTV Equipment Troubleshooting Agent

---

## 1. Project Overview

### 1.1 What This Project Does

This is an **AI-powered troubleshooting assistant** designed to help engineers diagnose and repair biomedical and CCTV equipment. The agent uses:

- **LangGraph** for workflow orchestration with state management
- **Groq LLM** (llama-3.3-70b-versatile) for conversational reasoning
- **ChromaDB** (vector database) for RAG-based knowledge retrieval  
- **USB Multimeter** integration for real-time measurements
- **YAML-based equipment configurations** for equipment-specific knowledge

### 1.2 Core Capabilities

1. **Conversational Interface**: Engineers describe problems in natural language
2. **Guided Diagnostics**: Step-by-step troubleshooting with safety warnings
3. **Automated Measurements**: Reads directly from USB multimeter (Mastech MS8250D)
4. **Fault Diagnosis**: Matches signal patterns against known fault signatures
5. **Recovery Guidance**: Provides ordered repair steps with verification criteria

### 1.3 Usage Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Mock** | `python -m src.interfaces.cli --mock` | Simulated faults for testing |
| **Live/USB** | `python -m src.interfaces.cli --usb` | Real multimeter integration |
| **LangGraph Studio** | `npx langgraph-cli studio -c langgraph.json` | Web UI for agent interaction |

---

## 2. Technology Stack

### 2.1 Core Technologies

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Agent Framework** | LangGraph | 0.0.20+ | Workflow orchestration, state management, checkpointing |
| **LLM Provider** | Groq | - | Fast inference (llama-3.3-70b-versatile) |
| **Vector Database** | ChromaDB | Latest | RAG knowledge base storage |
| **Embeddings** | sentence-transformers | all-MiniLM-L6-v2 | Local embeddings (no API cost) |
| **USB Communication** | pyserial | - | Mastech MS8250D multimeter |
| **Observability** | LangSmith | - | Tracing and debugging |

### 2.2 Key Dependencies

```
langgraph>=0.0.20
langchain-groq
chromadb
sentence-transformers
pyserial
python-dotenv
pyyaml
langchain
```

### 2.3 Infrastructure Services

The project uses Docker for:
- **ChromaDB**: http://localhost:8000 (vector database)
- **Mosquitto3 (MQTT broker - for ESP**: localhost:18832 integration)

---

## 3. Architecture

### 3.1 High-Level System Architecture

```
+-------------------------------------------------------------------------+
|                     LangGraph Studio (Frontend)                          |
|                    http://localhost:3453                                |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                   Conversational Agent (LangGraph)                       |
|  +-----------------------------------------------------------------+   |
|  |  ConversationalAgentState (Dataclass)                          |   |
|  |  * messages: Annotated list with add_messages reducer         |   |
|  |  * equipment_model, initial_problem                            |   |
|  |  * collected_measurements, test_points_measured               |   |
|  |  * workflow_phase: initial -> clarifying -> measuring -> ...  |   |
|  +-----------------------------------------------------------------+   |
|                                    |                                   |
|                          +---------+---------+                          |
|                          v                   v                          |
|                   +--------------+    +-----------------+             |
|                   |  Tool Node    |    |   LLM (Groq)   |             |
|                   |  (ReAct)      |    |  llama-3.3-70b  |             |
|                   +------+-------+    +-----------------+             |
|                          |                                              |
+--------------------------+----------------------------------------------+
                           |
        +------------------+------------------+------------------+
        v                  v                  v                  v
+---------------+  +---------------+  +---------------+  +---------------+
| query_        |  | get_equipment |  | read_         |  | ChromaDB      |
| diagnostic_   |  | _configuration|  | multimeter    |  | (RAG)         |
| knowledge     |  |               |  |               |  |               |
+---------------+  +---------------+  +---------------+  +---------------+
```

### 3.2 Data Flow

1. **User Input**: Engineer describes problem via LangGraph Studio
2. **Agent Processing**: LLM receives message + system prompt + conversation history
3. **Tool Selection**: Agent decides which tool to call based on context
4. **Evidence Retrieval**: RAG queries ChromaDB for diagnostic procedures
5. **Equipment Config**: Thresholds and fault signatures loaded from YAML
6. **Measurement**: USB multimeter readings collected (or manual entry)
7. **Diagnosis**: Signal patterns matched against fault signatures
8. **Response**: Agent provides guidance and recovery instructions

### 3.3 Key Design Patterns

- **add_messages Reducer**: Automatic message history management in LangGraph state
- **MemorySaver Checkpointing**: Session continuity across requests
- **Equipment Abstraction**: All equipment knowledge in YAML - no hardcoded logic
- **RAG-First**: All diagnostic guidance comes from vector store to prevent hallucination

---

## 4. Key Files and Their Purposes

### 4.1 Core Agent Files

| File | Purpose |
|------|---------|
| `src/studio/conversational_agent.py` | Main LangGraph definition, state schema (ConversationalAgentState), agent node factory (create_agent_node()) |
| `src/studio/tools.py` | LangChain tools: query_diagnostic_knowledge, get_equipment_configuration, get_test_point_guidance, read_multimeter, enter_manual_reading |
| `src/studio/background_usb_reader.py` | Background thread for continuous multimeter reading with noise filtering and stabilization |
| `src/studio/langgraph_studio.py` | LangGraph Studio entry point, graph() factory function |
| `langgraph.json` | LangGraph Studio configuration |

### 4.2 Infrastructure Files

| File | Purpose |
|------|---------|
| `src/infrastructure/usb_multimeter.py` | Serial communication with Mastech MS8250D, binary frame parsing, auto-detection |
| `src/infrastructure/chromadb_client.py` | ChromaDB wrapper with lazy initialization |
| `src/infrastructure/rag_repository.py` | RAG retrieval, document snippet parsing, fallback rules |
| `src/infrastructure/equipment_config.py` | YAML loader for equipment configs, fault matching, threshold interpretation |
| `src/infrastructure/llm_client.py` | LLM factory for Groq/OpenAI providers |

### 4.3 Data Files

| File | Purpose |
|------|---------|
| `data/equipment/cctv-psu-24w-v1.yaml` | Complete CCTV PSU specification: signals, thresholds, faults, recovery steps |
| `data/knowledge/cctv-psu-24w-v1-diagnostics.md` | Source documentation for RAG ingestion |
| `data/chromadb/` | Persisted ChromaDB vector store |
| `data/mock_signals/*.json` | Simulated fault scenarios for testing |

### 4.4 Configuration Files

| File | Purpose |
|------|---------|
| `.env` | API keys (GROQ_API_KEY, LANGCHAIN_API_KEY), mode settings |
| `docker-compose.yml` | ChromaDB and Mosquitto services |
| `start-services.ps1` / `start-services.sh` | Service startup scripts |

---

## 5. How to Run

### 5.1 Prerequisites

1. **Python 3.10+** installed
2. **Docker Desktop** running (for ChromaDB)
3. **Groq API key** from https://console.groq.com
4. **LangSmith API key** (optional) from https://smith.langchain.com

### 5.2 Setup Steps

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your API keys
# GROQ_API_KEY=your-groq-key
# LANGCHAIN_API_KEY=your-langsmith-key (optional)

# 3. Start infrastructure services
.\start-services.ps1   # Windows
# OR
./start-services.sh    # Linux/macOS

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run LangGraph Studio
npx langgraph-cli studio -c langgraph.json
```

LangGraph Studio will open at **http://localhost:3453**

### 5.3 Using LangGraph Studio

1. Open LangGraph Studio in browser
2. Select the "conversational_agent" graph
3. Start a new thread
4. Describe the problem (e.g., "My CCTV power supply has no output")

---

## 6. Features

### 6.1 USB Multimeter Integration

**Hardware**: Mastech MS8250D USB Multimeter

**How It Works**:
- background_usb_reader.py runs a background thread
- Continuously reads from serial port at 2400 baud
- Applies noise filtering (ignores values < 0.5V)
- Waits for stabilization (std dev <= 5V)
- Returns averaged stable reading to agent

**Supported Measurements**:
- DC Voltage, AC Voltage, DC Current
- Resistance, Continuity, Frequency, Capacitance

**Fallback**: If USB unavailable, use enter_manual_reading tool for manual entry

### 6.2 RAG Knowledge Base

All diagnostic guidance comes from ChromaDB to prevent hallucination.

**Knowledge Sources**:
- Equipment diagnostic manuals
- Measurement procedures
- Fault case studies
- Safety guidelines

**Retrieval Process**:
1. Agent sends query to query_diagnostic_knowledge tool
2. Query embedded using sentence-transformers
3. ChromaDB finds semantically similar documents
4. Top-k results returned with relevance scores
5. Agent uses retrieved content for guidance

**Ingestion**:
```bash
python scripts/ingest_knowledge.py
```

### 6.3 Diagnostic Workflows

**Workflow Phases**:
1. **Initial**: Engineer provides equipment model and problem description
2. **Clarifying**: Agent asks questions to narrow down the issue
3. **Measuring**: Agent guides to specific test points, collects measurements
4. **Diagnosing**: Agent analyzes accumulated evidence against fault signatures
5. **Complete**: Final diagnosis with recovery recommendations

**Fault Matching**:
- Equipment config defines fault signatures (signal patterns)
- Measurements interpreted against thresholds -> semantic states
- Signal states (e.g., "missing", "over_voltage", "normal") matched against known faults
- Highest-priority matching fault is selected

### 6.4 Equipment Configuration System

All equipment-specific knowledge in YAML - **no hardcoded logic**.

**CCTV PSU Example** (data/equipment/cctv-psu-24w-v1.yaml):

```yaml
signals:
  - signal_id: "output_12v"
    name: "12V Output Rail"
    test_point: "TP2"
    parameter: "voltage_dc"
    unit: "V"

thresholds:
  - signal_id: "output_12v"
    states:
      normal: { min: 11.4, max: 12.6 }
      under_voltage: { max: 10.8 }
      over_voltage: { min: 13.2 }
      missing: { max: 0.5 }

faults:
  - fault_id: "output_rail_collapse"
    name: "Output Rail Collapse"
    signatures:
      - signal_id: "output_12v"
        state: "missing"
    recovery:
      - step: 1
        action: "inspect"
        target: "Input fuse F1"
        instruction: "Check fuse continuity"
        safety: "Disconnect AC power before inspection"
```

### 6.5 Mock Mode for Testing

```bash
# Run with default scenario
python -m src.interfaces.cli --mock

# Run specific scenario
python -m src.interfaces.cli --mock cctv-psu-overvoltage
```

**Available Scenarios**:
- cctv-psu-output-rail: Output voltage collapsed
- cctv-psu-overvoltage: Output exceeded 24V
- cctv-psu-ripple: Excessive ripple voltage  
- cctv-psu-thermal: Thermal shutdown condition

---

## 7. Quick Reference for AI Agents

When working with this codebase:

### 7.1 Entry Points

- **Main LangGraph**: src/studio/conversational_agent.py -> graph() function
- **Tools**: src/studio/tools.py - defined with @tool decorator
- **Equipment configs**: data/equipment/*.yaml
- **RAG data**: data/knowledge/*.md - run scripts/ingest_knowledge.py to update

### 7.2 State Management

- **Messages**: Uses add_messages reducer - messages are automatically merged
- **Session continuity**: Uses MemorySaver checkpointer with thread_id from config
- **Important**: Don't manually append to messages - return new list for add_messages to handle

### 7.3 Environment Variables

Required in .env:
- GROQ_API_KEY - Required for LLM
- LLM_PROVIDER=groq
- LLM_MODEL=llama-3.3-70b-versatile

Optional:
- LANGCHAIN_API_KEY - For LangSmith tracing
- APP_MODE - mock/live/usb

### 7.4 Key Classes and Functions

```python
# State definition (src/studio/conversational_agent.py)
@dataclass
class ConversationalAgentState:
    messages: Annotated[list[BaseMessage], add_messages]
    equipment_model: str
    initial_problem: str
    collected_measurements: list[dict]
    workflow_phase: Literal["initial", "clarifying", "measuring", "diagnosing", "complete"]

# Tool definitions (src/studio/tools.py)
@tool
def query_diagnostic_knowledge(query: str, equipment_model: str, ...) -> dict

@tool  
def get_equipment_configuration(equipment_model: str, request_type: str) -> dict

@tool
def read_multimeter(test_point_id: str, measurement_type: str, timeout: float) -> dict

@tool
def enter_manual_reading(test_point_id: str, value: float, unit: str, ...) -> dict

# Equipment config (src/infrastructure/equipment_config.py)
def get_equipment_config(equipment_id: str) -> EquipmentConfig
```

### 7.5 Debugging Tips

- Enable LangSmith tracing with LANGCHAIN_TRACING=true in .env
- Check ChromaDB is running: docker ps should show chroma container
- Test USB connection: python test_usb_multimeter.py
- View raw serial data: python log_raw_data.py

---

## 8. Project Structure

```
ai-agent/
├── .env.example                    # Environment template
├── .gitignore                      
├── README.md                        # Main project README
├── langgraph.json                   # LangGraph Studio config
├── docker-compose.yml               # Docker services
├── requirements.txt                 # Python dependencies
├── start-services.ps1              # Windows startup
├── start-services.sh               # Linux/macOS startup
│
├── data/
│   ├── chromadb/                   # Persisted vector DB
│   ├── equipment/                  # Equipment YAML configs
│   │   └── cctv-psu-24w-v1.yaml
│   ├── knowledge/                   # RAG source docs
│   │   └── cctv-psu-24w-v1-diagnostics.md
│   └── mock_signals/               # Test scenarios
│       └── scenarios.json
│
├── src/
│   ├── studio/                      # LangGraph Studio components
│   │   ├── conversational_agent.py # Main graph & state
│   │   ├── tools.py                # LangChain tools
│   │   ├── background_usb_reader.py# USB reading thread
│   │   └── langgraph_studio.py     # Entry point
│   │
│   ├── infrastructure/             # External integrations
│   │   ├── usb_multimeter.py       # Serial comm
│   │   ├── chromadb_client.py      # Vector DB
│   │   ├── rag_repository.py       # RAG retrieval
│   │   ├── equipment_config.py     # YAML loader
│   │   └── llm_client.py           # LLM factory
│   │
│   ├── application/                 # Core agent logic
│   │   └── agent.py                # Diagnostic workflow
│   │
│   ├── domain/                      # Business models
│   │   └── models.py               # Data classes
│   │
│   └── interfaces/                  # User interfaces
│       ├── cli.py                   # Command-line
│       └── mode_router.py           # Mode switching
│
├── scripts/                         # Utility scripts
│   └── ingest_knowledge.py         # RAG ingestion
│
├── docs/                            # Documentation
│   └── PROJECT_AI_DOCUMENTATION.md # This file
│
└── tests/                           # Test suite
    └── ...
```

---

## 9. Available Equipment and Faults

### 9.1 CCTV PSU 24W (cctv-psu-24w-v1)

**Test Points**:
| ID | Name | Location | Normal Value |
|----|------|----------|--------------|
| AC_IN | AC Input | Terminal block | 230V AC |
| TP1 | Bridge Output | Primary side | 280-380V DC |
| TP2 | 12V Output | Output rail | 11.4-12.6V DC |
| TP3 | Feedback Ref | U5 vicinity | 2.4-2.6V DC |
| F1 | Input Fuse | Primary | <0.1 ohms |
| R2 | Feedback Resistor | Secondary | 465-475 ohms |
| C12 | Output Capacitor | Secondary | <0.2 ohms ESR |

**Defined Faults**:
1. output_rail_collapse - 12V output collapsed (Priority 1)
2. primary_side_failure - AC input not reaching primary (Priority 2)
3. excessive_ripple - Output ripple exceeds spec (Priority 3)
4. overvoltage_output - 12V exceeds safe maximum (Priority 4)
5. thermal_shutdown - Unit shuts down after warmup (Priority 5)

---

## 10. Troubleshooting Common Issues

| Issue | Solution |
|-------|----------|
| ChromaDB not responding | Run docker start (container_name) |
| LLM errors | Check GROQ_API_KEY in .env |
| LangSmith not working | Verify LANGCHAIN_API_KEY |
| USB multimeter not detected | Check COM port, try different baud rate |
| No RAG results | Run python scripts/ingest_knowledge.py |

---

*End of Documentation*
