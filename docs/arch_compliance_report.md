# Architectural Compliance Report

**Date:** 2026-02-03  
**Version:** 1.0

---

## 1. Executive Summary

This report audits the biomedical troubleshooting agent against the universal RAG-driven architecture principles. **Current compliance: PARTIAL**.

### Key Findings

| Principle | Status | Violations |
|-----------|--------|------------|
| No hard-coded equipment names | ❌ VIOLATED | CCTV-PSU-24W-V1 in multiple files |
| No hard-coded thresholds | ❌ VIOLATED | Voltage/current limits in models.py |
| No hard-coded fault logic | ❌ VIOLATED | Fault detection in agent.py |
| No hard-coded recovery actions | ❌ VIOLATED | Action mapping in agent.py |
| Images as first-class data | ⚠️ PARTIAL | Schema exists, not integrated |
| RAG-primary knowledge | ⚠️ PARTIAL | Static fallback contains logic |

---

## 2. Violations Catalog

### 2.1 Hard-Coded Equipment Names

**Files affected:**
- `src/domain/models.py` - `CCTV-PSU-24W-V1` in comments/examples
- `src/application/agent.py` - Equipment ID checks
- `scripts/populate_chromadb.py` - Equipment-specific documentation
- `data/mock_signals/scenarios.json` - CCTV-specific scenarios

**Refactor required:** Move all equipment IDs to data files.

### 2.2 Hard-Coded Thresholds

**File:** `src/domain/models.py`

```python
# VIOLATION: Hard-coded threshold
valid_units = {'V', 'mV', 'A', 'mA', 'Ω', 'kΩ', 'W', 'mW', 'Hz', 'kHz', '°C', '%RH'}
```

```python
# VIOLATION: Hard-coded semantic states
class SemanticState(Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    OUT_OF_SPEC_LOW = "out_of_spec_low"
    # ... more hard-coded states
```

**Refactor required:** Remove enum, make states data-driven via equipment configuration.

### 2.3 Hard-Coded Fault Logic

**File:** `src/application/agent.py` (lines 369-390)

```python
# VIOLATION: Hard-coded fault detection
if "output" in cause.lower() and "voltage" in cause.lower():
    action = "replace"
    target = "Output capacitor or regulator"
elif "short" in cause.lower() or "shorted" in cause.lower():
    action = "inspect"
    target = "Shorted component"
elif "open" in cause.lower() or "missing" in cause.lower():
    action = "replace"
    target = "Failed component"
else:
    action = "measure"
    target = "Suspicious test points"
```

**Refactor required:** Replace with data-driven recommendation lookup from equipment configuration.

### 2.4 Hard-Coded Priority Logic

**File:** `src/application/agent.py` (lines 360-368)

```python
# VIOLATION: Hard-coded priority determination
if state.overall_status == "failed" or confidence >= 0.8:
    priority = Severity.CRITICAL
elif state.overall_status == "degraded" or confidence >= 0.5:
    priority = Severity.HIGH
else:
    priority = Severity.MEDIUM
```

**Refactor required:** Priority should come from equipment configuration strategies.

---

## 3. Proposed Refactors

### 3.1 Equipment Configuration Schema

Create unified equipment definition file (`data/equipment/{equipment_id}.yaml`):

```yaml
metadata:
  equipment_id: "cctv-psu-24w-v1"
  name: "24W CCTV Power Supply"

signals:
  - signal_id: "output_12v"
    test_point: "TP2"
    parameter: "voltage_dc"
    unit: "V"

thresholds:
  - signal_id: "output_12v"
    states:
      normal: { min: 11.4, max: 12.6 }
      degraded: { min: 10.8, max: 13.2 }
      missing: { max: 0.5 }

faults:
  - fault_id: "output_rail_collapse"
    signatures:
      - signal_id: "output_12v"
        state: "missing"
    recovery:
      - action: "replace"
        target: "U5"
```

### 3.2 Refactored Domain Models

**Remove:**
- `SemanticState` enum
- `Severity` enum
- Hard-coded threshold validation
- Static rule engine

**Replace with:**
- Generic signal interpretation using equipment config
- Data-driven state lookup
- Configurable strategies

