# Prompt for Generating RAG-Optimized Troubleshooting Documentation

> **Instructions:** Copy this entire prompt and provide it to an AI assistant along with the image at `docs/CCTV Power Supply Unit.jpeg` to generate fresh RAG-optimized troubleshooting documentation for the CCTV Power Supply Unit.

---

## 1. Project Context

You are generating documentation for a **Biomedical Equipment Troubleshooting AI Agent** that uses Retrieval Augmented Generation (RAG) to assist technicians in **diagnosing AND repairing** equipment failures.

### System Architecture

The AI agent operates as follows:

```mermaid
flowchart LR
    USER[User Query] --> RETRIEVE[RAG Retrieval from ChromaDB]
    RETRIEVE --> AUGMENT[Augment LLM Context]
    AUGMENT --> GENERATE[Generate Diagnosis]
    GENERATE --> RESPONSE[Structured Response]
```

### Key Principles

1. **Deterministic Behavior**: All diagnostic logic must be traceable and reproducible
2. **Equipment-Agnostic Core**: No hard-coded equipment logic; all knowledge comes from configuration files and documentation
3. **RAG-Enhanced Reasoning**: LLM reasoning is augmented with retrieved documentation chunks
4. **Safety-First**: All recommendations include safety warnings and verification steps

### Target Users

- Biomedical engineers troubleshooting medical equipment
- Field technicians performing routine maintenance
- Equipment manufacturers creating diagnostic documentation

---

## 1.1 Diagnostic Philosophy

### Root Cause vs Symptom

A **symptom** is an observable manifestation of a failure, while the **root cause** is the underlying fault that produced it. Fixing only the symptom results in repeat failure.

**Critical Principle:** Protection devices (fuses, circuit breakers, thermal cutoffs) are rarely root causes. They fail to protect the circuit from something else.

| Symptom | Common Naive Fix | Actual Root Cause | Recurrence if Naive Fix |
|---------|------------------|-------------------|-------------------------|
| Blown fuse | Replace fuse | Shorted MOSFET | 95%+ immediate re-blow |
| No output | Replace output capacitor | Failed feedback loop | 70%+ recurrence |
| Overheating | Add cooling fan | Degraded component drawing excess current | 80%+ recurrence |

### Causality Chains

Every failure signature must trace back to root cause(s). Failures often cascade through multiple components:

```
ROOT CAUSE: Secondary Schottky diode shorts
    └─► Transformer secondary effectively shorted
        └─► Reflected impedance to primary drops
            └─► Primary current increases
                └─► MOSFET thermal stress increases
                    └─► MOSFET fails short
                        └─► DC bus shorted
                            └─► Massive current through rectifier
                                └─► SYMPTOM: Fuse blows
```

**Key Insight:** The fuse is the VICTIM, not the cause. Replacing the fuse without addressing the MOSFET (and what caused the MOSFET to fail) guarantees recurrence.

### Repair Validation

After any repair, verify that:

1. **The identified root cause was addressed** — The faulty component was replaced
2. **Contributing factors were resolved** — Whatever caused the component to fail was also fixed
3. **No secondary damage remains** — Other components in the cascade path were checked
4. **Functional verification passes** — The equipment operates normally under expected conditions

---

## 1.2 Expert Troubleshooting Methodologies

Expert technicians use proven methodologies that maximize diagnostic efficiency. These strategies are based on decades of field experience and theoretical foundations in systems theory and probability.

### 1.2.1 Half-Split Method (Binary Search)

**Principle:** Divide the system in half at a strategic test point. One measurement eliminates approximately 50% of possible fault locations.

**Why It Works:** Binary search has O(log n) complexity vs O(n) for sequential search. In a system with 100 possible fault locations, half-split finds the fault in ~7 tests vs 50 average for sequential.

**Application to SMPS:**
```
DC BUS TEST (Midpoint)
    │
    ├─► VOLTAGE PRESENT (155V/310V)
    │   └─► ELIMINATES: AC input, fuse, EMI filter, bridge rectifier, bulk capacitor
    │   └─► FAULT IS IN: Switching stage, transformer, or output section
    │
    └─► VOLTAGE ABSENT
        └─► ELIMINATES: Switching stage, transformer, output section
        └─► FAULT IS IN: AC input, fuse, EMI filter, bridge rectifier, bulk capacitor
```

**When to Use:**
- System has clear signal/power flow path
- Test points exist at natural midpoints
- Initial diagnosis with no prior probability information

**When NOT to Use:**
- High-probability fault location is known (use targeted testing instead)
- Test at midpoint is dangerous or difficult
- System has parallel paths that can't be isolated

**Expert Insight:** The DC Bus test is the highest-yield test in SMPS troubleshooting because it sits at the natural midpoint between input and output. One 10-second measurement eliminates half the circuit.

### 1.2.2 Signal Flow Tracing

**Principle:** Follow the power or signal path from input to output (or reverse), testing each stage's input and output.

**Direction Selection:**
- **Forward Tracing (Input → Output):** Use when input is known good, looking for where signal is lost
- **Backward Tracing (Output → Input):** Use when output symptom is clear, looking for source

**Application to SMPS Power Flow:**
```
AC INPUT → EMI FILTER → BRIDGE RECTIFIER → BULK CAP → MOSFET → TRANSFORMER → OUTPUT DIODE → OUTPUT CAP → LOAD
    │           │              │              │          │           │              │            │
  Test 1      Test 2         Test 3        Test 4     Test 5      Test 6         Test 7      Test 8
```

**Stage Boundary Testing:**
Each stage has defined input and output. Test both to determine if stage is passing or failing:

| Stage | Input Test | Output Test | If Input OK, Output Bad |
|-------|------------|-------------|-------------------------|
| Bridge Rectifier | AC voltage | DC voltage | Bridge faulty |
| Bulk Capacitor | DC voltage (rectifier out) | DC voltage (cap terminals) | Cap or connections faulty |
| MOSFET Switching | Gate drive | Drain waveform | MOSFET or gate drive faulty |

**Expert Insight:** Signal flow tracing is most effective when combined with half-split. Start with half-split to isolate a section, then use signal flow within that section.

### 1.2.3 Functional Block Analysis

**Principle:** Group components by function rather than physical location. Each functional block has defined inputs, processing, and outputs.

**SMPS Functional Blocks:**

```
┌─────────────────────────────────────────────────────────────────┐
│                        POWER PATH                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │   AC     │ → │  DC BUS  │ → │ SWITCHING│ → │  OUTPUT  │ →   │
│  │  INPUT   │   │  FORMATION│  │  STAGE   │   │  FILTER  │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CONTROL PATH                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                    │
│  │  PWM     │ ← │ FEEDBACK │ ← │  OUTPUT  │                    │
│  │CONTROLLER│   │  NETWORK │   │  SENSE   │                    │
│  └──────────┘   └──────────┘   └──────────┘                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      PROTECTION PATH                            │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                    │
│  │  OVP     │   │   OCP    │   │ THERMAL  │                    │
│  │ CIRCUIT  │   │ CIRCUIT  │   │ SHUTDOWN │                    │
│  └──────────┘   └──────────┘   └──────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

**Block Boundary Testing:**
Test inputs and outputs at block boundaries to isolate faulty block:

| Block | Input | Output | Test Points |
|-------|-------|--------|-------------|
| AC Input | Mains AC | Filtered AC | Before/after EMI filter |
| DC Bus Formation | Filtered AC | DC Bus (155V/310V) | Bridge in/out, cap terminals |
| Switching Stage | DC Bus, Gate Drive | Transformer primary | Drain waveform |
| Output Filter | Transformer secondary | DC Output (12V) | Diode in/out, cap terminals |

**Expert Insight:** Functional blocks often span multiple physical areas. The feedback network includes components on both primary and secondary sides (via optocoupler). Don't assume physical proximity equals functional relationship.

### 1.2.4 Stimulus-Response Testing

**Principle:** Inject a known stimulus and measure the response. Used for testing feedback loops, control circuits, and dynamic behavior.

**Applications:**

**A. Load Response Test:**
```
STIMULUS: Vary load from 10% to 100% rated current
RESPONSE: Monitor output voltage
EXPECTED: Voltage stays within regulation band (±5%)
FAILURE MODES:
  - Voltage sags under load → Output cap ESR high, or feedback too slow
  - Voltage overshoots on load removal → Feedback loop instability
  - Oscillation during load transient → Control loop compensation issue
```

**B. Line Response Test:**
```
STIMULUS: Vary input AC voltage (90V to 264V range)
RESPONSE: Monitor output voltage
EXPECTED: Output remains stable
FAILURE MODES:
  - Output drops at low line → Insufficient headroom, degraded components
  - Output rises at high line → Feedback not regulating
```

**C. Gate Drive Injection Test:**
```
STIMULUS: Inject external gate signal (with DC bus discharged)
RESPONSE: Monitor MOSFET drain
EXPECTED: Drain switches between high impedance and near-zero
FAILURE MODES:
  - No switching → MOSFET failed open or gate circuit issue
  - Always conducting → MOSFET failed short
