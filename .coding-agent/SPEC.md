# Project Specification

> What this project is and what it aims to achieve (product-level understanding)

---

## Problem Statement

### The Challenge

Electronic equipment troubleshooting requires specialized knowledge that:
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

---

## Core Concept: Step-by-Step Diagnostic Engine

### NOT a Chatbot

The system is fundamentally different from conversational chatbots:

| Chatbot Approach | Diagnostic Engine Approach |
|------------------|---------------------------|
| Free-form conversation | Structured workflow steps |
| Continuous flow | Interrupt between each step |
| User decides what to do next | System guides, user confirms "Next" |
| Hallucinates freely | RAG-grounded evidence |
| Ad-hoc measurements | Stabilized readings with algorithm |

### Atomic Diagnostic Step (STEP)

Each diagnostic step is an ATOMIC unit that performs sub-operations:
1. Show test point name and image
2. Show probe placement instructions
3. Take stabilized measurement via USB
4. Evaluate against expected values
5. Reason about the result
6. Explain to user: measured value, expected value, interpretation
7. Decide next action

---

## Target Users

| User Type | Use Case | Pain Points Solved |
|-----------|----------|-------------------|
| Field Technicians | On-site equipment diagnostics | No need to memorize all fault patterns |
| Maintenance Engineers | Preventive maintenance | Early detection of anomalies |
| Support Teams | Remote diagnostics | Faster triage without physical presence |

---

## Core Features

### 1. RAG-Driven Diagnostic Logic
- Queries ChromaDB for diagnostic guidance
- Retrieves relevant diagnostic procedures from knowledge base
- Grounds all decisions in equipment documentation

### 2. Hypothesis-Driven Workflow
- Uses symptoms to generate initial hypothesis list
- Prioritizes by equipment-specific fault priority
- Eliminates hypotheses through measurement

### 3. Interrupt-Based Step Control
- Uses `langgraph.types.interrupt()` to pause workflow
- Displays test point, image, and instructions
- Waits for user "Next" before measurement

### 4. USB Multimode Measurement
- Supports Mastech MS8250D multimeter
- Reads all modes: DCV, ACV, Resistance, Continuity, Diode, Frequency, Capacitance, Current
- Auto-detects COM port

### 5. Stabilized Multimeter Reading
- Rolling window stability detection (10 samples)
- Trimmed mean filtering
- Cluster detection for outlier identification

---

## Diagnostic Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  RAG → HYPOTHESES → STEP → REASON → DECISION              │
│                          │                                  │
│         ┌────────┬───────┴────────┬─────────┐                │
│         ▼        │               │         ▼                │
│   FAULT CONFIRMED    MORE TESTS    │   NEEDED                │
│         │        │               │         │                │
│         ▼        └───────┬───────┘         ▼                │
│      REPAIR              INTERRUPT        │                │
│         │                 (wait NEXT)      │                │
│         └───────────────────┬─────────────┘                │
│                             ▼                              │
│                      STEP (next)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Collection Method

### USB Automatic Data Collection

The system collects measurement data via USB from the **Mastech MS8250D Digital Multimeter**:
- **Connection**: CP210x USB-to-Serial adapter
- **Protocol**: UART @ 2400 baud
- **Auto-detection**: Automatically identifies COM port

---

## Multimode Support

The multimeter infrastructure supports all MS8250D modes:

| Mode | Type Code | Description |
|------|-----------|-------------|
| DC Voltage | DC_VOLTAGE | Direct current voltage |
| AC Voltage | AC_VOLTAGE | Alternating current voltage |
| DC Current | DC_CURRENT | Direct current |
| AC Current | AC_CURRENT | Alternating current |
| Resistance | RESISTANCE | Ohms (Ω) |
| Continuity | CONTINUITY | Beep mode for shorts |
| Diode | DIODE | Diode forward voltage |
| Frequency | FREQUENCY | Hz measurement |
| Capacitance | CAPACITANCE | Farads (F) |

---

## Equipment Support

### Currently Supported
- **CCTV Power Supply Unit (CCTV-PSU-24W-V1)**
  - Test points: AC input, output rail, fuse, ground
  - Faults: overvoltage, undervoltage, ripple, thermal, output failure

### Extensibility
New equipment can be added by:
1. Creating a YAML file in `data/equipment/`
2. Defining test_points with thresholds
3. Defining fault signatures with hypotheses
4. Defining recovery procedures
5. Adding documentation to `data/knowledge/`

---

## User Interactions

### Running the Agent

```bash
# Test multimeter directly
python test_mm.py

# Start LangGraph Studio (Windows)
start.bat
```

### Step-by-Step Flow

1. **System displays**: Test point name, image, probe instructions, expected value
2. **System interrupts**: "Press Next when ready to measure"
3. **User presses Next**: System takes stabilized measurement
4. **System evaluates**: Compares to expected, provides conclusion
5. **Decision**:
   - Fault confirmed → Show repair steps
   - Need more tests → Loop to next hypothesis

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Fault detection accuracy | >90% | N/A (requires validation) |
| Evidence grounding | 100% RAG | ✅ Implemented |
| Step-by-step control | Interrupt per step | ✅ Implemented |
| Measurement stability | <1% std dev | ✅ Implemented |
| Multimode support | All MS8250D modes | ✅ Implemented |

---

## Out of Scope (v1)

- [ ] Web interface (future)
- [ ] Cloud deployment (future)
- [ ] Multi-equipment batch processing (future)
- [ ] Predictive maintenance analytics (future)

---

## Future Enhancements

1. **Web Interface**: React-based UI for non-technical users
2. **Multi-equipment Support**: Expand beyond CCTV PSUs
3. **Historical Analysis**: Track equipment health over time
4. **Collaborative Diagnosis**: Multiple agents working together