### 3.3 Refactored Agent

**Before (violation):**
```python
def analyze_fault(state: AgentState) -> AgentState:
    if "output" in cause.lower():
        action = "replace"
```

**After (compliant):**
```python
def analyze_fault(state: AgentState) -> AgentState:
    # Load equipment config from RAG
    equipment_config = load_equipment_config(state.equipment_model)
    
    # Get fault from config based on signatures
    fault = equipment_config.find_fault(state.signal_states)
    
    # Get recovery from fault definition
    recovery = fault.get_recovery()
```

---

## 4. Data Flow After Refactor

```
User Input
    ↓
Load Equipment Config (from RAG/data file)
    ↓
Interpret Signals (using equipment thresholds)
    ↓
Match Fault Signatures (using equipment fault definitions)
    ↓
Retrieve Recovery Actions (from equipment config)
    ↓
Format Output (generic template)
```

**Key change:** All equipment knowledge flows from data, not code.

---

## 5. Schema Updates Required

### 5.1 Equipment Configuration Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["metadata", "signals", "thresholds", "faults"],
  "properties": {
    "metadata": { "$ref": "#/definitions/Metadata" },
    "signals": { "type": "array", "items": { "$ref": "#/definitions/Signal" } },
    "thresholds": { "type": "array", "items": { "$ref": "#/definitions/Threshold" } },
    "faults": { "type": "array", "items": { "$ref": "#/definitions/Fault" } },
    "strategies": { "$ref": "#/definitions/Strategies" },
    "images": { "type": "array", "items": { "$ref": "#/definitions/Image" } }
  }
}
```

### 5.2 Signal Schema

```yaml
Signal:
  type: object
  required: [signal_id, test_point, parameter, unit]
  properties:
    signal_id: string
    test_point: string
    parameter: string  # voltage_dc, current, etc.
    unit: string
    measurability: enum [external, internal]
```

### 5.3 Fault Schema

```yaml
Fault:
  type: object
  required: [fault_id, signatures, hypotheses, recovery]
  properties:
    fault_id: string
    signatures:
      type: array
      items:
        - signal_id: string
          state: string
          confidence: number
    hypotheses:
      type: array
      items:
        - component: string
          failure_mode: string
          cause: string
          confidence: number
    recovery:
      type: array
      steps:
        - action: enum [measure, inspect, replace, verify]
          target: string
          instruction: string
```

---

## 6. Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P1 | Create equipment configuration schema | Low | High |
| P2 | Remove hard-coded SemanticState enum | Medium | High |
| P3 | Refactor agent.py to use data-driven lookup | Medium | High |
| P4 | Create CCTV PSU equipment config file | Low | Medium |
| P5 | Update RAG to load from equipment config | Low | Medium |
| P6 | Add image metadata support | Low | Medium |
| P7 | Verify all device logic removed | Low | High |

---

## 7. Success Criteria Checklist

After refactor:

- [ ] No equipment ID strings in Python code
- [ ] No threshold values in Python code
- [ ] No fault detection logic in Python code
- [ ] No action mapping in Python code
- [ ] All equipment knowledge in YAML/JSON files
- [ ] Adding new equipment = adding one data file
- [ ] Agent can troubleshoot unknown equipment via RAG
- [ ] Images retrieved via test_point_id from config

---

## 8. Next Steps

1. **Approve schema** - Confirm equipment configuration schema meets requirements
2. **Create sample data** - Generate CCTV PSU equipment file
3. **Refactor incrementally** - Phase out hard-coded logic
4. **Test coverage** - Ensure all paths work with data-driven approach
5. **Documentation** - Update README with equipment addition guide

---

## Appendix: File Changes Summary

| File | Action | Reason |
|------|--------|--------|
| `src/domain/models.py` | REFACTOR | Remove hard-coded enums and thresholds |
| `src/application/agent.py` | REFACTOR | Replace fault detection with data lookup |
| `scripts/populate_chromadb.py` | REMOVE | Replace with equipment config loader |
| `data/mock_signals/scenarios.json` | MERGE | Consolidate into equipment config |
| `data/equipment/{id}.yaml` | CREATE | Equipment-specific data |