```

**Expert Insight:** Stimulus-response testing is essential for diagnosing intermittent faults and marginal performance that pass static tests but fail under dynamic conditions.

### 1.2.5 Current Signature Analysis

**Principle:** Analyze current waveforms to detect anomalies that indicate specific failure modes.

**Current Signatures in SMPS:**

| Signature | Indication | Root Cause |
|-----------|------------|------------|
| High inrush current, no decay | Short on DC bus | MOSFET short, bridge short, cap short |
| Normal inrush, then drop to zero | Open circuit after bulk cap | MOSFET open, controller not starting |
| Continuous high current | Overload condition | Output short, feedback failure |
| Pulsing current (hiccup) | Protection cycling | Overload, short, or protection fault |
| Irregular current spikes | Intermittent conduction | Bad connection, arcing |
| High ripple current | Degraded capacitor | High ESR, low capacitance |

**Measurement Methods:**
- **Current probe + oscilloscope:** Best for waveform analysis
- **Series resistor + oscilloscope:** Low-cost alternative, limited accuracy
- **AC clamp meter:** Quick RMS check, no waveform
- **USB multimeter with current mode:** For low-current measurements

**Expert Insight:** Current signature analysis can detect partial failures before catastrophic failure. A capacitor with rising ESR will show increasing ripple current before complete failure.

### 1.2.6 Thermal Profiling

**Principle:** Heat patterns reveal component stress, high-resistance connections, and overloaded components.

**Thermal Signatures:**

| Thermal Pattern | Indication | Root Cause |
|-----------------|------------|------------|
| MOSFET running hot | Excessive dissipation | Degraded gate drive, high switching losses |
| MOSFET running cold | Not switching | Gate drive failure, MOSFET open |
| Bridge rectifier hot | High forward drop or diode short | Degraded diode, one diode shorted |
| Output capacitor hot | High ripple current | High ESR, failing capacitor |
| Transformer hot | Core loss or copper loss | Shorted turns, overload |
| PCB hot spot | High current through thin trace | Overload, trace damage |
| Cold solder joint | Intermittent connection | Visible as temperature anomaly under load |

**Measurement Methods:**
- **IR camera:** Best for overall thermal mapping
- **Thermal probe/contact thermometer:** Point measurements
- **Finger test (quick check):** CAUTION - only on low-voltage sections after power-off

**Safety Note:** Never touch primary-side components immediately after power-off. Stored energy in bulk capacitor can be lethal.

**Expert Insight:** Components running COLD can be as diagnostic as hot components. A MOSFET that should be warm but is cold indicates it's not switching - a key diagnostic clue.

### 1.2.7 Voltage Distribution Analysis

**Principle:** Check voltage at key nodes and compare to expected values. Voltage drops reveal high-resistance paths.

**Key Voltage Nodes in SMPS:**

| Node | Expected Voltage | What It Tests |
|------|------------------|---------------|
| AC Input | 115V or 230V RMS | Mains supply |
| Bridge Output | 155V or 310V DC | Input stage |
| DC Bus (Bulk Cap) | 155V or 310V DC | Bulk capacitor |
| MOSFET Drain | DC Bus voltage | MOSFET off-state |
| MOSFET Source | Near 0V | Source connection |
| Vcc (Controller) | 10-20V (varies) | Controller power |
| Reference Voltage | 2.5V typical | Reference IC |
| Output | 12V ±5% | Output regulation |

**Voltage Drop Analysis:**
```
VOLTAGE DROP = V_upstream - V_downstream
EXPECTED DROP = I × R (where R is trace/cable resistance)

EXCESSIVE DROP INDICATES:
  - High resistance connection
  - Undersized conductor
  - Corroded contact
  - Partial open circuit
```

**Example: Output Cable Drop**
```
PSU Terminal: 12.00V
Load Terminal: 11.50V
Drop: 0.50V
Current: 5A
Implied Resistance: 0.50V / 5A = 0.1Ω
Expected for 2m of 18AWG: ~0.13Ω
Conclusion: Normal for this cable gauge/length
```

### 1.2.8 ESR (Equivalent Series Resistance) Testing

**Principle:** Measure capacitor ESR as early indicator of degradation. High ESR often precedes capacitance loss.

**Why ESR Matters:**
- ESR increases as electrolyte dries out
- High ESR causes ripple voltage increase
- High ESR causes internal heating, accelerating failure
- ESR can be measured in-circuit with specialized meters

**ESR Measurement Methods:**

| Method | In-Circuit? | Accuracy | Cost |
|--------|-------------|----------|------|
| Dedicated ESR meter | Yes (with caveats) | Good | $30-100 |
| LCR meter | No (requires removal) | Excellent | $50-500 |
| Scope + signal generator | No | Good | Variable |
| V/I method under load | Yes | Fair | Low |

**ESR Guidelines for Electrolytic Capacitors:**

| Capacitance | Voltage | Good ESR | Marginal | Bad |
|-------------|---------|----------|----------|-----|
| 100µF | 25V | <0.5Ω | 0.5-1Ω | >1Ω |
| 470µF | 25V | <0.2Ω | 0.2-0.5Ω | >0.5Ω |
| 1000µF | 25V | <0.1Ω | 0.1-0.2Ω | >0.2Ω |
| 47µF | 400V | <1.0Ω | 1-2Ω | >2Ω |
| 220µF | 400V | <0.5Ω | 0.5-1Ω | >1Ω |

**In-Circuit ESR Caveats:**
- Parallel components can affect reading
- Discharge capacitor before measurement
- Compare to known-good unit when possible

**Expert Insight:** ESR testing is one of the most valuable preventive maintenance tools. A capacitor with high ESR will fail soon, even if capacitance is still acceptable.

### 1.2.9 Ring Testing (For Transformers and Inductors)

**Principle:** Apply a voltage pulse and observe the ringing response. Shorted turns dampen the ringing.

**Setup:**
```
PULSE GENERATOR → INDUCTOR UNDER TEST → OSCILLOSCOPE
                      │
                      └─→ Observe ringing decay
```

**Interpretation:**
```
GOOD INDUCTOR:
  - Rings with multiple cycles
  - Exponential decay
  - Frequency determined by L and parasitic C

SHORTED TURNS:
  - Very few rings (heavily damped)
  - Quick decay
  - Lower frequency (reduced inductance)

OPEN WINDING:
  - No ringing
  - Pulse passes through unchanged
```

**Ring Test Count:**
| Component | Good | Suspect | Failed |
|-----------|------|---------|--------|
| Small inductor (<1mH) | 5+ rings | 2-4 rings | 0-1 rings |
| Power transformer primary | 3+ rings | 1-2 rings | 0 rings |
| Power transformer secondary | 4+ rings | 2-3 rings | 0-1 rings |

**Equipment:**
- Function generator (square wave, 1kHz-10kHz)
- Oscilloscope
- Or dedicated ring tester (e.g., Peak Atlas LCR40)

**Expert Insight:** Ring testing is one of the few ways to detect shorted turns without disassembling the transformer. Shorted turns are a common failure mode that other tests miss.

### 1.2.10 In-Circuit vs Out-of-Circuit Testing

**Principle:** Choose test method based on accuracy requirements vs time/effort trade-offs.

**In-Circuit Testing:**

| Advantages | Disadvantages |
|------------|---------------|
| Fast - no desoldering | Parallel paths can affect readings |
| No damage to component/PCB | May give false readings |
| Can test multiple components quickly | Limited test types possible |
| Preserves warranty in some cases | Component interaction can mask faults |

**When In-Circuit Testing is Appropriate:**
- Initial screening/triage
- Components with clear parallel path isolation
- When time is critical
- When desoldering is risky (multilayer PCB, SMD)

**Out-of-Circuit Testing:**

| Advantages | Disadvantages |
|------------|---------------|
| Accurate measurements | Time-consuming |
| No parallel path interference | Risk of damage during removal |
| Full characterization possible | Cannot test in operating circuit |
| Definitive results | Requires good soldering skills |

**When Out-of-Circuit Testing is Required:**
- In-circuit results are ambiguous
- Precision measurement needed
- Component characterization required
- Failure mode needs confirmation

**Decision Matrix:**

| Situation | Recommended Approach |
|-----------|---------------------|
| Initial diagnosis | In-circuit first |
| Ambiguous in-circuit result | Out-of-circuit for confirmation |
| High-value component | In-circuit first, out-of-circuit if needed |
| Production repair (time critical) | In-circuit with higher false-positive tolerance |
| Critical application (medical, aerospace) | Out-of-circuit for definitive results |

**Expert Insight:** Expert technicians develop intuition for when in-circuit readings are reliable. A resistance reading across a capacitor that shows 0.1Ω is clearly a short (capacitor can't be that low). A reading of 100kΩ across the same capacitor might be the capacitor itself or a parallel resistor - requires further investigation.

---

## 1.3 Diagnostic Efficiency Metrics

Expert troubleshooting is not just about finding faults - it's about finding them efficiently. These metrics help optimize diagnostic sequences.

### 1.3.1 Diagnostic Yield

**Definition:** The percentage of possible fault locations that a test can eliminate.

**Calculating Yield:**
```
YIELD = (Fault Locations Eliminated / Total Possible Fault Locations) × 100%
```

**Example - DC Bus Voltage Test:**
```
Total fault locations in SMPS: ~20 major components
DC Bus Present eliminates: AC input, fuse, EMI filter, bridge, bulk cap = 5 components
DC Bus Absent eliminates: MOSFET, transformer, output diode, output caps, feedback = 8 components

YIELD = 8/20 = 40% (minimum)
YIELD = 5/20 = 25% (if present)

Either outcome eliminates significant portion → HIGH YIELD TEST
```

**Yield Categories:**

| Yield | Category | Example Tests |
|-------|----------|---------------|
| >40% | High Yield | DC Bus voltage, Output voltage |
| 20-40% | Medium Yield | Component resistance, Gate drive |
| <20% | Low Yield | Individual component test, Visual inspection |

### 1.3.2 Test Cost Factors

**Time Cost:**
| Test | Time Required | Notes |
|------|---------------|-------|
| Visual inspection | 1-2 min | No tools needed |
| DC Bus voltage | 30-60 sec | With meter ready |
| MOSFET resistance | 1-2 min | Requires probe access |
| ESR measurement | 2-3 min | May need capacitor access |
| Gate waveform | 3-5 min | Requires oscilloscope setup |
| Out-of-circuit test | 10-20 min | Desoldering required |

**Equipment Cost:**
| Test | Minimum Equipment | Professional Equipment |
|------|-------------------|------------------------|
| Voltage measurement | Basic multimeter ($20) | True RMS meter ($100+) |
| Resistance measurement | Basic multimeter ($20) | 4-wire meter ($200+) |
| ESR measurement | ESR meter ($30) | LCR meter ($200+) |
| Waveform analysis | USB scope ($100) | 100MHz+ scope ($500+) |
| Thermal analysis | IR thermometer ($30) | IR camera ($300+) |

**Risk Cost:**
| Test | Risk Level | Risk Description |
|------|------------|------------------|
| Visual inspection | None | No electrical contact |
| Output voltage (secondary) | Low | Low voltage, safe |
| DC Bus voltage (primary) | High | Lethal voltage present |
| Gate drive measurement | High | Requires powered primary side |
| Component removal | Medium | Possible PCB damage |

**Skill Cost:**
| Test | Skill Level | Training Required |
|------|-------------|-------------------|
| Visual inspection | Basic | Minimal |
| Voltage/resistance measurement | Basic | 1-2 hours |
| ESR measurement | Intermediate | 2-4 hours |
| Oscilloscope measurements | Intermediate | 8-16 hours |
| Signal injection testing | Advanced | 20+ hours |

### 1.3.3 Efficiency Formula

**Formula:**
```
DIAGNOSTIC EFFICIENCY = (YIELD × PROBABILITY) / (TIME × RISK × SKILL)

