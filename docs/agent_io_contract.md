# AI Agent I/O Contract

> **Document Version:** 1.0  
> **Last Updated:** 2026-02-03  
> **Related:** [`docs/agent_scope.md`](docs/agent_scope.md)

---

## 1. INPUT CONTRACT

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["trigger", "signals", "context"],
  "properties": {
    "trigger": {
      "type": "object",
      "required": ["type", "content"],
      "properties": {
        "type": { "type": "string", "enum": ["symptom_report", "signal_submission", "follow_up", "verification_request"] },
        "content": { "type": "string", "description": "User question or natural language description" },
        "urgency": { "type": "string", "enum": ["low", "normal", "high", "critical"], "default": "normal" }
      }
    },
    "signals": {
      "type": "object",
      "required": ["equipment_id", "measurements"],
      "properties": {
        "equipment_id": { "type": "string", "description": "Model/serial to route to correct RAG namespace" },
        "measurements": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["test_point", "parameter", "value", "unit"],
            "properties": {
              "test_point": { "type": "string", "description": "e.g., TP12 - Output Voltage" },
              "parameter": { "type": "string", "enum": ["voltage", "current", "resistance", "power", "frequency"] },
              "value": { "type": "number" },
              "unit": { "type": "string" },
              "expected_range": { "type": "object", "properties": { "min": { "type": "number" }, "max": { "type": "number" } } },
              "timestamp": { "type": "string", "format": "date-time" },
              "instrument": { "type": "string" }
            }
          }
        }
      }
    },
    "context": {
      "type": "object",
      "required": ["retrieved_docs"],
      "properties": {
        "retrieved_docs": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["doc_id", "title", "content", "relevance_score"],
            "properties": {
              "doc_id": { "type": "string" },
              "title": { "type": "string" },
              "section": { "type": "string" },
              "content": { "type": "string", "description": "Retrieved documentation snippet" },
              "relevance_score": { "type": "number", "minimum": 0, "maximum": 1 }
            }
          }
        },
        "conversation_history": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "role": { "type": "string", "enum": ["user", "agent"] },
              "content": { "type": "string" },
              "timestamp": { "type": "string", "format": "date-time" }
            }
          }
        }
      }
    }
  }
}
```

### Input Example

```json
{
  "trigger": {
    "type": "signal_submission",
    "content": "CCTV power supply unit not outputting 12V. Measured TP1 and getting unusual reading.",
    "urgency": "high"
  },
  "signals": {
    "equipment_id": "CCTV-PSU-24W-V1",
    "measurements": [
      {
        "test_point": "TP1 - Primary Side",
        "parameter": "voltage",
        "value": 18.5,
        "unit": "V",
        "expected_range": { "min": 170, "max": 265 },
        "timestamp": "2026-02-03T08:15:00Z",
        "instrument": "Fluke 87V"
      },
      {
        "test_point": "TP2 - Output 12V",
        "parameter": "voltage",
        "value": 0.0,
        "unit": "V",
        "expected_range": { "min": 11.4, "max": 12.6 },
        "timestamp": "2026-02-03T08:16:00Z",
        "instrument": "Fluke 87V"
      },
      {
        "test_point": "R2 - Feedback Resistor",
        "parameter": "resistance",
        "value": 470,
        "unit": "Ω",
        "expected_range": { "min": 470, "max": 470 }
      }
    ]
  },
  "context": {
    "retrieved_docs": [
      {
        "doc_id": "CCTV-PSU-SM-001",
        "title": "24W CCTV Power Supply Service Manual",
        "section": "Section 3.2 - No Output Troubleshooting",
        "content": "If TP1 shows low voltage and TP2 is 0V, suspect bridge rectifier or primary side failure. Check D1-D4 continuity. Expected TP1 AC voltage: 170-265V.",
        "relevance_score": 0.95
      },
      {
        "doc_id": "CCTV-PSU-SM-001",
        "title": "24W CCTV Power Supply Service Manual",
        "section": "Section 4.1 - Component Specifications",
        "content": "R2 is 470Ω ±1% feedback resistor. Open R2 causes output to collapse to 0V.",
        "relevance_score": 0.72
      }
    ],
    "conversation_history": []
  }
}
```

---

## 2. OUTPUT CONTRACT

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["observed_signals", "fault_hypothesis", "reasoning_path", "next_action"],
  "properties": {
    "observed_signals": {
      "type": "object",
      "required": ["interpretation", "anomalies", "status"],
      "properties": {
        "interpretation": {
          "type": "string",
          "description": "Human-readable summary of what the signal data indicates"
        },
        "anomalies": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["test_point", "expected", "measured", "severity"],
            "properties": {
              "test_point": { "type": "string" },
              "expected": { "type": "string" },
              "measured": { "type": "string" },
              "deviation": { "type": "string" },
              "severity": { "type": "string", "enum": ["critical", "warning", "minor"] }
            }
          }
        },
        "status": { "type": "string", "enum": ["normal", "degraded", "failed"] }
      }
    },
    "fault_hypothesis": {
      "type": "object",
      "required": ["primary_cause", "confidence", "supporting_evidence", "contradicting_evidence"],
      "properties": {
        "primary_cause": { "type": "string", "description": "Most likely root cause" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1, "description": "Never 1.0" },
        "component": { "type": "string", "description": "Suspect component ID if known" },
        "failure_mode": { "type": "string", "description": "e.g., open circuit, short circuit, degraded" },
        "supporting_evidence": {
          "type": "array",
          "items": { "type": "string" }
        },
        "contradicting_evidence": {
          "type": "array",
          "items": { "type": "string" }
        },
        "differential_diagnoses": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["cause", "probability"],
            "properties": {
              "cause": { "type": "string" },
              "probability": { "type": "number" },
              "key_differentiator": { "type": "string" }
            }
          }
        }
      }
    },
    "reasoning_path": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step", "observation", "inference", "source"],
        "properties": {
          "step": { "type": "integer" },
          "observation": { "type": "string", "description": "What was observed from signals/docs" },
          "inference": { "type": "string", "description": "Logical deduction from observation" },
          "source": { "type": "string", "enum": ["signal", "documentation", "logic"], "description": "Source of this inference" }
        }
      }
    },
    "next_action": {
      "type": "object",
      "required": ["action", "target", "expected_result", "priority"],
      "properties": {
        "action": { "type": "string", "enum": ["measure", "inspect", "replace", "verify", "escalate"] },
        "target": { "type": "string", "description": "Test point or component to act on" },
        "instruction": { "type": "string", "description": "Detailed step-by-step instruction" },
        "expected_result": { "type": "string", "description": "What to expect if hypothesis is correct" },
        "priority": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
        "safety_warning": { "type": "string" }
      }
    },
    "metadata": {
      "type": "object",
      "required": ["version", "timestamp", "equipment_id"],
      "properties": {
        "version": { "type": "string", "const": "1.0" },
        "timestamp": { "type": "string", "format": "date-time" },
        "equipment_id": { "type": "string" },
        "processing_time_ms": { "type": "integer" }
      }
    }
  }
}
```

