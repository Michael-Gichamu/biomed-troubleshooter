# Biomedical Equipment Signal Schema

> **Document Version:** 1.0  
> **Last Updated:** 2026-02-03  
> **Purpose:** Define signal representation, semantic state mapping, and reasoning approach for the troubleshooting agent

---

## 1. SIGNAL SCHEMA

### 1.1 Raw Signal Definition

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["signal_id", "test_point", "parameter", "value", "unit", "timestamp"],
  "properties": {
    "signal_id": {
      "type": "string",
      "pattern": "^SIG-[A-Z0-9]{8}$",
      "description": "Unique identifier for signal provenance tracking"
    },
    "test_point": {
      "type": "object",
      "required": ["id", "name", "location"],
      "properties": {
        "id": { "type": "string" },
        "name": { "type": "string", "description": "Human-readable label e.g., 'TP12 - Output 12V'" },
        "location": { "type": "string", "description": "Board location e.g., 'U12 Pin 3'" },
        "component_id": { "type": "string", "description": "Associated component e.g., 'C4'" }
      }
    },
    "parameter": {
      "type": "string",
      "enum": [
        "voltage_dc", "voltage_ac", "voltage_rms",
        "current", "resistance", "impedance",
        "power_real", "power_apparent", "power_reactive",
        "frequency", "duty_cycle", "rise_time", "fall_time",
        "temperature", "pressure", "humidity"
      ]
    },
    "value": { "type": "number" },
    "unit": {
      "type": "string",
      "enum": ["V", "mV", "A", "mA", "Ω", "kΩ", "W", "mW", "Hz", "kHz", "°C", "%RH"]
    },
    "accuracy": {
      "type": "object",
      "properties": {
        "tolerance": { "type": "number", "description": "± percentage" },
        "instrument_error": { "type": "number", "description": "± absolute value in unit" }
      }
    },
    "timestamp": { "type": "string", "format": "date-time" },
    "instrument": {
      "type": "object",
      "properties": {
        "model": { "type": "string" },
        "id": { "type": "string" },
        "calibration_date": { "type": "string", "format": "date" }
      }
    },
    "measurement_conditions": {
      "type": "object",
      "properties": {
        "load_state": { "type": "string", "enum": ["no_load", "nominal_load", "full_load", "overload"] },
        "power_state": { "type": "string", "enum": ["off", "standby", "on", "operating"] },
        "ambient_temp": { "type": "number", "unit": "°C" }
      }
    }
  }
}
```

### 1.2 Raw Signal Example

```json
{
  "signal_id": "SIG-A1B2C3D4",
  "test_point": {
    "id": "TP12",
    "name": "Output 12V Rail",
    "location": "U5 Pin 4",
    "component_id": "C12"
  },
  "parameter": "voltage_dc",
  "value": 11.2,
  "unit": "V",
  "accuracy": { "tolerance": 5, "instrument_error": 0.05 },
  "timestamp": "2026-02-03T08:15:00Z",
  "instrument": {
    "model": "Fluke 87V",
    "id": "FLUKE-001",
    "calibration_date": "2025-06-15"
  },
  "measurement_conditions": {
    "load_state": "nominal_load",
    "power_state": "operating",
    "ambient_temp": 23
  }
}
```

---

## 2. SEMANTIC STATE MAPPING

### 2.1 State Definition Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["signal_id", "semantic_state", "raw_value", "threshold_profile"],
  "properties": {
    "signal_id": { "type": "string" },
    "semantic_state": {
      "type": "string",
      "enum": [
        "normal",
        "degraded",
        "out_of_spec_low",
        "out_of_spec_high",
        "missing",
        "noisy",
        "intermittent",
        "shorted",
        "open_circuit",
        "unknown"
      ]
    },
    "raw_value": { "type": "number" },
    "unit": { "type": "string" },
    "threshold_profile": { "type": "string", "description": "Reference to threshold set used" },
    "state_transition": {
      "type": "object",
      "properties": {
        "previous_state": { "type": "string" },
        "triggered_at": { "type": "string", "format": "date-time" },
        "duration_ms": { "type": "integer" }
      }
    },
    "interpretation": { "type": "string", "description": "What this state means for the system" },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
  }
}
```

### 2.2 Threshold Configuration

```json
{
  "voltage_dc_12v_rail": {
    "parameter": "voltage_dc",
    "nominal_value": 12.0,
    "unit": "V",
    "thresholds": {
      "normal": { "min": 11.4, "max": 12.6 },
      "degraded": { "min": 10.8, "max": 13.2 },
      "out_of_spec_low": { "min": 10.0, "max": null },
      "out_of_spec_high": { "min": null, "max": 14.0 },
      "missing": { "max": 0.5 }
    }
  },
  "voltage_ac_input": {
    "parameter": "voltage_rms",
    "nominal_value": 230.0,
    "unit": "V",
    "thresholds": {
      "normal": { "min": 207, "max": 253 },
      "degraded": { "min": 185, "max": 275 },
      "out_of_spec_low": { "min": null, "max": 170 },
      "out_of_spec_high": { "min": 280, "max": null }
    }
  },
  "current_output": {
    "parameter": "current",
    "nominal_value": 2.0,
    "unit": "A",
    "thresholds": {
      "normal": { "min": 0, "max": 2.0 },
      "overload": { "min": 2.0, "max": 2.5 },
      "overcurrent": { "min": 2.5, "max": null }
    }
  }
}
```