Where:
  YIELD = Percentage of circuit eliminated (0-1)
  PROBABILITY = Prior probability of fault in eliminated section (0-1)
  TIME = Normalized time cost (1-10 scale)
  RISK = Normalized risk factor (1-10 scale)
  SKILL = Normalized skill requirement (1-10 scale)
```

**Example Calculation - DC Bus Voltage Test:**
```
YIELD = 0.40 (eliminates 40% of circuit)
PROBABILITY = 0.50 (fault equally likely in either half)
TIME = 2 (30-60 seconds, relatively fast)
RISK = 7 (lethal voltage present)
SKILL = 3 (basic multimeter skills)

EFFICIENCY = (0.40 × 0.50) / (2 × 7 × 3) = 0.20 / 42 = 0.0048
```

**Example Calculation - Output Voltage Test:**
```
YIELD = 0.30 (eliminates 30% of circuit)
PROBABILITY = 0.50
TIME = 1 (very fast)
RISK = 2 (low voltage, safe)
SKILL = 2 (basic skills)

EFFICIENCY = (0.30 × 0.50) / (1 × 2 × 2) = 0.15 / 4 = 0.0375
```

**Interpretation:** Output voltage test has higher efficiency due to lower risk and skill requirements, despite lower yield. This is why experts often start with safe, easy tests.

### 1.3.4 Test Sequencing Optimization

**Optimal Sequence Principles:**

1. **High-yield tests first** - Eliminate large portions of circuit quickly
2. **Safe tests before risky tests** - Gather information without danger
3. **Easy tests before difficult tests** - Quick wins before deep investigation
4. **Probability-weighted** - Test most likely faults first within eliminated area

**Optimized Sequence for "Dead Unit" Symptom:**

```
SEQUENCE ORDER (by efficiency):

1. VISUAL INSPECTION
   - Yield: Low (10%)
   - Time: 1 min
   - Risk: None
   - Skill: Basic
   - WHY FIRST: Zero risk, fast, can find obvious faults

2. OUTPUT VOLTAGE TEST
   - Yield: Medium (30%)
   - Time: 30 sec
   - Risk: Low
   - Skill: Basic
   - WHY SECOND: Safe, fast, eliminates output section

3. DC BUS VOLTAGE TEST
   - Yield: High (40%)
   - Time: 1 min
   - Risk: High
   - Skill: Basic
   - WHY THIRD: High yield justifies risk, but after safe tests

4. MOSFET RESISTANCE TEST
   - Yield: Medium (20%)
   - Time: 2 min
   - Risk: Medium (discharged circuit)
   - Skill: Basic
   - WHY FOURTH: Targeted test based on previous results

5. GATE DRIVE WAVEFORM
   - Yield: Medium (15%)
   - Time: 5 min
   - Risk: High
   - Skill: Intermediate
   - WHY FIFTH: Requires oscilloscope, powered circuit
```

**Expert Insight:** The optimal sequence is NOT purely probability-based. A test with 60% probability but high risk should come AFTER a test with 40% probability but zero risk. The efficiency formula captures this trade-off.

---

## 1.4 Failure Mode Analysis

Understanding how components fail is essential for efficient diagnosis. Each component has characteristic failure modes with predictable signatures.

### 1.4.1 Component Failure Modes

**Electrolytic Capacitors:**

| Failure Mode | Probability | Mechanism | Detection Method |
|--------------|-------------|-----------|------------------|
| High ESR | 40% | Electrolyte evaporation, drying | ESR meter, ripple voltage |
| Capacitance loss | 30% | Electrolyte depletion | Capacitance meter |
| Open circuit | 15% | Connection failure, lead corrosion | Capacitance/ESR meter |
| Short circuit | 10% | Dielectric breakdown | Resistance measurement |
| Venting/bulging | 5% | Gas generation from overheating | Visual inspection |

**Failure Progression:**
```
NORMAL → ESR INCREASES → CAPACITANCE DROPS → INTERNAL HEATING → 
PRESSURE BUILDS → VENTING → COMPLETE FAILURE
```

**MOSFETs:**

| Failure Mode | Probability | Mechanism | Detection Method |
|--------------|-------------|-----------|------------------|
| Drain-Source short | 60% | Avalanche breakdown, thermal runaway | D-S resistance (<10Ω) |
| Gate-Source short | 20% | Gate oxide puncture (ESD, overvoltage) | G-S resistance (<100Ω) |
| Gate-Source leakage | 10% | Partial oxide damage | G-S leakage current |
| Drain-Source open | 5% | Bond wire lift | D-S resistance (open) |
| Gate open | 5% | Gate connection failure | No gate response |

**Failure Indicators:**
```
D-S SHORT: Fuse blows, no output, 0Ω D-S resistance
G-S SHORT: No switching, gate drive clamped, controller may be damaged
D-S OPEN: DC bus present, no switching, MOSFET cold
GATE OPEN: No switching, gate signal present at driver but not at MOSFET
```

**Diodes (Including Schottky):**

| Failure Mode | Probability | Mechanism | Detection Method |
|--------------|-------------|-----------|------------------|
| Short circuit | 50% | Forward overcurrent, thermal | Forward/reverse resistance |
| Open circuit | 30% | Bond wire failure, thermal stress | Forward voltage drop |
| Increased leakage | 15% | Junction damage | Reverse leakage current |
| Increased forward voltage | 5% | Junction degradation | Forward voltage test |

**Schottky Diode Specifics:**
- More prone to short failure than standard diodes
- Lower forward voltage (0.2-0.4V vs 0.6-0.7V)
- Higher leakage in normal operation
- Very sensitive to overvoltage and overcurrent

**Resistors:**

| Failure Mode | Probability | Mechanism | Detection Method |
|--------------|-------------|-----------|------------------|
| Open circuit | 70% | Overcurrent, thermal stress | Resistance measurement |
| Value increase | 20% | Partial damage, aging | Resistance measurement |
| Value decrease | 5% | Contamination, moisture | Resistance measurement |
| Noise increase | 5% | Partial damage | Scope under operating conditions |

**Power Resistor Specifics:**
- Higher failure rate than signal resistors
- Thermal cycling causes mechanical stress
- Often fail open to protect circuit

**Transformers:**

| Failure Mode | Probability | Mechanism | Detection Method |
|--------------|-------------|-----------|------------------|
| Shorted turns | 40% | Insulation breakdown | Ring test, inductance |
| Open winding | 30% | Wire break, connection failure | Continuity test |
| Primary-secondary short | 10% | Insulation failure | Isolation test |
| Core damage | 10% | Overheating, physical damage | Inductance, visual |
| Inter-winding short | 10% | Insulation failure | Ring test, inductance |

**Transformer Failure Indicators:**
```
SHORTED TURNS: Reduced inductance, overheating, reduced output
OPEN WINDING: No output, infinite resistance
PRI-SEC SHORT: Safety hazard! Output has primary voltage reference
```

### 1.4.2 Failure Cascades

**Principle:** A single component failure often triggers a cascade of secondary failures. Understanding cascade patterns helps identify root cause vs victim components.

**Common Cascade Patterns:**

**Pattern 1: Secondary Diode Short Cascade**
```
ROOT CAUSE: Secondary Schottky diode shorts
    │
    └─► EFFECT 1: Transformer secondary effectively shorted
        │
        └─► EFFECT 2: Reflected impedance to primary drops
            │
            └─► EFFECT 3: Primary current increases dramatically
                │
                └─► EFFECT 4: MOSFET thermal stress increases
                    │
                    └─► EFFECT 5: MOSFET fails short (D-S)
                        │
                        └─► EFFECT 6: DC bus shorted
                            │
                            └─► EFFECT 7: Massive current through rectifier
                                │
                                └─► SYMPTOM: Fuse blows
```

**Key Insight:** The fuse is the LAST component to fail. Replacing fuse + MOSFET without addressing the diode guarantees recurrence.

**Pattern 2: Bulk Capacitor Degradation Cascade**
```
ROOT CAUSE: Bulk capacitor ESR increases
    │
    └─► EFFECT 1: DC bus ripple increases
        │
        └─► EFFECT 2: MOSFET sees voltage spikes
            │
            └─► EFFECT 3: MOSFET avalanche stress
                │
                └─► EFFECT 4: MOSFET degradation
                    │
                    └─► EFFECT 5: Switching becomes erratic
                        │
                        └─► EFFECT 6: Output instability
                            │
                            └─► SYMPTOM: Intermittent output, noise
```

**Pattern 3: Feedback Loop Failure Cascade**
```
ROOT CAUSE: Optocoupler degradation
    │
    └─► EFFECT 1: Feedback signal weakened
        │
        └─► EFFECT 2: Controller sees lower output
            │
            └─► EFFECT 3: Controller increases duty cycle
                │
                └─► EFFECT 4: Output voltage rises
                    │
                    └─► EFFECT 5: OVP may activate
                        │
                        └─► SYMPTOM: Overvoltage or cycling
