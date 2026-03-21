# Project Specification

> What this project is and what it aims to achieve (product-level understanding)

---

## Problem Statement

### The Challenge

Biomedical and electronic equipment troubleshooting requires specialized knowledge that:
- Takes years of training to develop
- Is often held by few experienced technicians
- Is difficult to document and transfer
- Becomes a single point of failure in operations

### The Solution

An AI-powered **step-by-step diagnostic engine** that:
- **Guides technicians through structured diagnostics**: Each step is atomic and explicit
- **Waits between steps**: Uses interrupt system for user control
- **Provides real-time diagnostics**: Interprets live electrical measurements via USB
- **Delivers evidence-based recommendations**: Uses RAG to ground decisions in documentation
- **Works continuously**: No fatigue, consistent results, 24/7 availability

---

## Core Concept: Step-by-Step Diagnostic Engine

### NOT a Chatbot

The system is fundamentally different from conversational chatbots:

| Chatbot Approach | Diagnostic Engine Approach |
|------------------|---------------------------|
| Free-form conversation | Structured workflow steps |
| Continuous flow | Interrupt between each step |
| User decides what to do next | System guides, user confirms "Next" |
| Hallsucinates freely | RAG-grounded evidence |
| Ad-hoc measurements | Stabilized readings with algorithm |

### Atomic Diagnostic Step (STEP)

Each diagnostic step is an ATOMIC unit that performs 9 sub-operations:

```
1. SHOW TEST POINT       → Display test point name
2. SHOW PROBE PLACEMENT → Show probe placement instructions
3. SHOW IMAGE            → Show exactly ONE image
4. CALL READ_MULTIMETER → Call read_multimeter function
5. STABILIZE             → Stabilize measurement using algorithm
6. EVALUATE              → Evaluate against expected values
7. REASON                → Reason about the result
8. EXPLAIN TO USER       → Measured value, expected value, interpretation, conclusion
9. DECIDE NEXT ACTION    → Fault confirmed → REPAIR, or more tests needed → INTERRUPT
```

**INTERRUPT happens AFTER the full step completes**, not before measurement.

---

## Target Users

| User Type | Use Case | Pain Points Solved |
|-----------|----------|-------------------|
| Field Technicians | On-site equipment diagnostics | No need to memorize all fault patterns |
| Maintenance Engineers | Preventive maintenance | Early detection of anomalies |
| Support Teams | Remote diagnostics | Faster triage without physical presence |
| Training AI | Learning from expert decisions | Capture and codify tribal knowledge |

---

## Core Features

### 1. RAG-Driven Diagnostic Logic
**What it does**: Queries ChromaDB for diagnostic guidance

- Retrieves relevant diagnostic procedures from knowledge base
- Grounds all decisions in equipment documentation
- Prevents hallucinations by requiring RAG evidence

### 2. Hypothesis-Driven Workflow
**What it does**: Generates ordered list of fault hypotheses

- Uses symptoms to generate initial hypothesis list
- Prioritizes by equipment-specific fault priority
- Eliminates hypotheses through measurement

### 3. Interrupt-Based Step Control
**What it does**: Pauses between diagnostic steps

- Uses `langgraph.types.interrupt()` to pause workflow
- Displays test point, image, and instructions
- Waits for user "Next" before measurement
- Prevents autonomous measurement without human oversight

### 4. Stabilized Multimeter Reading
**What it does**: Extracts stable readings from noisy measurements

- Rolling window stability detection (10 samples)
- Trimmed mean filtering (10% top/bottom)
- Cluster detection for outlier identification
- Zero reading validation

### 5. Evidence-Based Evaluation
**What it does**: Compares measurements against expected values

- Parses expected value ranges from equipment config
- Determines if measurement confirms or eliminates hypothesis
- Provides clear conclusion: "FAULT CONFIRMED" or "Normal"

---