### 2.3 Semantic State Examples

| Raw Value | Unit | Semantic State | Interpretation |
|-----------|------|----------------|----------------|
| 11.8 | V | `normal` | 12V rail operating within ±5% tolerance |
| 10.5 | V | `degraded` | 12V rail below spec but still functional; likely loading issue |
| 8.2 | V | `out_of_spec_low` | 12V rail significantly undervoltage; may cause intermittent failures |
| 0.1 | V | `missing` | 12V rail collapsed; likely short, failed regulator, or no power |
| 14.1 | V | `out_of_spec_high` | 12V rail overvoltage; regulator failure or loose feedback |
| 2.3 | A | `overload` | Drawing 115% of rated current; thermal stress likely |
| 2.8 | A | `overcurrent` | Drawing 140% of rated current; imminent failure likely |
| OL | Ω | `open_circuit` | Infinite resistance indicates open component |
| 0.01 | Ω | `shorted` | Near-zero resistance indicates shorted component |

---

## 3. WHY SEMANTIC STATES, NOT RAW NUMBERS

### 3.1 The Abstraction Principle

The agent MUST reason on **semantic states** (e.g., "5V rail missing") rather than **raw numbers** (e.g., "0.03V"). This is a deliberate architectural decision with engineering justification.

### 3.2 Reasons for Semantic State Reasoning

| Reason | Explanation |
|--------|-------------|
| **Equipment Independence** | Raw thresholds vary by equipment model. Semantic states ("normal", "missing") abstract the specific numbers. The agent can troubleshoot any PSU with the same state vocabulary. |
| **Noise Robustness** | Real measurements have noise, drift, and instrument error. Raw values fluctuate; semantic states with hysteresis are stable. |
| **RAG Alignment** | Knowledge base documentation uses semantic language ("output is missing", "rail is low"). Matching semantic-to-semantic is more reliable than numeric-to-text. |
| **Decision Clarity** | "Overcurrent condition" clearly indicates a failure mode. "2.8A" requires the agent to know that 2.8A is overcurrent for this specific equipment. |
| **Confidence Calibration** | State transitions can be tracked over time. "Missing for 30 seconds" vs. "spike to missing" have different confidence implications. |
| **Multi-Source Fusion** | When combining signals from multiple instruments, semantic states are easier to fuse than raw numbers with different scales/units. |

### 3.3 Failure Mode Example

**Raw Number Approach (Problematic):**
```
Input: TP12 = 0.03V
Agent must infer: "This means the 12V rail is missing"
Problem: Agent must know 0.03V ≈ 0V for this equipment. 
         Different equipment might have 0.1V as "normal idle".
```

**Semantic State Approach (Robust):**
```
Input: TP12 = 0.03V → State: "missing" (threshold < 0.5V)
Agent reasoning: "12V rail is missing"
Benefit: State mapping is equipment-configurable. 
         Agent uses consistent vocabulary regardless of specific thresholds.
```

### 3.4 State Transition Reasoning

Semantic states enable temporal reasoning:

```json
{
  "signal_id": "SIG-12345678",
  "state_history": [
    { "state": "normal", "timestamp": "2026-02-03T08:00:00Z" },
    { "state": "degraded", "timestamp": "2026-02-03T08:05:00Z" },
    { "state": "out_of_spec_low", "timestamp": "2026-02-03T08:07:00Z" },
    { "state": "missing", "timestamp": "2026-02-03T08:10:00Z" }
  ],
  "agent_reasoning": "Gradual degradation over 10 minutes suggests thermal failure, 
                      not instantaneous short. Check for failing capacitor or 
                      thermally-sensitive component."
}
```

---

## 4. THRESHOLD MANAGEMENT

### 4.1 Threshold Sources (Priority Order)

1. **Equipment Specification** (highest priority): Datasheet nominals and tolerances
2. **Service Manual**: Published service procedures with pass/fail criteria
3. **Historical Data**: Learned baselines from healthy equipment
4. **Factory Defaults**: Fallback generic thresholds

### 4.2 Threshold Hysteresis

To prevent flapping between states:

```
                  ┌─────────────────────────────────────┐
    out_of_spec ──┤  hysteresis band (e.g., 5% of range) ├── normal
                  └─────────────────────────────────────┘

For 12V rail:
- Upper normal bound: 12.6V
- Lower out_of_spec_high: 12.6V
- Lower normal bound: 11.4V  
- Upper out_of_spec_low: 11.4V - (0.12V hysteresis) = 11.28V
```

### 4.3 Unknown State Handling

When signal cannot be interpreted:

```json
{
  "signal_id": "SIG-UNKNOWN",
  "semantic_state": "unknown",
  "interpretation": "Value 847.3 Hz does not match any configured threshold profile for parameter frequency",
  "confidence": 0.1,
  "agent_action": "Request clarification from user: 'What is the expected frequency at this test point?'"
}
```

---

## 5. SIGNAL FLOW IN AGENT

```
Raw Measurement → Threshold Mapping → Semantic State → RAG Query → Diagnosis
     (0.03V)          (missing)         ("12V rail        (symptom        (component
                                         missing")        match)           failure)")
```

The agent's reasoning chain always operates on the **rightmost column**. Raw values are an implementation detail; semantic states are the agent's cognitive model.