```

**Cascade Analysis Checklist:**
When a failed component is found, always check:
- [ ] What could have caused this component to fail?
- [ ] What other components may have been damaged by this failure?
- [ ] Are there components in the cascade path that should be tested?
- [ ] Is the found component the root cause or a victim?

### 1.4.3 Latent vs Patent Failures

**Patent Failures:** Visible symptoms present, equipment not functioning correctly.

**Latent Failures:** Hidden failures not yet causing symptoms, but will cause future failures.

**Detecting Latent Failures:**

| Latent Failure | Detection Method | Why It Matters |
|----------------|------------------|----------------|
| Capacitor ESR increase | ESR measurement | Will cause future instability |
| Solder joint degradation | Visual inspection, thermal cycling | Will cause intermittent connection |
| MOSFET gate oxide damage | Gate leakage test | Will progress to complete failure |
| Transformer insulation degradation | Hi-pot test, ring test | Will progress to shorted turns |
| Connector contact oxidation | Contact resistance test | Will cause intermittent connection |

**Latent Failure Detection Strategy:**
```
1. DURING REPAIR: Test related components even if not obviously failed
2. AFTER REPAIR: Run stress test to reveal latent failures
3. PREVENTIVE: Periodic testing of critical components
```

**Expert Insight:** A significant portion of "sudden" failures had latent precursors that could have been detected. The MOSFET that "suddenly" failed short may have had gate oxide damage for weeks.

---

## 1.5 Safety-Critical Considerations

SMPS troubleshooting involves lethal voltages. Safety must be embedded in every diagnostic procedure.

### 1.5.1 Hazardous Energy Sources

**Primary Side Hazards:**

| Hazard | Voltage/Energy | Location | Danger Level |
|--------|----------------|----------|--------------|
| AC Input | 115V/230V RMS | Before bridge rectifier | LETHAL |
| DC Bus | 155V-340V DC | Bulk capacitor | LETHAL |
| MOSFET Drain | Up to 600V+ peaks | MOSFET drain | LETHAL |
| Stored Energy | 10-50 Joules | Bulk capacitor | LETHAL |

**Energy Calculation:**
```
E = ½ × C × V²

Example: 100µF capacitor at 310V
E = 0.5 × 0.0001F × (310V)² = 4.8 Joules

10 Joules to chest can cause fibrillation
50 Joules is potentially lethal
```

**Safe Discharge Procedure:**
```
1. DISCONNECT AC POWER
2. WAIT 5 MINUTES for natural discharge
3. VERIFY with multimeter that DC bus is <50V
4. If still charged, use discharge resistor:
   - 100kΩ 5W resistor across capacitor terminals
   - Wait 30 seconds
   - Verify voltage is near zero
5. SHORT capacitor terminals with insulated probe
   - Only after verifying near-zero voltage
   - Confirms complete discharge
```

**Discharge Resistor Selection:**
```
R = V² / P

For 310V and 5W resistor:
R = (310)² / 5 = 19,220Ω minimum

Use 100kΩ for safety margin
Discharge time constant τ = R × C = 100kΩ × 100µF = 10 seconds
Wait 5τ = 50 seconds for 99% discharge
```

### 1.5.2 Isolation Requirements

**When Isolation Transformer is Required:**
- Oscilloscope measurements on primary side
- Any test equipment with ground reference
- Working on live primary circuits
- Testing with AC power applied

**Why Isolation Matters:**
```
WITHOUT ISOLATION:
   AC Hot ────┬──── Circuit
              │
   Scope GND ─┴──── Earth Ground
   
   If probe touches DC bus:
   DC Bus (310V) ─── Scope GND ─── Earth
   = SHORT CIRCUIT through scope!
   = Destroyed scope, possible electrocution

WITH ISOLATION TRANSFORMER:
   AC Hot ────┬──── Isolation ──── Circuit
              │         │
   Scope GND ─┴─────────┴─── No earth reference
   
   Probe can touch any point safely
   (Still dangerous - voltage is still lethal!)
```

**Ground Reference Issues:**
```
PROBLEM: Oscilloscope ground is earth-referenced
SOLUTIONS:
1. Use isolation transformer (best)
2. Use differential probe (best for high voltage)
3. Use battery-powered scope (inherently isolated)
4. Float the scope (DANGEROUS - not recommended)
```

**Safety Rules for Primary Side Testing:**
1. Always use isolation transformer when using grounded test equipment
2. Never touch primary side components with AC connected
3. Discharge bulk capacitor before any physical contact
4. Use one hand only when probing live circuits (reduces current path through heart)
5. Have another person present when working on live high-voltage circuits

### 1.5.3 Protection Circuit Behavior

**Understanding Protection Circuits:**

Protection circuits are designed to prevent catastrophic failure. Understanding their behavior helps distinguish protection activation from component failure.

**Over-Voltage Protection (OVP):**
```
TRIGGER: Output voltage exceeds threshold (typically 130-150% of nominal)
RESPONSE: Shutdown or crowbar (intentional short)
INDICATORS: 
  - Output drops to zero suddenly
  - May reset after power cycle
  - No component damage if working correctly

DISTINGUISH FROM FAILURE:
  - OVP: Output was high before shutdown
  - Failure: Output never reached correct level
```

**Over-Current Protection (OCP):**
```
TRIGGER: Output current exceeds threshold (typically 110-150% of rated)
RESPONSE: Shutdown or hiccup mode
INDICATORS:
  - Output cycles on/off (hiccup)
  - Works with reduced load
  - May be load fault, not PSU fault

DISTINGUISH FROM FAILURE:
  - OCP: Works with load disconnected
  - Failure: No output even without load
```

**Thermal Protection:**
```
TRIGGER: Internal temperature exceeds threshold (typically 90-110°C)
RESPONSE: Shutdown until temperature drops
INDICATORS:
  - Works when cold, fails when warm
  - Thermal imaging shows hot spot
  - Fan failure or blocked ventilation

DISTINGUISH FROM FAILURE:
  - Thermal: Works after cooling period
  - Failure: No output regardless of temperature
```

**Protection vs Failure Decision Tree:**
```
OUTPUT = 0V?
    │
    ├─► YES
    │   │
    │   ├─► Disconnect load, retry
    │   │   ├─► Works? → OCP or load fault
    │   │   └─► Still dead? → Continue
    │   │
    │   ├─► Cool down, retry
    │   │   ├─► Works? → Thermal protection
    │   │   └─► Still dead? → Continue
    │   │
    │   └─► Power cycle
    │       ├─► Works briefly? → OVP or latch-up
    │       └─► Still dead? → Component failure
    │
    └─► NO (some output)
        └─► Check output level and stability
```

---

## 1.6 RAG-Specific Optimization

The documentation structure must be optimized for retrieval-augmented generation. These strategies ensure the right information is retrieved at the right time.

### 1.6.1 Symptom-First Organization

**Principle:** Users search by what they observe. Documentation must be organized around symptoms, not components.

**Symptom Taxonomy:**

```
LEVEL 1: Primary Symptom Category
├── No Output
│   ├── Complete dead (no LED, no fan)
│   ├── Fuse blows immediately
│   ├── Output cycling/hiccup
│   └── Output present but wrong voltage
├── Output Present but Degraded
│   ├── Low output voltage
│   ├── High output voltage
│   ├── Excessive ripple
│   └── Unstable output
├── Thermal Issues
│   ├── Overheating
│   ├── Thermal shutdown
│   └── Running too cool
└── Intermittent Issues
    ├── Intermittent output
    ├── Load-dependent failure
    └── Temperature-dependent failure
```

**Symptom-to-Diagnostic Mapping:**
```
SYMPTOM: "Unit completely dead"
    │
    └─► RETRIEVE: SIG-001 (Unit Completely Dead)
        │
        └─► RETRIEVE: SYS-001 (System Not Powering On)
            │
            └─► RETRIEVE: SUB-001 (Input/Power Section)
                │
                └─► RETRIEVE: MEAS-001 (DC Bus Voltage)
```

**Chunk Title Format for Symptom Retrieval:**
```
SIG-XXX: [Observable Symptom] — [Distinguishing Details]

Examples:
SIG-001: Unit Completely Dead — No LED, No Fan, No Output
SIG-002: Fuse Blows Immediately — On Power-Up
SIG-003: Output Cycling — Hiccup Mode, 1-2 Hz
SIG-004: Low Output Voltage — 8-10V Instead of 12V
```

### 1.6.2 Decision Tree Encoding

**Principle:** Each decision point in a diagnostic sequence is a separate chunk. This allows the RAG system to retrieve the next step based on current findings.

**Decision Tree Chunk Structure:**
```
## DEC-XXX: [Decision Point Name]

**Context:** [What situation triggers this decision]
**Previous Step:** [What was just tested]
**Finding:** [What the test result was]

**Decision Logic:**
| Finding | Interpretation | Next Action |
|---------|----------------|-------------|
| Result A | Meaning A | RETRIEVE: DEC-YYY or MEAS-XXX |
| Result B | Meaning B | RETRIEVE: DEC-ZZZ or SIG-XXX |

**Related Chunks:** [Links to all possible next steps]
```

**Example:**
```markdown
## DEC-001: DC Bus Voltage Result

**Context:** Testing DC Bus voltage as first diagnostic step
**Previous Step:** None (initial test)
**Finding:** DC Bus voltage measurement result

**Decision Logic:**
| Finding | Interpretation | Next Action |
|---------|----------------|-------------|
| 155V or 310V (normal) | Input section OK | RETRIEVE: DEC-002 (Switching Stage) |
| 0V (absent) | Input section fault | RETRIEVE: DEC-003 (Input Fault) |
| 50-100V (low) | Bulk cap or selector issue | RETRIEVE: DEC-004 (Capacitor Analysis) |
| High ripple (>30Vpp) | Bulk cap ESR failure | RETRIEVE: MEAS-005 (ESR Test) |

**Related Chunks:** DEC-002, DEC-003, DEC-004, MEAS-005
```

**Decision Tree Flow:**
```
DEC-001 (DC Bus Result)
    │
    ├─► Normal ──► DEC-002 (Switching Stage)
    │                   │
    │                   ├─► Gate Present ──► DEC-005 (Transformer)
    │                   └─► Gate Absent ──► DEC-006 (Controller)
    │
    ├─► Absent ──► DEC-003 (Input Fault)
    │                   │
    │                   ├─► Fuse OK ──► DEC-007 (Bridge Rectifier)
    │                   └─► Fuse Blown ──► DEC-008 (Short Investigation)
    │
    └─► Low ──► DEC-004 (Capacitor Analysis)
                        │
                        ├─► ESR High ──► REP-002 (Cap Replacement)
                        └─► Selector Wrong ──► REP-003 (Selector Fix)
