# Equipment Configuration Schema

This document defines the unified equipment configuration format. All equipment-specific knowledge lives here - **NO code changes required** to add new equipment.

---

## 1. Schema Overview

```yaml
# One file per equipment: data/equipment/{equipment_id}.yaml
metadata:          # Equipment identification
signals:          # All measurable signals
thresholds:       # Signal interpretation rules
faults:           # Fault definitions and recovery
strategies:        # Troubleshooting strategies
images:           # Reference images
recovery_protocols: # Named recovery procedures
```

---

## 2. Complete CCTV PSU Example

```yaml
# =============================================================================
# FILE: data/equipment/cctv-psu-24w-v1.yaml
# =============================================================================

metadata:
  equipment_id: "cctv-psu-24w-v1"
  name: "24W CCTV Power Supply Unit"
  category: "power_supply"
  manufacturer: "Generic CCTV"
  version: "1.0.0"
  created: "2026-02-03"

# =============================================================================
# SIGNALS
# All signals the equipment can report or that can be measured
# =============================================================================
signals:
  # Input signals
  - signal_id: "ac_input"
    name: "AC Input Voltage"
    test_point: "AC_IN"
    parameter: "voltage_rms"
    unit: "V"
    measurability: "external"

  # Primary side
  - signal_id: "bridge_output"
    name: "Bridge Rectifier Output"
    test_point: "TP1"
    parameter: "voltage_dc"
    unit: "V"
    measurability: "internal"

  - signal_id: "input_fuse"
    name: "Input Fuse"
    test_point: "F1"
    parameter: "resistance"
    unit: "Ω"
    measurability: "internal"

  # Secondary/Output
  - signal_id: "output_12v"
    name: "12V Output Rail"
    test_point: "TP2"
    parameter: "voltage_dc"
    unit: "V"
    measurability: "internal"

  - signal_id: "feedback_ref"
    name: "Feedback Reference"
    test_point: "TP3"
    parameter: "voltage_dc"
    unit: "V"
    measurability: "internal"

  - signal_id: "output_current"
    name: "Output Current"
    test_point: "I_OUT"
    parameter: "current"
    unit: "A"
    measurability: "internal"

  - signal_id: "feedback_resistor"
    name: "Feedback Resistor"
    test_point: "R2"
    parameter: "resistance"
    unit: "Ω"
    measurability: "internal"

  - signal_id: "output_capacitor_esr"
    name: "Output Capacitor ESR"
    test_point: "C12"
    parameter: "resistance"
    unit: "Ω"
    measurability: "internal"

  # Thermal
  - signal_id: "u5_temperature"
    name: "U5 Case Temperature"
    test_point: "U5"
    parameter: "temperature"
    unit: "°C"
    measurability: "internal"

# =============================================================================
# THRESHOLDS
# Semantic states and their numerical boundaries
# =============================================================================
thresholds:
  # AC Input
  - signal_id: "ac_input"
    states:
      normal: { min: 170, max: 265 }
      degraded: { min: 150, max: 285 }
      under_voltage: { max: 150 }
      over_voltage: { min: 285 }
      missing: { max: 10 }

  # Bridge Output
  - signal_id: "bridge_output"
    states:
      normal: { min: 280, max: 380 }
      degraded: { min: 250, max: 400 }
      low: { max: 250 }
      missing: { max: 10 }

  # 12V Output
  - signal_id: "output_12v"
    states:
      normal: { min: 11.4, max: 12.6 }
      degraded: { min: 10.8, max: 13.2 }
      under_voltage: { max: 10.8 }
      over_voltage: { min: 13.2 }
      missing: { max: 0.5 }

  # Feedback Reference
  - signal_id: "feedback_ref"
    states:
      normal: { min: 2.4, max: 2.6 }
      degraded: { min: 2.2, max: 2.8 }
      failed: { max: 0.2 }
      over: { min: 2.8 }

  # Output Current
  - signal_id: "output_current"
    states:
      normal: { min: 0, max: 2.0 }
      overload: { min: 2.0, max: 2.5 }
      over_current: { min: 2.5 }
      shorted: { max: 0.01 }

  # Feedback Resistor
  - signal_id: "feedback_resistor"
    states:
      normal: { min: 465, max: 475 }
      degraded: { min: 450, max: 490 }
      open: { min: 100000 }
      shorted: { max: 10 }

  # Output Capacitor ESR
  - signal_id: "output_capacitor_esr"
    states:
      normal: { max: 0.2 }
      degraded: { max: 0.5 }
      failed: { min: 0.5 }

  # Temperature
  - signal_id: "u5_temperature"
    states:
      normal: { max: 60 }
      elevated: { max: 80 }
      warning: { max: 95 }
      critical: { min: 95 }

# =============================================================================
# FAULTS
# All faults, their signatures, and recovery actions
# =============================================================================
faults:
  # Fault 1: Output Rail Collapse
  - fault_id: "output_rail_collapse"
    name: "Output Rail Collapse"
    description: "12V output has collapsed to near zero"
    signatures:
      - signal_id: "output_12v"
        state: "missing"
        confidence: 0.9
      - signal_id: "feedback_ref"
        state: "failed"
        confidence: 0.6
    hypotheses:
      - rank: 1
        component: "U5"
        failure_mode: "failed"
        cause: "Buck converter IC has failed"
        confidence: 0.85
      - rank: 2
        component: "BR1"
        failure_mode: "failed"
        cause: "Bridge rectifier has failed"
        confidence: 0.10
    recovery:
      - step: 1
        action: "inspect"
        target: "Input fuse F1"
        instruction: "Check fuse continuity"
        verification: "Fuse reads <0.1Ω"
        safety: "Disconnect AC power before inspection"
      - step: 2
        action: "measure"
        target: "Bridge output TP1"
        instruction: "Measure DC voltage at bridge output"
        verification: "Should read 280-380V DC"
      - step: 3
        action: "replace"
        target: "U5"
        instruction: "Replace buck converter IC"
        verification: "Output returns to 12V ±5%"
        estimated_time: "15 minutes"
        difficulty: "moderate"
        tools: ["Soldering iron", "Thermal paste"]

  # Fault 2: Overvoltage Output
  - fault_id: "overvoltage_output"
    name: "Overvoltage Output"
    description: "12V output exceeds safe maximum"
    signatures:
      - signal_id: "output_12v"
        state: "over_voltage"
        confidence: 0.95
    hypotheses:
      - rank: 1
        component: "R2"
        failure_mode: "open"
        cause: "Feedback resistor R2 has failed open"
        confidence: 0.92
    recovery:
      - step: 1
        action: "measure"
        target: "Feedback reference TP3"
        instruction: "Measure reference voltage"
        verification: "Should read 2.5V ±0.1V"
      - step: 2
        action: "measure"
        target: "Feedback resistor R2"
        instruction: "Measure R2 resistance"
        verification: "Should read 470Ω ±1%"
      - step: 3
        action: "replace"
        target: "R2"
        instruction: "Replace with 470Ω ±1% resistor"
        verification: "Output returns to 12V ±5%"

  # Fault 3: Thermal Shutdown
  - fault_id: "thermal_shutdown"
    name: "Thermal Shutdown"
    description: "Unit shuts down after operating for several minutes"
    signatures:
      - signal_id: "u5_temperature"
        state: "critical"
        confidence: 0.9
      - signal_id: "output_12v"
        state: "missing"
        confidence: 0.7
    hypotheses:
      - rank: 1
        component: "U5"
        failure_mode: "overheating"
        cause: "Inadequate heatsinking on buck converter"
        confidence: 0.87
    recovery:
      - step: 1
        action: "measure"
        target: "U5 temperature"
        instruction: "Monitor temperature during operation"
      - step: 2
        action: "inspect"
        target: "Heatsink"
        instruction: "Check heatsink attachment and thermal compound"
      - step: 3
        action: "improve"
        target: "Thermal management"
        instruction: "Add/replace heatsink or improve airflow"
        verification: "Temperature stays below 70°C at full load"

  # Fault 4: Excessive Ripple
  - fault_id: "excessive_ripple"
    name: "Excessive Output Ripple"
    description: "Output voltage ripple exceeds specification"
    signatures:
      - signal_id: "output_12v"
        state: "degraded"
        confidence: 0.8
      - signal_id: "output_capacitor_esr"
        state: "failed"
        confidence: 0.9
    hypotheses:
      - rank: 1
        component: "C12"
        failure_mode: "degraded"
        cause: "Output capacitor has high ESR"
        confidence: 0.90
    recovery:
      - step: 1
        action: "measure"
        target: "C12 ESR"
        instruction: "Measure capacitor ESR"
        verification: "Should be <0.2Ω"
      - step: 2
        action: "replace"
        target: "C12"
        instruction: "Replace with low-ESR 1000μF 16V capacitor"
        verification: "Ripple <50mV p-p"

  # Fault 5: Primary Side Failure
  - fault_id: "primary_side_failure"
    name: "Primary Side Input Fault"
    description: "AC input not reaching primary side circuits"
    signatures:
      - signal_id: "ac_input"
        state: "normal"
        confidence: 0.9
      - signal_id: "bridge_output"
        state: "low"
        confidence: 0.95
    hypotheses:
      - rank: 1
        component: "F1"
        failure_mode: "open"
        cause: "Input fuse has failed"
        confidence: 0.88
    recovery:
      - step: 1
        action: "inspect"
        target: "Input fuse F1"
        instruction: "Visual inspection of fuse"
      - step: 2
        action: "measure"
        target: "F1 resistance"
        instruction: "Measure fuse continuity"
        verification: "Should read <0.1Ω"
      - step: 3
        action: "replace"
        target: "F1"
        instruction: "Replace with 250V 1A slow-blow fuse"
        verification: "Primary side voltage returns"

# =============================================================================
# TROUBLESHOOTING STRATEGIES
# =============================================================================
strategies:
  default: "protection_first"
  available:
    - id: "protection_first"
      name: "Protection-First Reasoning"
      description: "Check protection circuits first"
      priority_order:
        - "Check for obvious protection triggers"
        - "Verify input power integrity"
        - "Check output short conditions"
    - id: "energy_flow"
      name: "Energy Flow Tracing"
      description: "Trace power from input to output"
      priority_order:
        - "Verify AC input"
        - "Check primary conversion"
        - "Verify regulation"
    - id: "binary_partition"
      name: "Binary Partition"
      description: "Divide system in half, test each half"
    - id: "bayesian"
      name: "Bayesian Updating"
      description: "Update probabilities based on evidence"
    - id: "information_gain"
      name: "Information Gain"
      description: "Order tests by information gain"
  active: "protection_first"

# =============================================================================
# IMAGES
# =============================================================================
images:
  - image_id: "pcb_overview"
    filename: "cctv-psu-pcb-overview.jpg"
    description: "Full PCB layout overview"
    test_points: ["AC_IN", "TP1", "TP2", "TP3", "F1", "U5", "R2", "C12"]
    annotations:
      - target: "AC_IN"
        position: "top-left corner"
        label: "AC Input Connector"
      - target: "U5"
        position: "center-right"
        label: "Buck Converter IC"

  - image_id: "test_point_tp2"
    filename: "cctv-psu-tp2-detail.jpg"
    description: "Close-up of TP2 (12V output)"
    test_points: ["TP2"]

# =============================================================================
# RECOVERY PROTOCOLS
# =============================================================================
recovery_protocols:
  - protocol_id: "power_cycle"
    name: "Safe Power Cycle"
    steps:
      - step: 1
        action: "disconnect"
        instruction: "Disconnect AC power"
        wait_seconds: 30
      - step: 2
        action: "inspect"
        instruction: "Check for visible damage"
      - step: 3
        action: "connect"
        instruction: "Reconnect AC power"
      - step: 4
        action: "measure"
        instruction: "Verify output voltage"
        expected: "12V ±5%"

# =============================================================================
# VALIDATION
# =============================================================================
validation:
  schema_version: "1.0.0"
```

---

## 3. How to Add New Equipment

1. Create file: `data/equipment/{new-equipment-id}.yaml`
2. Populate with equipment-specific data
3. Add documentation to RAG
4. Add reference images
5. **NO code changes required**

---

## 4. Adding to RAG

Equipment configuration files should be indexed in ChromaDB:

```python
from src.infrastructure.rag_repository import RAGRepository

repo = RAGRepository.from_directory()
repo.initialize()

# Load all equipment configs into RAG
import yaml
for config_file in Path("data/equipment").glob("*.yaml"):
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    repo.add_documents(
        documents=[yaml.dump(config)],
        metadatas=[{"equipment_id": config["metadata"]["equipment_id"]}],
        ids=[config["metadata"]["equipment_id"]]
    )
```
