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

An AI-powered diagnostic agent that:
- **Automates troubleshooting**: Reduces dependency on expert technicians
- **Provides real-time diagnostics**: Interprets live electrical measurements via USB
- **Delivers evidence-based recommendations**: Uses RAG to ground decisions in documentation
- **Works continuously**: No fatigue, consistent results, 24/7 availability

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

### 1. Signal Interpretation
**What it does**: Converts raw electrical measurements into semantic states

- Reads voltage, current, resistance from Mastech MS8250D multimeter via USB
- Maps against equipment-specific thresholds from YAML
- Returns: `normal`, `over_voltage`, `under_voltage`, `missing`, `short_circuit`, etc.

**Example**:
```
Input:  { "test_point": "output_rail", "value": 28.5, "unit": "V" }
Output: { "state": "over_voltage", "severity": "high", "threshold_exceeded": 4.5 }
```

### 2. Fault Analysis
**What it does**: Identifies root cause from signal patterns

- Matches signal anomaly patterns against known fault signatures
- Uses LLM for complex reasoning when patterns are ambiguous
- Returns: fault hypothesis with confidence score

### 3. Evidence Retrieval
**What it does**: Grounds diagnosis in equipment documentation

- Queries ChromaDB vector store (embedded mode) with semantic search
- Retrieves relevant diagnostic procedures
- Returns: supporting evidence for the diagnosis

### 4. Recovery Recommendations
**What it does**: Provides actionable repair instructions

- Loads step-by-step recovery procedures from YAML
- Chains multiple recovery steps based on fault type
- Returns: prioritized list of actions with instructions

---

## Data Collection Method

### USB Automatic Data Collection

The system automatically collects measurement data via USB from the **Mastech MS8250D Digital Multimeter**:
- **Connection**: CP210x USB-to-Serial adapter
- **Protocol**: UART @ 2400 baud
- **Auto-detection**: Automatically identifies COM port

The multimeter continuously streams measurements which the system interprets in real-time.

---

## Business Logic Overview

### Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Raw         │     │ Signal           │     │ Fault           │
│ Measurements│────▶│ Interpretation   │────▶│ Analysis        │
│ (USB)       │     │ (thresholds)     │     │ (LLM + rules)   │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Recovery    │◀────│ Recommendations │◀────│ Evidence        │
│ Actions     │     │ Generation       │     │ Retrieval (RAG)│
└─────────────┘     └──────────────────┘     └─────────────────┘
```

### Hybrid Intelligence Model

The system combines two diagnostic approaches:

1. **Deterministic (Rule-based)**
   - Exact threshold matching
   - Known fault signatures
   - Fast, reliable, explainable

2. **Probabilistic (LLM-based)**
   - Complex pattern recognition
   - Novel fault scenarios
   - Nuanced reasoning

The system tries deterministic first, then escalates to LLM for ambiguous cases.

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
3. Defining fault signatures
4. Defining recovery procedures
5. Adding documentation to [`data/knowledge/`](data/knowledge/)

---

## User Interactions

### CLI Mode
```bash
# Mock diagnosis (no hardware)
python -m src.interfaces.cli --mock

# Real hardware diagnosis via USB
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1
```

### LangGraph Studio Mode
```bash
# Start studio
langgraph dev --port 2024

# Open browser to interact with agent visually
# View traces, replay decisions, debug workflow
```

### Expected Output
```json
{
  "diagnosis": "Output rail overvoltage detected",
  "confidence": 0.92,
  "evidence": [
    "Output voltage measured at 28.5V (threshold: 24V + 10%)",
    "Documentation confirms PSU age > 3 years increases failure risk"
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "Replace Zener diode",
      "instruction": "1. Disconnect power...",
      "safety_warning": "Ensure PSU is unplugged before opening"
    }
  ]
}
```

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Fault detection accuracy | >90% | N/A (requires validation) |
| Evidence grounding | 100% | ✅ Implemented |
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