```

### 1.6.3 Cross-Reference Strategy

**Principle:** Related chunks link to each other, enabling navigation through diagnostic sequences.

**Cross-Reference Types:**

| Reference Type | Purpose | Format |
|----------------|---------|--------|
| Prerequisite | What must be done first | `**Prerequisites:** MEAS-001, DEC-001` |
| Next Step | What to do after this | `**Next Steps:** DEC-002, DEC-003` |
| Related | Related information | `**Related:** COMP-001, CAUS-001` |
| Alternative | Other approaches | `**Alternatives:** MEAS-006, MEAS-007` |
| Detail | More detailed information | `**Details:** COMP-001, COMP-002` |

**Cross-Reference Density:**
```
MINIMUM: 3 cross-references per chunk
OPTIMAL: 5-7 cross-references per chunk
MAXIMUM: 10 cross-references (avoid clutter)

Every chunk should link to:
- At least one prerequisite (if applicable)
- At least one next step (if applicable)
- At least one related chunk for context
```

**Cross-Reference Example:**
```markdown
## MEAS-003: MOSFET Drain-Source Resistance

**Purpose:** Test for MOSFET D-S short (most common failure mode)
**Prerequisites:** 
- DC bus discharged (SAFETY-001)
- AC power disconnected

⚠️ **SAFETY:** Verify DC bus voltage is <5V before proceeding

**Procedure:**
1. Set multimeter to resistance mode, 200Ω range
2. Place black probe on MOSFET source (usually center pin or tab)
3. Place red probe on MOSFET drain
4. Record resistance value

**Decision Logic:**
| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| <10Ω | D-S short (failed) | RETRIEVE: COMP-001, CAUS-001 |
| 10Ω-100kΩ | Degraded (marginal) | RETRIEVE: COMP-001, MEAS-004 |
| >100kΩ | Normal | RETRIEVE: DEC-002 |

**Related Chunks:** 
- COMP-001 (MOSFET Fault Model) - failure modes
- CAUS-001 (MOSFET Failure Cascade) - what caused this
- SAFETY-001 (Capacitor Discharge) - prerequisite
- DEC-002 (Switching Stage Decision) - next step
- MEAS-004 (Gate-Source Test) - alternative test
```

---

## 1.7 Validation of System-Subsystem-Component Approach

### 1.7.1 Is System-Subsystem-Component Hierarchy Optimal?

**Assessment:** The System-Subsystem-Component hierarchy is a valid approach, but has limitations that experts address through additional strategies.

**Strengths:**
- Provides clear organizational structure
- Aligns with probability-based prioritization
- Easy to understand and follow
- Works well for straightforward failures

**Limitations:**
- Does not capture functional relationships across subsystems
- Does not handle feedback loops well
- May miss cascade failures that span subsystems
- Can lead to tunnel vision on one subsystem

**Expert Enhancement:** Combine hierarchy with functional block analysis:
```
HIERARCHY: System → Subsystem → Component
    +
FUNCTIONAL: Power Path, Control Path, Protection Path
    =
HYBRID APPROACH: Use hierarchy for initial organization,
                  use functional analysis for complex failures
```

### 1.7.2 Is Probability-Based Traversal Optimal?

**Assessment:** Probability-based traversal is efficient for common failures but can be suboptimal for edge cases.

**When Probability Works Well:**
- Common failure modes (MOSFET short, capacitor degradation)
- Limited information about the specific failure
- Time-critical troubleshooting

**When Probability Can Fail:**
- Unusual failure modes (manufacturing defect, design flaw)
- Multiple simultaneous failures
- Cascade failures where the root cause is low probability

**Expert Enhancement:** Use efficiency formula instead of pure probability:
```
EFFICIENCY = (YIELD × PROBABILITY) / (TIME × RISK × SKILL)

This accounts for:
- How much the test eliminates (yield)
- How likely the fault is (probability)
- How long the test takes (time)
- How dangerous the test is (risk)
- How much skill is required (skill)

A lower-probability test may be done first if it has:
- High yield
- Low time cost
- Low risk
- Low skill requirement
```

### 1.7.3 What Would an Expert Do Differently?

**Expert vs Novice Comparison:**

| Aspect | Novice Approach | Expert Approach |
|--------|-----------------|-----------------|
| Starting point | Follow manual sequentially | Assess situation, choose optimal entry |
| Test selection | Test in order listed | Select tests based on efficiency |
| Information use | Use only current test result | Integrate all available information |
| Pattern recognition | Match to documented patterns | Recognize patterns plus variations |
| Failure cascades | Fix obvious failure | Trace cascade to root cause |
| Safety | Follow rules by rote | Understand why rules exist |
| Tool selection | Use available tools | Select optimal tool for task |
| Time management | Thorough but slow | Efficient, knows when to skip |

**Expert Strategies Not in Basic Hierarchy:**

1. **Half-Split First:** Before diving into subsystems, use half-split to eliminate large portions
2. **Safe Before Risky:** Do all safe tests before any risky tests, regardless of probability
3. **Functional Cross-Check:** When subsystem approach stalls, switch to functional analysis
4. **Cascade Tracing:** When a failed component is found, always trace the cascade
5. **Latent Failure Check:** After repair, check for latent failures that could cause recurrence
6. **Stimulus-Response:** For intermittent or marginal failures, use dynamic testing

**Recommended Hybrid Approach:**
```
1. INITIAL ASSESSMENT
   - Visual inspection (zero risk)
   - Output voltage test (low risk)
   - Gather information about failure circumstances

2. HALF-SPLIT ENTRY
   - DC Bus voltage test (high yield)
   - Eliminates 50% of circuit

3. PROBABILITY-WEIGHTED SUBSYSTEM
   - Within remaining section, use probability order
   - But consider efficiency formula for test selection

4. FUNCTIONAL ANALYSIS (if needed)
   - For complex failures, analyze functional blocks
   - Check feedback loops, protection circuits

5. CASCADE TRACING
   - When failed component found, trace cascade
   - Identify root cause vs victim

6. LATENT FAILURE CHECK
   - After repair, stress test
   - Check related components
```

---

## 1.8 System-Subsystem-Component Hierarchy

The diagnostic approach follows a three-level hierarchy with probability-weighted traversal:

```
SYSTEM (Overall Equipment)
  └── SUBSYSTEM 1: Input/Power Section
        ├── Component: Fuse (40% probability when this subsystem is faulty)
        ├── Component: Bridge Rectifier (30%)
        ├── Component: Bulk Capacitor (20%)
        └── Component: Input Selector (10%)
  └── SUBSYSTEM 2: Switching Section
        ├── Component: MOSFET (50%)
        ├── Component: PWM Controller (30%)
        └── Component: Snubber Network (20%)
  └── SUBSYSTEM 3: Output Section
        ├── Component: Output Capacitors (35%)
        ├── Component: Schottky Diode (35%)
        └── Component: Feedback Network (30%)
```

### Probability-Weighted Traversal

**Always check the most probable first at each level:**

1. **System Level:** Identify which subsystem is most probable given the symptom
2. **Subsystem Level:** Within that subsystem, test components in probability order
3. **Component Level:** For each component, test failure modes in probability order

**Example:**
- Symptom: "Unit completely dead"
- System Level: Input/Power Section is most probable (60%)
- Subsystem Level: Within Input/Power, Fuse is most probable (40%)
- Component Level: For Fuse, open circuit is most probable failure mode (80%)

This approach minimizes diagnostic time by focusing on highest-probability paths first.

---

## 2. RAG Optimization Requirements

The documentation you generate will be **chunked and embedded into ChromaDB** for semantic retrieval. Follow these best practices:

### 2.1 Atomic Chunking

Each chunk must be **self-contained** and address **one concept only**. A retrieved chunk should be understandable without requiring other chunks.

**Good Example:**
```markdown
## SIG-001: Unit Completely Dead — No LED, No Fan, No Output

**Symptom Class:** Total Power Failure
**Observable:** No indication of any electrical activity
**First Test:** DC Bus Voltage
**Expected If Fault Here:** 0V on bulk capacitor
```

**Bad Example:**
```markdown
## Troubleshooting Guide