### Output Example

```json
{
  "observed_signals": {
    "interpretation": "Primary side input voltage is 18.5V instead of expected 170-265V AC. Output is completely dead at 0V. Feedback resistor R2 reads 470Ω nominal.",
    "anomalies": [
      {
        "test_point": "TP1 - Primary Side",
        "expected": "170-265V AC",
        "measured": "18.5V",
        "deviation": "-89%",
        "severity": "critical"
      },
      {
        "test_point": "TP2 - Output 12V",
        "expected": "11.4-12.6V",
        "measured": "0.0V",
        "deviation": "-100%",
        "severity": "critical"
      }
    ],
    "status": "failed"
  },
  "fault_hypothesis": {
    "primary_cause": "Primary side input failure - likely bridge rectifier shorted or AC input fault",
    "confidence": 0.78,
    "component": "BR1 (Bridge Rectifier)",
    "failure_mode": "open circuit or shorted input",
    "supporting_evidence": [
      "TP1 shows 18.5V instead of 170-265V - indicates primary side not receiving proper AC input",
      "Service manual section 3.2 states: 'If TP1 shows low voltage and TP2 is 0V, suspect bridge rectifier or primary side failure'",
      "Output collapse correlates with primary side failure per documentation"
    ],
    "contradicting_evidence": [
      "R2 feedback resistor reads nominal, which would typically rule out feedback circuit failure"
    ],
    "differential_diagnoses": [
      {
        "cause": "Failed bridge rectifier (BR1)",
        "probability": 0.78,
        "key_differentiator": "Check D1-D4 diode continuity; shorted diodes indicate BR1 failure"
      },
      {
        "cause": "Failed input fuse",
        "probability": 0.15,
        "key_differentiator": "Inspect fuse F1 visually and test continuity"
      },
      {
        "cause": "Loose AC connector",
        "probability": 0.07,
        "key_differentiator": "Verify AC input connector is fully seated"
      }
    ]
  },
  "reasoning_path": [
    {
      "step": 1,
      "observation": "TP1 measured 18.5V (expected 170-265V AC)",
      "inference": "Primary side is receiving severely reduced or DC voltage instead of proper AC input",
      "source": "signal"
    },
    {
      "step": 2,
      "observation": "TP2 output is 0V (expected 12V)",
      "inference": "Power supply is not converting any power - downstream circuits are not powered",
      "source": "signal"
    },
    {
      "step": 3,
      "observation": "Service manual section 3.2: 'If TP1 shows low voltage and TP2 is 0V, suspect bridge rectifier or primary side failure'",
      "inference": "This symptom pattern is a known failure mode documented in official service procedures",
      "source": "documentation"
    },
    {
      "step": 4,
      "observation": "R2 feedback resistor reads 470Ω nominal",
      "inference": "Feedback circuit is functional; failure is upstream in primary side",
      "source": "signal"
    },
    {
      "step": 5,
      "observation": "Bridge rectifier D1-D4 typically fail shorted or open, causing primary input failure",
      "inference": "Most probable root cause is failed bridge rectifier or related primary component",
      "source": "documentation"
    }
  ],
  "next_action": {
    "action": "measure",
    "target": "BR1 - Bridge Rectifier (pins 1-4)",
    "instruction": "Set multimeter to diode mode. Measure forward voltage drop across each diode pair: AC1-to-DC+ (should read ~0.7V), AC2-to-DC+ (should read ~0.7V), AC1-to-DC-, AC2-to-DC-. Then reverse polarity to check for leakage.",
    "expected_result": "All four measurements should show ~0.7V forward drop and OL reverse. Shorted diodes (<0.1V both directions) indicate BR1 failure.",
    "priority": "critical",
    "safety_warning": "Ensure AC power is disconnected before touching test points. Capacitors may retain charge - discharge before measurement."
  },
  "metadata": {
    "version": "1.0",
    "timestamp": "2026-02-03T08:20:00Z",
    "equipment_id": "CCTV-PSU-24W-V1",
    "processing_time_ms": 1247
  }
}
```

---

## 3. CONTRACT COMPLIANCE RULES

| Rule | Description |
|------|-------------|
| OUTPUT_001 | All four output sections MUST be present (`observed_signals`, `fault_hypothesis`, `reasoning_path`, `next_action`) |
| OUTPUT_002 | `confidence` MUST be < 1.0 (never express 100% certainty) |
| OUTPUT_003 | Every `reasoning_path` step MUST cite source (`signal`, `documentation`, or `logic`) |
| OUTPUT_004 | `next_action.priority` MUST be one of: critical, high, medium, low |
| OUTPUT_005 | `next_action.safety_warning` MUST be present if measurement involves AC or capacitors |
| OUTPUT_006 | `metadata.timestamp` MUST be ISO 8601 UTC |
| OUTPUT_007 | `fault_hypothesis.differential_diagnoses` MUST include alternatives if confidence < 0.9 |