## Diagnostic Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CORRECTED DIAGNOSTIC WORKFLOW                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────┐    ┌─────────┐    ┌───────────┐    ┌────────────┐           │
│   │   RAG   │───▶│  PLAN   │───▶│   STEP    │───▶│  DECISION  │           │
│   │  NODE   │    │  NODE   │    │   NODE    │    │   NODE     │           │
│   └─────────┘    └─────────┘    └─────┬─────┘    └──────┬─────┘           │
│        ▲                               │                │                 │
│        │                               │                │                 │
│        │                               │     ┌──────────┴──────────┐      │
│        │                               │     │                     │      │
│        │                               │     ▼                     ▼      │
│        │                               │  ┌────────────┐    ┌────────────┐  │
│        │                               │  │   FAULT    │    │ MORE TESTS │  │
│        │                               │  │ CONFIRMED  │    │   NEEDED   │  │
│        │                               │  └─────┬──────┘    └─────┬──────┘  │
│        │                               │        │                │         │
│        │                               │        ▼                ▼         │
│        │                               │  ┌────────────┐    ┌──────────┐   │
│        │                               │  │   REPAIR   │    │ INTERRUPT│   │
│        │                               │  │   NODE     │    │   NODE   │   │
│        │                               │  └────────────┘    └─────┬──────┘   │
│        │                               │                         │          │
│        │                               │                         ▼          │
│        │                               │                  ┌────────────┐    │
│        │                               │                  │  Wait for  │    │
│        │                               │                  │   "NEXT"   │    │
│        │                               │                  └─────┬──────┘    │
│        │                               │                        │           │
│        │                               │                        ▼           │
│        │                               │   ┌────────────────────────┐         │
│        │                               └───│    Continue to next   │         │
│        │                                   │    STEP (from PLAN)   │         │
│        │                                   └────────────────────────┘         │
│        │                                                                      │
│        └─────────────────────── (loop back for more tests)                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Corrections:**
- STEP is an atomic unit that includes: show test point, show image, measure, stabilize, evaluate, reason, explain
- DECISION node determines: FAULT CONFIRMED → REPAIR, or MORE TESTS → INTERRUPT
- **INTERRUPT happens AFTER STEP completes**, not before measurement
- After INTERRUPT, user presses NEXT → continues to next STEP

---

## Data Collection Method

### USB Automatic Data Collection

The system automatically collects measurement data via USB from the **Mastech MS8250D Digital Multimeter**:
- **Connection**: CP210x USB-to-Serial adapter
- **Protocol**: UART @ 2400 baud
- **Auto-detection**: Automatically identifies COM port

The multimeter continuously streams measurements which the system stabilizes before interpretation.

---

## Multimeter Stabilization Algorithm

The new [`MultimeterStabilizer`](src/infrastructure/multimeter_stabilizer.py:21) class implements:

1. **Rolling Window**: Maintain 10 most recent samples
2. **Stability Check**: Standard deviation < 1% of mean
3. **Trimmed Mean**: Remove top/bottom 10% if unstable
4. **Cluster Detection**: Group values within ±5%, select largest cluster
5. **Zero Validation**: Majority rule for zero readings

---

## Business Logic Overview

### Hybrid Intelligence Model

The system combines two diagnostic approaches:

1. **Deterministic (Rule-based)**
   - Exact threshold matching from YAML
   - Known fault signatures
   - Fast, reliable, explainable

2. **Probabilistic (LLM-based)**
   - Complex pattern recognition
   - Novel fault scenarios
   - Nuanced reasoning from RAG context

The system uses deterministic first, then LLM for ambiguous cases.

---

## Equipment Support

### Currently Supported
- **CCTV Power Supply Unit (SP-80M / CCTV-PSU-24W-V1)**
  - Test points: AC input, output rail, fuse, ground
  - Faults: overvoltage, undervoltage, ripple, thermal, output failure

### Extensibility
New equipment can be added by:
1. Creating a YAML file in [`data/equipment/`](data/equipment/)
2. Defining test_points with thresholds
3. Defining fault signatures with hypotheses
4. Defining recovery procedures
5. Adding documentation to [`data/knowledge/`](data/knowledge/)

---

## User Interactions

### LangGraph Studio Mode
```bash
# Start studio
langgraph dev --port 2024

# Open browser to interact with agent visually
# View traces, replay decisions, debug workflow
```

### Step-by-Step Flow

1. **System displays**: Test point name, image, probe instructions, expected value
2. **System interrupts**: "Press Next when ready to measure"
3. **User presses Next**: System takes stabilized measurement
4. **System evaluates**: Compares to expected, provides conclusion
5. **Decision**:
   - Fault confirmed → Show repair steps
   - Need more tests → Loop to RAG for next hypothesis

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Fault detection accuracy | >90% | N/A (requires validation) |
| Evidence grounding | 100% RAG | ✅ Implemented |
| Step-by-step control | Interrupt per step | ✅ Implemented |
| Measurement stability | <1% std dev | ✅ Implemented |
| Response time (mock) | <5s | ✅ Implemented |
| Equipment extensibility | YAML-driven | ✅ Implemented |

---

## Out of Scope (v1)

- [ ] Web interface (future)
- [ ] Cloud deployment (future)
- [ ] Multi-equipment batch processing (future)
- [ ] Predictive maintenance analytics (future)
- [ ] Warranty/contract integration (future)

---

## Future Enhancements

1. **Web Interface**: React-based UI for non-technical users
2. **Multi-equipment Support**: Expand beyond CCTV PSUs
3. **Historical Analysis**: Track equipment health over time
4. **Collaborative Diagnosis**: Multiple agents working together