The power supply may fail due to various reasons including blown fuses, 
failed MOSFETs, capacitor degradation, or feedback loop issues. 
To troubleshoot, first check the fuse, then measure DC bus...
```

### 2.2 Diagnostic-Centric Titles

Titles must be **searchable and symptom-focused**:

| Good Title | Poor Title |
|------------|------------|
| `SIG-001: Unit Completely Dead — No LED, No Fan, No Output` | `Power Supply Issues` |
| `MEAS-003: MOSFET Drain-Source Resistance` | `Testing Components` |
| `COMP-001: Primary MOSFET Fault Model` | `About MOSFETs` |

### 2.3 Stable IDs for Retrieval

Use consistent ID prefixes for each chunk type:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `SYS-*` | System-Level Diagnostic Gates | `SYS-001`, `SYS-002` |
| `SUB-*` | Subsystem Diagnostic Gates | `SUB-001`, `SUB-002` |
| `SIG-*` | Failure Signatures | `SIG-001`, `SIG-002` |
| `MEAS-*` | Measurement Rules | `MEAS-001`, `MEAS-002` |
| `COMP-*` | Component Fault Models | `COMP-001`, `COMP-002` |
| `SG-*` | Subsystem Gates | `SG-001`, `SG-002` |
| `CAUS-*` | Causality Chains | `CAUS-001`, `CAUS-002` |
| `FIELD-*` | Field-Induced Faults | `FIELD-001`, `FIELD-002` |
| `AMB-*` | Ambiguity Resolution | `AMB-001`, `AMB-002` |
| `DS-*` | Diagnostic Strategies | `DS-001`, `DS-002` |
| `YD-*` | Diagnostic Yield Notes | `YD-001`, `YD-002` |
| `TE-*` | Time Estimates | `TE-001`, `TE-002` |
| `VI-*` | Visual Indicators | `VI-001`, `VI-002` |
| `RM-*` | Recurrence Risk Matrices | `RM-001`, `RM-002` |
| `PJ-*` | Probability Justifications | `PJ-001`, `PJ-002` |
| `REP-*` | Repair Procedures | `REP-001`, `REP-002` |

### 2.4 Cross-References Between Chunks

Each chunk must include a `Related Chunks` section linking to related IDs:

```markdown
**Related Chunks:** MEAS-001, MEAS-002, SG-001, COMP-001, CAUS-001
```

### 2.5 Probability Weights with Mechanistic Reasoning

Include probability percentages with **mechanistic explanations**:

```markdown
**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| MOSFET Drain-Source short | 60% | Highest electrical + thermal stress; avalanche breakdown |
| Bridge rectifier diode short | 25% | Surge damage; inrush stress; thermal breakdown |
| Bulk capacitor internal short | 10% | Dielectric breakdown; age-related; overvoltage event |
```

### 2.6 Decision Logic Tables

Include clear if-then-else decision tables:

```markdown
**Decision Logic:**
| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| Normal (155V/310V) | Input, fuse, rectifier, bulk cap OK | Test switching stage |
| Zero | Primary side fault | Test fuse, rectifier, bulk cap |
| Low (50-100V) | Bulk cap degraded or selector mismatch | Test ESR; verify selector |
```

### 2.7 Visual Indicators

Include visual inspection clues:

```markdown
**Visual Indicators:**
- Cracked or exploded package
- Burn marks on heatsink
- Discolored thermal compound
- PCB discoloration under device
```

### 2.8 Recurrence Risk Warnings

Warn about recurrence if root cause is not addressed:

```markdown
**Recurrence Risk:**
| Action | Risk | Outcome |
|--------|------|---------|
| Replace fuse only | 95%+ | Immediate re-blow |
| Replace fuse + MOSFET | 40% | Re-blow if MOSFET was victim, not cause |
| Replace fuse + verified root cause | <5% | Successful repair |
```

**Critical Principle:** Replacing a component without identifying the root cause results in HIGH recurrence risk. Every repair must include verification that the root cause was addressed.

**Root Cause Verification Checklist:**
- [ ] Identified component is the actual root cause, not a victim
- [ ] Checked upstream components that could have caused the failure
- [ ] Checked downstream components that may have been damaged
- [ ] Verified no contributing factors remain (ESR, thermal, environmental)

### 2.9 Time Estimates

Include diagnostic time estimates:

```markdown
**Time Estimate:** ~3–7 minutes (with cover open, tools ready)

**Sequence:**
1. Selector check: <15 s
2. Short checks: 1–3 min
3. DC bus measurement: 30–60 s
4. Vcc stability test: 1–2 min
```

### 2.10 Diagnostic Yield Notes

Explain why a test is ordered early:

```markdown
**Diagnostic Yield:** Highest — Single measurement eliminates ~50% of circuit in 10 seconds
**Why Ordered Early:** Highest "half-split" leverage; prevents wasting time on secondary when primary isn't powered
```

### 2.11 Subsystem Gates (Elimination Logic)

Document tests that eliminate entire subsystems:

```markdown
## SG-001: DC Bus Present Gate — Eliminates Input Path

**Gate Measurement:** MEAS-001 (DC Bus Voltage)

**Decision Logic:**
```
DC BUS VOLTAGE = 155V or 310V (normal)?
    │
    ├─► YES (Present)
    │   └─► ELIMINATES: AC input, fuse, EMI filter, bridge rectifier, bulk capacitor
    │       └─► PROCEED TO: SG-003 (Gate Waveform)
    │
    └─► NO (Absent/Low)
        └─► FAULT IN: Input path
            └─► PROCEED TO: MEAS-002 (Fuse), MEAS-004 (Bridge)
```
```

### 2.12 Causality Chains

Document nth-order failure propagations:

```markdown
## CAUS-005: Secondary Diode Short — Cascade Chain

```
SECONDARY DIODE SHORTS
  └─► Transformer secondary effectively shorted
      └─► Reflected impedance to primary drops
          └─► Primary current increases
              └─► MOSFET thermal stress increases
                  └─► MOSFET failure
```
```

### 2.13 Field-Induced Faults

Document faults caused by installation/environment:

```markdown
## FIELD-001: DC Output Cable Voltage Drop

**Symptom:** Output voltage correct at PSU terminals, but low at load
**Cause:** Excessive cable length or undersized gauge
**Mechanism:** I×R drop in cabling
**Test:** Measure voltage at both ends under load
**Resolution:** Shorten cable, increase gauge, or add remote sense
```

### 2.14 Safety Warnings

Use prominent safety tags for hazardous procedures:

```markdown
⚠️ **SAFETY:** Lethal voltage (155–310V DC); discharge capacitor before physical contact
```

---

## 3. Equipment Configuration Reference

The documentation must align with the equipment configuration in `data/equipment/cctv-psu-24w-v1.yaml`:

### Signals and Test Points

| Signal ID | Name | Test Point | Parameter | Unit |
|-----------|------|------------|-----------|------|
| `ac_input` | AC Input Voltage | AC_IN | voltage_rms | V |
| `bridge_output` | Bridge Rectifier Output | TP1 | voltage_dc | V |
| `output_12v` | 12V Output Rail | TP2 | voltage_dc | V |
| `feedback_ref` | Feedback Reference | TP3 | voltage_dc | V |
| `output_current` | Output Current | I_OUT | current | A |
| `u5_temperature` | U5 Case Temperature | U5 | temperature | °C |

### Thresholds

| Signal | Normal Range | Degraded | Fault States |
|--------|--------------|----------|--------------|
| `output_12v` | 11.4–12.6V | 10.8–13.2V | under_voltage <10.8V, over_voltage >13.2V |
| `feedback_ref` | 2.4–2.6V | 2.2–2.8V | failed <0.2V |
| `u5_temperature` | <60°C | 60–80°C | critical >95°C |

### Defined Faults

| Fault ID | Name | Primary Component |
|----------|------|-------------------|
| `output_rail_collapse` | Output Rail Collapse | U5 (Buck converter) |
| `overvoltage_output` | Overvoltage Output | R2 (Feedback resistor) |
| `thermal_shutdown` | Thermal Shutdown | U5 (Thermal management) |
| `excessive_ripple` | Excessive Output Ripple | C12 (Output capacitor) |
| `primary_side_failure` | Primary Side Input Fault | F1 (Input fuse) |

---

## 4. Image Reference Instruction

**Analyze the provided image at `docs/CCTV Power Supply Unit.jpeg`** to:

1. **Identify component locations** — Map component designators (U5, F1, C12, R2, etc.) to physical positions on the PCB
2. **Locate test points** — Identify where TP1, TP2, TP3, AC_IN, I_OUT are physically located
3. **Document visual landmarks** — Note distinctive visual features that help technicians orient themselves
4. **Identify safety-critical areas** — Highlight high-voltage zones (primary side) vs low-voltage zones (secondary side)
5. **Note component markings** — Read any visible part numbers, ratings, or silkscreen labels

Include image references in each chunk using this format:

```markdown
**IMG:** IMG_REF_<DESCRIPTOR>
```

For example:
- `IMG: IMG_REF_DEAD_UNIT`
- `IMG: IMG_REF_BLOWN_FUSE`
- `IMG: IMG_REF_DC_BUS_TESTPOINT`

---

## 5. Required Chunk Types

Generate documentation chunks for each of these categories:

### 5.1 System-Level Diagnostic Gates (SYS-*)

Document system-level diagnostic entry points with probability-ranked subsystem analysis:

**Example:**
```markdown
## SYS-001: System Not Powering On

**Symptom:** Complete system failure - no LED, no fan, no output
**System State:** Completely unresponsive

**Subsystem Probability Ranking:**
| Subsystem | Probability | Reasoning |
|-----------|-------------|-----------|
| Input/Power Section | 60% | No power reaching any stage; highest probability |
| Switching Section | 25% | Controller or MOSFET failure could prevent startup |
| Output Section | 15% | Secondary-side failure rarely causes complete silence |

**Diagnostic Sequence:**
1. Test subsystems in probability order
2. Start with SUB-001 (Input/Power Section Diagnostic Gate)
3. If Input/Power eliminated, proceed to SUB-002 (Switching Section)

**First Test:** MEAS-001 (DC Bus Voltage) - highest leverage measurement

**Related Chunks:** SUB-001, SUB-002, SUB-003, SIG-001, MEAS-001
```

### 5.2 Subsystem Diagnostic Gates (SUB-*)

Document subsystem-level diagnostic gates with probability-ranked component analysis:

**Example:**
```markdown
## SUB-001: Input/Power Section Diagnostic Gate

**Subsystem:** Input/Power Section
**Components in this subsystem:** AC input, EMI filter, Fuse, Bridge Rectifier, Bulk Capacitor, Input Selector

**Component Probability Ranking (when this subsystem is faulty):**
| Component | Probability | Failure Mode | Mechanism |
|-----------|-------------|--------------|-----------|
| Fuse | 40% | Open circuit | Overcurrent protection; sacrificial device |
| Bridge Rectifier | 30% | Diode short | Inrush stress; surge damage; thermal breakdown |
| Bulk Capacitor | 20% | Open/High ESR | Age-related degradation; overvoltage |
| Input Selector | 10% | Wrong position | Misconfiguration; mechanical failure |

**Diagnostic Sequence:**
1. Visual inspection (fuse, burnt components)
2. MEAS-002 (Fuse continuity) - fastest test
3. MEAS-001 (DC Bus Voltage) - eliminates or confirms subsystem
4. MEAS-004 (Bridge Rectifier) - if DC bus absent and fuse OK

**Entry Criteria:** SYS-001 indicates Input/Power as most probable subsystem
**Exit Criteria:** DC bus voltage normal (155V/310V) eliminates this subsystem

**Related Chunks:** SYS-001, MEAS-001, MEAS-002, MEAS-004, COMP-002, COMP-003
```

### 5.3 Failure Signatures (SIG-*)

Document observable symptoms with:
- Symptom class
- Observable characteristics (visual, acoustic, thermal)
- Diagnostic implication
- Root cause candidates with probabilities
- First test to perform
- Related chunks

**Example:**
```markdown
## SIG-002: Fuse Blows Immediately On Power-Up

**Symptom Class:** Instantaneous Overcurrent
**Observable:** Fuse ruptures within <100ms of AC application
**Acoustic:** Possible audible pop
**Thermal:** Fuse element may show heat discoloration
**Visual:** Fuse element broken; may be blackened
**IMG:** IMG_REF_BLOWN_FUSE

