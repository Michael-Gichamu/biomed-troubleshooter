# LangGraph Agent Design Document

> **Document Version:** 1.0  
> **Last Updated:** 2026-02-03  
> **Purpose:** Design the LangGraph workflow for biomedical equipment troubleshooting agent

---

## 1. Graph Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ENTRY POINT                                     │
│                           (User Input Received)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  validate_input                                                                │
│  ──────────────────────────────────────────────────────────────────────────  │
│  • Validate JSON schema                                                       │
│  • Check required fields                                                      │
│  • Route to appropriate workflow                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                           │
                    │ Invalid                   │ Valid
                    ▼                           ▼
           ┌─────────────────┐         ┌─────────────────────┐
           │  return_error   │         │  interpret_signals  │
           └─────────────────┘         └─────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │  retrieve_knowledge │
                                    │  (RAG Query)        │
                                    └─────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │  analyze_fault      │
                                    │  (Core Reasoning)   │
                                    └─────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │  generate_response  │
                                    │  (Output Formatting)│
                                    └─────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │    END (Response)   │
                                    └─────────────────────┘
```

---

## 2. Node Definitions

### 2.1 `validate_input`

**Purpose:** Sanity-check incoming requests before expensive processing.

**What it does:**
1. Validates JSON structure against input schema
2. Checks all required fields are present
3. Verifies signal data has minimum required test points
4. Routes to appropriate workflow (initial diagnosis vs. follow-up)

**Output:**
- `status`: "valid" | "invalid"
- `error_message`: string (if invalid)
- `workflow_type`: "initial" | "follow_up" | "verification"

**Failure Modes:**
| Failure | Symptom | Debug Action |
|---------|---------|--------------|
| JSON parse error | Cannot decode request | Check request format |
| Missing equipment_id | No model/serial specified | Return "equipment required" error |
| Empty signals array | User submitted no measurements | Prompt for signal data |
| Invalid timestamp | Malformed ISO 8601 | Return "timestamp format error" |

---

### 2.2 `return_error`

**Purpose:** Return user-friendly error messages without crashing.

**What it does:**
1. Translates technical errors to user-friendly messages
2. Suggests next steps for recovery
3. Logs error for debugging

**Output:**
- `error_type`: string
- `user_message`: string
- `suggested_action`: string

**Failure Modes:**
| Failure | Symptom | Debug Action |
|---------|---------|--------------|
| Missing error template | Generic "error occurred" | Add error message mapping |
| Circular error reference | Infinite error loop | Check error routing logic |

---

### 2.3 `interpret_signals`

**Purpose:** Convert raw measurement numbers into semantic states.

**What it does:**
1. Looks up threshold profile for the equipment model
2. Maps each raw measurement to a semantic state (normal, missing, overvoltage, etc.)
3. Identifies anomalies and prioritizes by severity
4. Builds the `observed_signals` section of the output

**Output:**
- `observed_signals`: Object containing:
  - `interpretation`: string (summary)
  - `anomalies`: Array of {test_point, expected, measured, severity}
  - `status`: "normal" | "degraded" | "failed"
  - `state_mapping`: Array of {signal_id, raw_value, semantic_state}

**Failure Modes:**
| Failure | Symptom | Debug Action |
|---------|---------|--------------|
| Missing threshold profile | "unknown" state for all signals | Check ChromaDB for equipment profile |
| Hysteresis flapping | State toggles rapidly | Adjust hysteresis bands |
| Out-of-range value | All values marked "unknown" | Verify threshold config for edge cases |

---

### 2.4 `retrieve_knowledge`

**Purpose:** Query RAG for relevant troubleshooting documentation.

**What it does:**
1. Constructs query from symptom description + anomalous signals
2. Queries ChromaDB for relevant documents
3. Ranks results by relevance score
4. Returns top-K snippets with metadata

**Output:**
- `retrieved_docs`: Array of {doc_id, title, content, relevance_score}
- `query_string`: string (the actual query sent to RAG)
- `doc_count`: integer (number of documents retrieved)

**Failure Modes:**
| Failure | Symptom | Debug Action |
|---------|---------|--------------|
| ChromaDB connection error | Empty results | Check ChromaDB service |
| No relevant docs | Low relevance scores | Improve RAG chunking |
| Timeout | Request hangs >30s | Add query timeout |

---

### 2.5 `analyze_fault`

**Purpose:** Core reasoning engine - generate fault hypothesis from signals + knowledge.

**What it does:**
1. Synthesizes semantic signal states with RAG knowledge
2. Builds reasoning chain step-by-step
3. Generates primary fault hypothesis with confidence score
4. Creates differential diagnoses (alternative causes)
5. Determines next diagnostic action

**Output:**
- `fault_hypothesis`: Object containing:
  - `primary_cause`: string
  - `confidence`: number (0.0-1.0)
  - `supporting_evidence`: Array of strings
  - `contradicting_evidence`: Array of strings
  - `differential_diagnoses`: Array of {cause, probability, key_differentiator}
- `reasoning_chain`: Array of {step, observation, inference, source}
- `next_action`: Object {action, target, instruction, expected_result, priority}

**Failure Modes:**
| Failure | Symptom | Debug Action |
|---------|---------|--------------|
| No matching diagnosis | Confidence = 0.0 | Check RAG retrieval quality |
| Conflicting evidence ignored | Diagnosis contradicts signals | Verify evidence weighting |
| Reasoning chain incomplete | Missing steps in chain | Check chain-building logic |

---

### 2.6 `generate_response`

**Purpose:** Format the final structured output per I/O contract.

**What it does:**
1. Assembles all computed fields into final output structure
2. Validates output against JSON schema
3. Adds metadata (version, timestamp, processing_time)
4. Ensures all required fields are present

**Output:**
- Complete agent output conforming to [`docs/agent_io_contract.md`](docs/agent_io_contract.md)

**Failure Modes:**
| Failure | Symptom | Debug Action |
|---------|---------|--------------|
| Missing required field | Output schema validation fails | Check all output sections |
| Invalid confidence | Value > 1.0 or NaN | Add confidence clamp |
| Timestamp format error | ISO 8601 validation fails | Use standardized timestamp |

---

## 3. Shared State Object

```typescript
interface AgentState {
  // === INPUT ===
  raw_input: {
    trigger: {
      type: string;
      content: string;
      urgency: string;
    };
    signals: {
      equipment_id: string;
      measurements: any[];
    };
    context: {
      retrieved_docs: any[];
      conversation_history: any[];
    };
  };