**Diagnostic Implication:**
Hard short exists on DC bus side. Current path: AC → Rectifier → DC Bus → Short

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| MOSFET Drain-Source short | 60% | Highest electrical + thermal stress; avalanche breakdown |
| Bridge rectifier diode short | 25% | Surge damage; inrush stress; thermal breakdown |
| Bulk capacitor internal short | 10% | Dielectric breakdown; age-related; overvoltage event |
| Primary winding short to core | 5% | Insulation failure; manufacturing defect |

**Critical Rule:** Do NOT replace fuse before testing MOSFET D-S resistance

**Recurrence Risk:**
| Action | Risk | Outcome |
|--------|------|---------|
| Replace fuse only | 95%+ | Immediate re-blow |
| Replace fuse + MOSFET | 40% | Re-blow if MOSFET was victim, not cause |
| Replace fuse + verified root cause | <5% | Successful repair |

**Next Actions:** MEAS-003, MEAS-004, MEAS-005 (in order)
**Related Chunks:** MEAS-002, MEAS-003, MEAS-004, COMP-001, COMP-003, CAUS-001, AMB-003
```

### 5.2 Measurement Rules (MEAS-*)

Document test procedures with:
- Test point location
- Required instrument
- Safety warnings
- Expected values
- Decision logic table
- Diagnostic yield note

**Example:**
```markdown
## MEAS-001: DC Bus Voltage Measurement

**Test Point:** Bulk electrolytic capacitor positive to negative terminal
**Instrument:** Multimeter DC voltage, 400V+ range
**IMG:** IMG_REF_DC_BUS_TESTPOINT

⚠️ **SAFETY:** Lethal voltage (155–310V DC); discharge capacitor before physical contact

**Expected Values:**
| Input Voltage | Expected DC Bus |
|---------------|-----------------|
| 115VAC (selector on 115V) | 155–165V DC |
| 230VAC (selector on 230V) | 310–330V DC |

**Decision Logic:**
| Result | Interpretation | Next Action | Eliminates |
|--------|----------------|-------------|------------|
| Normal (155V/310V) | Input, fuse, rectifier, bulk cap functional | Test switching stage (MEAS-006) | 50% of circuit |
| Zero | Primary side fault | Test fuse (MEAS-002) | Secondary, feedback |
| Low (50–100V) | Bulk cap degraded or selector mismatch | Test ESR (MEAS-005); verify selector | — |
| High ripple (>30Vpp) | Bulk cap ESR failure | Replace bulk capacitor | — |

**Diagnostic Yield:** Highest — Single measurement eliminates ~50% of circuit in 10 seconds
**Related Chunks:** SG-001, SG-002, COMP-002, CAUS-001
```

### 5.3 Component Fault Models (COMP-*)

Document component failure modes with:
- Component description
- Failure probability with mechanistic reasoning
- Primary failure modes with probabilities
- Visual indicators
- Cascading damage chains
- Recurrence prevention notes

**Example:**
```markdown
## COMP-001: Primary MOSFET Fault Model

**Component:** Primary-side power MOSFET (N-channel, 600–800V rated)
**IMG:** IMG_REF_MOSFET_COMPONENT
**Failure Probability:** 35% (highest in system)

**Why 35% — Mechanistic Reasoning:**
| Stress Factor | Severity | Explanation |
|---------------|----------|-------------|
| Electrical stress | Extreme | Sustains full DC bus (310V) + switching spikes (can exceed 500V) |
| Thermal stress | High | Switching losses; heatsink interface critical |
| Avalanche stress | High | Voltage spikes from transformer leakage inductance |
| Current stress | High | Full primary current (can exceed 3A peak) |

**Primary Failure Modes:**
| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| Drain-Source short | 70% | Avalanche breakdown; thermal runaway | D-S <10Ω; fuse blows |
| Gate-Source short | 20% | Gate oxide puncture from ESD or dV/dt | G-S <100Ω; no gate drive |
| Open (rare) | 10% | Bond wire lift from thermal cycling | DC bus present, no switching, cold MOSFET |

**Visual Indicators:**
- Cracked or exploded package
- Burn marks on heatsink
- Discolored thermal compound
- PCB discoloration under device

**Cascading Damage:**
```
MOSFET shorts D-S
    └─► DC bus shorted
        └─► Massive current through rectifier
            └─► Fuse blows (protective sacrifice)
                └─► If fuse replaced without MOSFET test
                    └─► Immediate re-blow
```

**Recurrence Prevention:** After MOSFET replacement, verify bulk cap ESR and snubber integrity to prevent repeat failure.

**Related Chunks:** SIG-002, MEAS-003, CAUS-001, CAUS-005, CAUS-006
```

### 5.4 Subsystem Gates (SG-*)

Document elimination logic gates with:
- Gate measurement reference
- Decision tree (ASCII art)
- What is eliminated by each outcome
- Next steps

**Example:**
```markdown
## SG-001: DC Bus Present Gate — Eliminates Input Path

**Gate Measurement:** MEAS-001 (DC Bus Voltage)
**Time Cost:** 10–30 seconds

**Decision Logic:**
```
DC BUS VOLTAGE = 155V or 310V (normal)?
    │
    ├─► YES (Present)
    │   └─► ELIMINATES: AC input, fuse, EMI filter, bridge rectifier, bulk capacitor
    │       └─► PROCEED TO: SG-003 (Gate Waveform)
    │
    └─► NO (Absent/Low)
        └─► FAULT IN: Input path
            └─► PROCEED TO: MEAS-002 (Fuse), MEAS-004 (Bridge)
```

**Diagnostic Yield:** Eliminates ~50% of circuit in one measurement
**Related Chunks:** MEAS-001, MEAS-002, MEAS-004, SG-002
```

### 5.5 Causality Chains (CAUS-*)

Document failure propagation with ASCII trees:

**Example:**
```markdown
## CAUS-005: Secondary Diode Short — Cascade Chain

```
SECONDARY DIODE SHORTS
  └─► Transformer secondary effectively shorted
      └─► Reflected impedance to primary drops
          └─► Primary current increases
              └─► MOSFET thermal stress increases
                  └─► MOSFET failure
```

**Key Insight:** Secondary diode shorts are often the root cause of primary MOSFET failures. When MOSFET fails, always test secondary diode.

**Related Chunks:** COMP-001, MEAS-010, SIG-002, SIG-004
```

### 5.6 Field-Induced Faults (FIELD-*)

Document installation/environmental faults:

**Example:**
```markdown
## FIELD-001: DC Output Cable Voltage Drop

**Symptom:** Output voltage correct at PSU terminals, but low at load
**Cause:** Excessive cable length or undersized gauge
**Mechanism:** I×R drop in cabling
**IMG:** IMG_REF_CABLE_DROP

**Test Procedure:**
1. Measure voltage at PSU output terminals under load
2. Measure voltage at load end of cable under load
3. Calculate drop: V_psu - V_load

**Decision Logic:**
| Drop | Interpretation | Action |
|------|----------------|--------|
| <0.5V | Normal | Look elsewhere |
| 0.5–1.0V | Marginal | Consider upgrade for long runs |
| >1.0V | Excessive | Shorten cable, increase gauge, or add remote sense |

**Related Chunks:** SIG-005, AMB-002, MEAS-008
```

### 5.7 Ambiguity Resolution (AMB-*)

Document differentiation tests for similar symptoms:

**Example:**
```markdown
## AMB-001: Differentiating Causes of Output Cycling/Hiccup

**Symptom:** Output pulses on/off at 0.5–2 Hz rate

**Differentiation Tests:**
| Test | Result | Indicates |
|------|--------|-----------|
| Disconnect load | Cycling stops | Load overload or short |
| Disconnect load | Cycling continues | Internal PSU fault |
| DC bus during cycling | Stable 155/310V | Feedback or controller issue |
| DC bus during cycling | Droops significantly | Bulk capacitor fault |
| Output voltage at peak | ~12V briefly | Overload protection |
| Output voltage at peak | Never reaches 12V | Short circuit protection |

**Related Chunks:** SIG-007, MEAS-001, MEAS-005, SG-005
```

### 5.8 Diagnostic Yield Notes (YD-*)

Document why tests are ordered:

**Example:**
```markdown
## YD-001: Diagnostic Yield Note — DC Bus Measurement

**Applies To:** MEAS-001, SG-001, SG-002

**Diagnostic Yield:** Eliminates ~40–60% of the power chain in one reading
**Measurement Cost:** Low (10–30 s)
**Risk/Cost of Error:** High (live primary HV probing)
**Why Ordered Early:** Highest "half-split" leverage; prevents wasting time on secondary when primary isn't powered
```

### 5.9 Time Estimates (TE-*)

Document diagnostic time:

**Example:**
```markdown
## TE-001: Time Estimate — Fast Triage Path (Bench)

**Goal:** Reach a dominant root-cause bucket quickly (not full repair)
**Typical Time-to-Bucket:** ~3–7 minutes (with cover open, tools ready)

**Sequence:**
| Step | Action | Time |
|------|--------|------|
| 1 | Selector check | <15 s |
| 2 | Short checks (MOSFET, bridge, diode) | 1–3 min |
| 3 | DC bus measurement with limiter | 30–60 s |
| 4 | Vcc stability test | 1–2 min |
| 5 | Decision: upstream vs control vs secondary | — |
```

### 5.10 Visual Indicators (VI-*)

Document visual inspection clues:

**Example:**
```markdown
## VI-001: Visual Indicators — Primary MOSFET Catastrophic Failure

**Applies To:** COMP-001, SIG-002

**Clues (Ranked by Reliability):**
1. Cracked/holed MOSFET package; soot trail to heatsink
2. Discolored gate resistor area (often nearby small resistor runs hot during fault)
3. PCB charring around drain trace / snubber network

**Interpretation Rule:** Visual damage here strongly correlates with a hard primary short; still run MEAS-003 because the cause may be secondary.
```

### 5.11 Recurrence Risk Matrices (RM-*)

Document recurrence risks:

**Example:**
```markdown
## RM-001: Recurrence Risk Matrix — Fuse Blows

**Symptom:** FS-001 Fuse Blows Immediately

| If you replace only... | Recurrence Risk | Why it comes back |
|------------------------|-----------------|-------------------|
| Fuse | 95%+ | Hard short remains |
| Fuse + MOSFET | 40–70% | Secondary short still kills MOSFET |
| Fuse + MOSFET + Secondary diode | 5–15% | Possible bulk cap contribution |
| Full root cause analysis | <5% | Successful repair |

**Key Insight:** Fuse failure is a symptom, not a root cause. Always investigate before replacement.
```

### 5.12 Probability Justifications (PJ-*)

Document mechanistic reasoning for probabilities:

**Example:**
```markdown
## PJ-001: Probability Justification — Fuse Blown

**Question:** Why is MOSFET failure 60% probability when fuse blows?

**Mechanistic Reasoning:**
1. **Stress Exposure:** MOSFET sees highest electrical stress (310V DC + 500V+ spikes)
2. **Thermal Stress:** Switching losses create sustained thermal load
3. **Avalanche Events:** Leakage inductance causes repeated avalanche stress
4. **Failure Mode:** When MOSFET fails, it typically fails short (D-S), causing immediate fuse blow

**Contrast with Other Causes:**
- Bridge rectifier: Lower stress, protected by inrush limiting
- Bulk capacitor: Typically fails open or high ESR, not hard short
- Transformer: Rare failure mode, typically open rather than short

**Conclusion:** MOSFET is the component most likely to cause immediate fuse blow due to combination of high stress and short-circuit failure mode.
```

### 5.13 Repair Procedures (REP-*)

Document repair procedures with verification steps and root cause checklists:

**Example:**
```markdown
## REP-001: MOSFET Replacement Procedure

**Applies To:** COMP-001 (Primary MOSFET Fault Model)

⚠️ **SAFETY:** 
- Disconnect AC power and wait 5 minutes for capacitor discharge
- Verify DC bus voltage is 0V before proceeding
- Use ESD precautions when handling MOSFET

**Required Tools:**
- Soldering station (temperature controlled)
- Desoldering braid or vacuum pump
- Thermal compound
- Multimeter
- Replacement MOSFET (matching part number or equivalent)

**Repair Procedure:**
| Step | Action | Verification |
|------|--------|--------------|
| 1 | Remove old MOSFET | All leads cleared from PCB |
| 2 | Clean pads | No solder bridges, clean copper |
| 3 | Apply thermal compound to new MOSFET | Thin, even layer on back |
| 4 | Install new MOSFET | Proper orientation, leads through holes |
| 5 | Solder leads | No bridges, good fillets |
| 6 | Trim leads | No excess length |

**Verification Steps:**
1. **Gate-Source resistance:** Should be >1MΩ (MEAS-003)
2. **Drain-Source resistance:** Should be >100kΩ (MEAS-003)
3. **No solder bridges:** Visual inspection under magnification

**Root Cause Checklist (BEFORE powering on):**
- [ ] Secondary Schottky diode tested (MEAS-005) - could have caused overload
- [ ] Snubber network components tested - could have allowed avalanche
- [ ] Bulk capacitor ESR tested - could have caused instability
- [ ] Gate drive circuit tested - could have caused gate stress

**Power-On Test:**
1. Connect AC through current limiter (60W bulb in series)
2. Monitor DC bus voltage rise
3. Check for stable switching
4. Verify output voltage

**Related Chunks:** COMP-001, MEAS-003, MEAS-005, RM-001, CAUS-005
```

---

## 6. Root Cause Cascade Example

The following example demonstrates the complete diagnostic and repair process, emphasizing root cause analysis:

```markdown
## EXAMPLE: Root Cause Cascade — Fuse Blows Immediately

### OBSERVED SYMPTOM: Fuse Blows Immediately (SIG-002)

**Initial Presentation:** 
- Unit completely dead
- Visual inspection shows blown fuse
- No output, no LED

### NAIVE REPAIR (Wrong Approach):
```
1. Replace fuse
2. Power on
3. Fuse blows again (95% recurrence)
```

**Why This Fails:** The fuse is a PROTECTION DEVICE, not a root cause. The fuse blew because something downstream is shorted. Replacing the fuse without finding the short guarantees immediate re-blow.

### ROOT CAUSE ANALYSIS:

**Step 1: System-Level Assessment (SYS-001)**
- Symptom: Complete power failure
- Most probable subsystem: Input/Power Section (60%)

**Step 2: Subsystem-Level Assessment (SUB-001)**
- Within Input/Power Section, most probable component: Fuse (40%)
- But fuse is a symptom, not cause — must look downstream

**Step 3: Component-Level Testing**
```
SIG-002 → Test MOSFET D-S (MEAS-003)
    │
    ├─► MOSFET shorted (D-S < 10Ω)?
    │   └─► YES: MOSFET is a root cause candidate
    │       │
    │       └─► But WHY did MOSFET fail?
    │           ├─► Check secondary Schottky (MEAS-005) - could have caused overload
    │           ├─► Check snubber network - could have allowed avalanche
    │           └─► Check bulk cap ESR (MEAS-005) - could have caused instability
    │
    └─► NO: Test bridge rectifier (MEAS-004)
        └─► Continue probability-weighted traversal
```

**Step 4: Causality Chain Discovery**
```
ROOT CAUSE: Secondary Schottky diode shorted
    └─► Transformer secondary effectively shorted
        └─► Reflected impedance to primary drops
            └─► Primary current increases
                └─► MOSFET thermal stress increases
                    └─► MOSFET fails short (D-S)
                        └─► DC bus shorted
                            └─► Fuse blows (SYMPTOM)
```

### CORRECT REPAIR:
```
1. Replace secondary Schottky diode (root cause)
2. Replace MOSFET (victim of root cause)
3. Replace fuse (protection device that did its job)
4. Verify bulk cap ESR (contributing factor check)
5. Verify snubber network (contributing factor check)
6. Power on with current limiter
7. Verify stable operation
8. Full load test
```

### RECURRENCE RISK COMPARISON:
| Repair Approach | Recurrence Risk | Outcome |
|-----------------|-----------------|---------|
| Replace fuse only | 95%+ | Immediate re-blow |
| Replace fuse + MOSFET | 40-70% | MOSFET fails again (Schottky still shorted) |
| Replace fuse + MOSFET + Schottky | 5-15% | Possible bulk cap contribution |
| Full root cause analysis + all affected components | <5% | Successful repair |

**Key Lesson:** Every component in the causality chain must be identified and addressed. The fuse is the last link in the chain, not the first.
```

---

## 6. Expected Output Format

Generate a **single markdown document** with the following structure:

```markdown
# RAG-Optimized Diagnostic Documentation
## CCTV Power Supply Unit (12V 30A SMPS)

---

## RETRIEVAL INDEX

Complete chunk ID → Title mapping for direct lookup.

### Failure Signatures (SIG-*)
| ID | Title |
|----|-------|
| SIG-001 | Unit Completely Dead — No LED, No Fan, No Output |
| SIG-002 | Fuse Blows Immediately On Power-Up |
| ... | ... |

### Measurement Rules (MEAS-*)
| ID | Title |
|----|-------|
| MEAS-001 | DC Bus Voltage Measurement |
| ... | ... |

[Continue for all chunk types...]

---

## SECTION 1: FAILURE SIGNATURES (SIG-*)

[All SIG-* chunks...]

## SECTION 2: MEASUREMENT RULES (MEAS-*)

[All MEAS-* chunks...]

[Continue for all sections...]

---

## IMAGE REFERENCE INDEX

| Image ID | Description | Related Chunks |
|----------|-------------|----------------|
| IMG_REF_DEAD_UNIT | Photo of completely dead unit | SIG-001 |
| IMG_REF_DC_BUS_TESTPOINT | Location of DC bus test point | MEAS-001, SG-001 |
| ... | ... | ... |

---

*Document Version: 1.0*
*Generated: [Date]*
*Equipment: CCTV-PSU-24W-V1*
```

---

## 7. Quality Checklist

Before finalizing, verify each chunk includes:

- [ ] Stable ID with correct prefix
- [ ] Diagnostic-centric title
- [ ] Symptom class or purpose
- [ ] Observable characteristics
- [ ] Probability weights with mechanistic reasoning (where applicable)
- [ ] Decision logic table (where applicable)
- [ ] Safety warnings for hazardous procedures
- [ ] Image reference (IMG: IMG_REF_*)
- [ ] Related chunks cross-references
- [ ] Recurrence risk warnings (for fault-related chunks)
- [ ] Time estimates (for measurement/diagnostic chunks)
- [ ] Diagnostic yield notes (for measurement chunks)
- [ ] Root cause verification checklist (for repair procedures)
- [ ] System-Subsystem-Component hierarchy alignment (for SYS-* and SUB-* chunks)
- [ ] Causality chain documentation (for component failures)

---

## 8. Summary

Generate comprehensive RAG-optimized troubleshooting documentation for the CCTV Power Supply Unit that:

1. **Analyzes the provided image** to identify components, test points, and safety zones
2. **Uses atomic chunking** with one concept per chunk
3. **Includes all required chunk types** (SYS-*, SUB-*, SIG-*, MEAS-*, COMP-*, SG-*, CAUS-*, FIELD-*, AMB-*, DS-*, YD-*, TE-*, VI-*, RM-*, PJ-*, REP-*)
4. **Aligns with the equipment configuration** in `data/equipment/cctv-psu-24w-v1.yaml`
5. **Follows RAG best practices** for retrieval optimization
6. **Includes safety warnings** for all hazardous procedures
7. **Provides cross-references** between related chunks
8. **Documents field-induced faults** and environmental factors
9. **Includes recurrence risk matrices** to prevent repeat failures
10. **Provides time estimates** for diagnostic procedures
11. **Emphasizes root cause analysis** over symptom treatment
12. **Follows System-Subsystem-Component hierarchy** with probability-weighted traversal
13. **Includes repair procedures** with verification steps and root cause checklists
14. **Documents causality chains** to trace failures to their root causes

The output should be a single, comprehensive markdown document ready for chunking and ingestion into ChromaDB.