  // === VALIDATION ===
  validation: {
    is_valid: boolean;
    error_message?: string;
    workflow_type: "initial" | "follow_up" | "verification";
  };

  // === SIGNAL INTERPRETATION ===
  signal_interpretation: {
    observed_signals: {
      interpretation: string;
      anomalies: Array<{
        test_point: string;
        expected: string;
        measured: string;
        severity: "critical" | "warning" | "minor";
      }>;
      status: "normal" | "degraded" | "failed";
    };
    state_mapping: Array<{
      signal_id: string;
      raw_value: number;
      semantic_state: string;
    }>;
  };

  // === RAG RETRIEVAL ===
  knowledge_retrieval: {
    query_string: string;
    retrieved_docs: Array<{
      doc_id: string;
      title: string;
      content: string;
      relevance_score: number;
    }>;
  };

  // === FAULT ANALYSIS ===
  fault_analysis: {
    fault_hypothesis: {
      primary_cause: string;
      confidence: number;
      supporting_evidence: string[];
      contradicting_evidence: string[];
      differential_diagnoses: Array<{
        cause: string;
        probability: number;
        key_differentiator: string;
      }>;
    };
    reasoning_chain: Array<{
      step: number;
      observation: string;
      inference: string;
      source: "signal" | "documentation" | "logic";
    }>;
    next_action: {
      action: "measure" | "inspect" | "replace" | "verify" | "escalate";
      target: string;
      instruction: string;
      expected_result: string;
      priority: "critical" | "high" | "medium" | "low";
    };
  };

  // === OUTPUT ===
  output: {
    // Populated by generate_response node
  };

  // === METADATA ===
  metadata: {
    version: string;
    timestamp: string;
    equipment_id: string;
    processing_time_ms: number;
    node_history: string[];
    errors: string[];
  };
}
```

**State Flow:**

```
Entry → validate_input → [state.validation]
                              │
                              ├── Invalid → return_error → END
                              │
                              └── Valid → interpret_signals → [state.signal_interpretation]
                                                      │
                                                      ▼
                                              retrieve_knowledge → [state.knowledge_retrieval]
                                                      │
                                                      ▼
                                              analyze_fault → [state.fault_analysis]
                                                      │
                                                      ▼
                                              generate_response → [state.output]
                                                      │
                                                      ▼
                                              END
```

---

## 4. Entry/Exit Conditions

### Entry Conditions
- User submits JSON matching input schema
- At least one signal measurement present
- Equipment identifier specified

### Exit Conditions
- `generate_response` completes successfully
- All output schema fields validated
- Response returned to user

### Retry/Recovery
- Input validation failures → `return_error` (no retry)
- RAG timeout → retry once with simplified query
- Analysis failures → return partial result with `confidence: 0.0`

---

## 5. Testing Strategy

| Node | Test Focus |
|------|------------|
| validate_input | Schema validation, edge cases, error messages |
| interpret_signals | Threshold mapping, state transitions, hysteresis |
| retrieve_knowledge | Query construction, relevance ranking, timeout handling |
| analyze_fault | Reasoning chain completeness, confidence calibration |
| generate_response | Schema compliance, field completeness |

---

## 6. Next Steps

1. Implement each node as a Python function using LangGraph `@node` decorator
2. Define state object as Pydantic model for validation
3. Build graph with StateGraph class
4. Add unit tests for each node in isolation
5. Integration test with mock signal scenarios
