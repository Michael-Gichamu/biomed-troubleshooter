# RAG-Optimized Diagnostic Documentation: CCTV-PSU-24W-V1

**Equipment:** CCTV Power Supply Unit - 12V 2A (24W)  
**PCB Marking:** SP-80M  
**Document Version:** 2.0  
**Purpose:** RAG retrieval for AI-powered troubleshooting agent  
**Target:** ChromaDB Vector Store

---

## 1. Equipment Overview

The CCTV-PSU-24W-V1 is a switched-mode power supply (SMPS) designed to provide stable 12V DC output for CCTV cameras. It accepts universal AC input (110-240V) and uses a flyback/forward converter topology.

**Key Specifications:**
- Input: 110-240V AC, 50/60Hz
- Output: 12V DC, 2A (24W rated)
- Topology: Flyback/Forward converter with PWM control

**PCB Layout Zones:**
| Zone | Components | Voltage Level |
|------|------------|---------------|
| Upper-left | Bridge rectifier, bulk capacitors, EMI filter | HIGH (110-380V DC) |
| Center | Power transformer (primary) | HIGH |
| Lower-center | PWM Controller (U5) | HIGH |
| Right edge | Primary MOSFET on heatsink | HIGH |
| Lower-right | Output capacitor (C12), Schottky diode | LOW (12V) |
| Center-bottom | Feedback network, optocoupler | LOW |

---

## 2. Power Flow Explanation

```
AC Input → Fuse (F1) → EMI Filter → Bridge Rectifier → Bulk Capacitor
                                                                  ↓
                                                            DC Bus (310V/155V)
                                                                  ↓
                                                            Primary MOSFET
                                                                  ↓
                                                            Power Transformer
                                                                  ↓
                                                            Output Schottky
                                                                  ↓
                                                            Output Capacitor (C12)
                                                                  ↓
                                                            12V Output
```

**Stage-by-Stage:**

1. **AC Input Stage:** AC mains enters through fuse F1 (250V 1A slow-blow), passes through EMI filter, then bridge rectifier converts to pulsating DC.

2. **DC Bus (Bulk Stage):** Bulk electrolytic capacitor smooths rectified AC to ~310V DC (230V input) or ~155V DC (115V input).

3. **Switching Stage:** PWM controller (U5) drives primary MOSFET at ~50-100kHz. MOSFET switches current through transformer primary, creating magnetic flux.

4. **Output Stage:** Transformer secondary output is rectified by Schottky diode, filtered by output capacitor C12, producing clean 12V DC.

5. **Feedback Loop:** Output voltage is sampled through feedback resistor network and optocoupler. Signal crosses to primary side, controlling PWM duty cycle to maintain 12V regulation.

---

## 3. Test Points and Expected Values

| Test Point | Location | Measurement | Normal Value | Fault Threshold |
|------------|----------|-------------|--------------|-----------------|
| TP1 (Bridge Output) | Near BR1, upper-right | DC Voltage | 280-380V DC | <250V or 0V |
| TP2 (Output Rail) | Near C12, lower-right | DC Voltage | 11.4-12.6V | <10.8V or >13.2V |
| TP3 (Feedback Ref) | Near U5, center | DC Voltage | 2.4-2.6V | <2.2V or >2.8V |
| F1 (Fuse) | Near AC input | Resistance | <0.1Ω (continuity) | Open |
| MOSFET D-S | Right edge, TO-220 | Resistance | >100kΩ | <10Ω (shorted) |
| Schottky Diode | Near C12, secondary | Forward Voltage | 0.15-0.45V | <0.1V (shorted) |
| C12 ESR | Output capacitor | ESR | <0.2Ω | >0.5Ω |

---

## 4. Signal Relationships

**How signals relate to faults:**

| If This Signal | And This Signal | Then This Fault Likely |
|----------------|-----------------|----------------------|
| output_12v = 0V | bridge_output = 0V | Input path failure (fuse, bridge) |
| output_12v = 0V | bridge_output = 310V | Switching failure (MOSFET, U5) |
| output_12v = low | feedback_ref = normal | Output capacitor ESR high |
| output_12v = high | feedback_ref = high | Feedback resistor R2 failed |
| output_12v = cycling | (any) | Overload or protection active |
| u5_temperature = critical | output_12v = 0V | Thermal shutdown (ventilation) |

**Signal Chain Logic:**

```
ac_input → bridge_output → dc_bus → primary_mosfet → transformer → schottky → output_12v → feedback_ref → u5_control

IF ac_input normal AND bridge_output = 0V
    THEN fault is in: fuse, bridge rectifier, or bulk capacitor

IF bridge_output normal AND output_12v = 0V  
    THEN fault is in: MOSFET, PWM controller, or transformer

IF output_12v low AND feedback_ref normal
    THEN fault is in: output capacitor C12 or Schottky diode

IF output_12v high AND feedback_ref high
    THEN fault is in: feedback resistor R2 or optocoupler
```

---

## 5. Normal Operation Description

**What "good" looks like:**

1. **Power-On Sequence:**
   - AC applied → Fuse intact → Bridge produces DC
   - Bulk capacitor charges → DC bus reaches ~310V (230V input)
   - PWM controller starts → MOSFET begins switching
   - Transformer transfers energy → Secondary produces pulsed output
   - Schottky rectifies → C12 filters → Output reaches 12V
   - Feedback loop locks → Output stabilizes at 12V ±0.2V

2. **Steady-State Indicators:**
   - No audible noise (transformer at proper frequency)
   - MOSFET and transformer warm but not hot (<60°C)
   - Output voltage stable at 11.4-12.6V under load
   - Ripple <50mVpp on output

3. **Load Response:**
   - Output voltage stays within 10.8-13.2V from no-load to full load
   - Transient response <100mV deviation on load change

---

## 6. Fault Signatures

### SIG-001: Unit Completely Dead — No Output, No LED

**Observable:** Zero output voltage, no indicators, complete silence on power-up.

**IF-THEN Reasoning:**

```
IF output_12v = 0V AND ac_input = 0V
    THEN check power cord, wall outlet, switch

IF output_12v = 0V AND ac_input normal AND bridge_output = 0V
    THEN fuse blown OR bridge failed

IF output_12v = 0V AND ac_input normal AND bridge_output = 310V
    THEN MOSFET failed OR PWM controller failed
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Fuse F1 blown | 35% | Downstream short caused sacrifice |
| MOSFET D-S short | 25% | Thermal runaway, no switching |
| PWM controller U5 failed | 20% | No gate drive to MOSFET |
| Bridge rectifier failed | 15% | No DC bus creation |
| Bulk capacitor open | 5% | No energy storage |

---

### SIG-002: Fuse Blows Immediately On Power-Up

**Observable:** Fuse ruptures within <100ms of AC application.

**IF-THEN Reasoning:**

```
IF fuse blown AND MOSFET D-S < 10Ω
    THEN MOSFET failed short → replace MOSFET AND find root cause

IF fuse blown AND MOSFET D-S > 100kΩ
    THEN MOSFET OK → check bridge rectifier for short
```

**Critical Rule:** NEVER replace fuse before testing MOSFET. 95%+ immediate re-blow if downstream short remains.

**Cascade Chain:**
```
Secondary Schottky shorts → Primary current spikes → MOSFET fails → Fuse blows
                                    ↑
                        (Root cause often missed)
```

---

### SIG-003: Output Cycling / Hiccup Mode — 0.5-2 Hz

**Observable:** Output pulses on/off repeatedly.

**IF-THEN Reasoning:**

```
IF output cycles AND load disconnected = stable
    THEN load fault (camera short or cable short)

IF output cycles AND load disconnected = still cycles
    THEN PSU internal fault

IF output cycles AND bridge_output droops during cycle
    THEN bulk capacitor degraded (ESR high)
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Load short/overload | 40% | OCP repeatedly triggering |
| Output capacitor C12 high ESR | 25% | Ripple triggers false OVP |
| Feedback network fault | 20% | Loop instability |
| Output Schottky degraded | 15% | Regulation failure |

---

### SIG-004: Low Output Voltage — Below 10.8V

**Observable:** Output reads 8-11V under load.

**IF-THEN Reasoning:**

```
IF output_12v = low AND no-load = 12V
    THEN output capacitor ESR high (load regulation failure)

IF output_12v = low AND no-load = still low
    THEN feedback or set-point fault

IF output_12v = low AND feedback_ref < 2.2V
    THEN feedback network pulling voltage down

IF output_12v = low AND feedback_ref > 2.6V
    THEN controller not receiving correct feedback
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Output capacitor C12 high ESR | 30% | Voltage droop under load |
| Output Schottky degraded | 25% | Increased forward drop |
| Feedback network fault | 25% | Wrong set point |
| Transformer degraded | 15% | Reduced coupling |

---

### SIG-005: High Output Voltage — Above 13.2V

**Observable:** Output exceeds safe maximum, risk of camera damage.

**⚠️ SAFETY: Disconnect load immediately if >13.2V detected.**

**IF-THEN Reasoning:**

```
IF output_12v = high AND feedback_ref = high (>2.6V)
    THEN feedback resistor R2 failed open OR optocoupler degraded

IF output_12v = high AND feedback_ref = normal (2.4-2.6V)
    THEN optocoupler CTR degraded OR controller fault
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Optocoupler degraded (CTR drop) | 40% | Less feedback signal → higher duty cycle |
| Feedback resistor R2 value change | 30% | Altered divider ratio |
| Reference voltage fault | 20% | TL431 or equivalent failed |
| OVP circuit failed | 10% | Protection not activating |

---

### SIG-006: Excessive Output Ripple / Noise

**Observable:** AC ripple on DC output, camera interference.

**IF-THEN Reasoning:**

```
IF ripple > 200mVpp AND output_12v = normal
    THEN output capacitor C12 failed (high ESR)

IF ripple > 200mVpp AND output_12v = low
    THEN check bulk capacitor AND Schottky
```

**Measurement:** Use oscilloscope, AC coupling, 20MHz bandwidth. Ripple >200mVpp is excessive.

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Output capacitor C12 high ESR | 50% | Ripple current creates voltage ripple |
| Output capacitor C12 low capacitance | 20% | Less filtering |
| Bulk input capacitor degraded | 20% | Input ripple propagates to output |
| Output Schottky degraded | 10% | Non-ideal switching |

---

### SIG-007: Thermal Shutdown — Works Cold, Fails Hot

**Observable:** Unit operates normally cold, fails after 5-30 minutes.

**IF-THEN Reasoning:**

```
IF works cold AND fails hot AND enclosure open = works longer
    THEN ventilation/installation issue

IF works cold AND fails hot AND enclosure open = still fails
    THEN component degradation (U5, MOSFET)
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Inadequate ventilation | 35% | Blocked airflow |
| U5 degraded | 25% | Higher internal resistance |
| Output overload | 20% | Drawing > rated current |
| Thermal interface degraded | 15% | Dried thermal compound |
| Input voltage too high | 5% | More dissipation |

---

## 7. Root Cause Explanations

### CAUS-001: Secondary Schottky Short → Fuse Blow Cascade

**Why the fuse is NOT the cause:**

```
Schottky diode shorts (root cause)
    ↓
Transformer secondary effectively shorted
    ↓
Primary current spikes massively
    ↓
MOSFET thermal stress → fails D-S short (victim)
    ↓
DC bus hard-connected to primary
    ↓
Current through bridge rectifier
    ↓
FUSE BLOWS (sacrificial protection - last to fail)
```

**DIAGNOSTIC MANDATE:** If MOSFET is shorted, ALWAYS test Schottky diode BEFORE powering on after repair. 40-70% recurrence if Schottky not tested.

---

### CAUS-002: Bulk Capacitor ESR Degradation → Output Instability

**Mechanism:**

```
Bulk capacitor ages → ESR increases
    ↓
DC bus ripple increases (Vripple = I × ESR)
    ↓
MOSFET drain voltage shows increased spikes
    ↓
Increased avalanche stress on MOSFET
    ↓
Output ripple increases through transformer
    ↓
Intermittent operation, noise, eventual failure
```

---

### CAUS-003: Optocoupler CTR Degradation → Overvoltage

**Mechanism:**

```
Optocoupler LED ages → CTR decreases
    ↓
Less photocurrent reaches primary side
    ↓
Controller sees "output too low" (false signal)
    ↓
Controller increases duty cycle to compensate
    ↓
Output voltage rises above set point
    ↓
Overvoltage condition (SIG-005)
```

---

## 8. Diagnostic Strategy

### Primary Strategy: Half-Split Testing

**The DC Bus Test (MEAS-001) is the highest-yield first test:**

```
DC BUS = 155V/310V?
    │
    ├─► YES → Fault in switching OR output section
    │        (Eliminates: AC input, fuse, bridge, bulk cap)
    │
    └─► NO → Fault in input section
             (Eliminates: MOSFET, U5, transformer, output)
```

**Diagnostic Yield:** Single test eliminates ~50% of circuit fault space.

### Strategy Selection:

| If Symptom | Use Strategy |
|------------|--------------|
| Complete dead (SIG-001) | Half-split: DC bus test first |
| Fuse blown (SIG-002) | Cascade trace: MOSFET → Schottky |
| Output degraded (SIG-004,005,006) | Feedback trace: output → feedback → control |
| Intermittent/thermal (SIG-007) | Thermal profiling: operate to failure |

---

## 9. Step-by-Step Troubleshooting Logic

### PATH A: Dead Unit (No Output)

```
STEP 1: Visual inspection
    → Look for: blown fuse, burnt components, capacitor bulge
    → IF damage found → document, proceed to test

STEP 2: Output voltage test (TP2)
    → IF 0V → proceed to STEP 3
    → IF 12V → fault is intermittent or downstream

STEP 3: Fuse continuity test (F1)
    → IF open → DO NOT replace yet, go to STEP 4
    → IF continuity → go to STEP 5

STEP 4: MOSFET D-S resistance test
    → IF <10Ω → MOSFET failed → test Schottky (MEAS-005)
    → IF >100kΩ → MOSFET OK → test bridge (MEAS-004)

STEP 5: DC bus voltage test (TP1)
    → IF 0V → input path fault (fuse, bridge, bulk cap)
    → IF 155V/310V → switching section fault (U5, MOSFET)
```

### PATH B: Degraded Output (Low/High/Ripple)

```
STEP 1: Output voltage measurement (TP2)
    → IF <10.8V → go to PATH B1 (low output)
    → IF >13.2V → go to PATH B2 (high output)
    → IF 11.4-12.6V but ripple high → PATH B3 (ripple)

PATH B1 (Low Output):
    STEP 1a: Feedback reference (TP3)
        → IF 2.4-2.6V → test C12 ESR (MEAS-008)
        → IF <2.2V → check feedback network R2
        → IF >2.6V → check optocoupler

PATH B2 (High Output):
    STEP 2a: Feedback reference (TP3)
        → IF >2.6V → R2 failed open → replace R2
        → IF normal → optocoupler degraded → replace optocoupler

PATH B3 (Excessive Ripple):
    STEP 3a: Output capacitor ESR test (C12)
        → IF >0.5Ω → replace C12
        → IF <0.2Ω → check bulk capacitor ESR
```

---

## 10. Repair Procedures

### REP-001: MOSFET Replacement

**Prerequisites:**
- Schottky diode tested and OK (or replaced)
- Root cause identified (not just symptom)

**Procedure:**
1. Disconnect AC, wait 5 minutes, verify DC bus <5V
2. Note MOSFET orientation (Gate, Drain, Source)
3. Desolder all three leads
4. Clean pads with desoldering braid
5. Apply thin thermal compound to new MOSFET
6. Install in correct orientation
7. Solder all leads, verify no bridges
8. Verify G-S >1MΩ, D-S >100kΩ before power-on

**Power-On Test:**
- Use 60W bulb in series with AC (current limiter)
- Bulb should flash then dim
- If bulb stays bright → short remains
- Verify output reaches 12V before removing bulb

---

### REP-002: Output Capacitor C12 Replacement

**Procedure:**
1. Discharge C12 (short terminals briefly)
2. Note polarity (negative stripe)
3. Desolder both leads
4. Install replacement with correct polarity
5. Solder leads, trim excess

**Specification:** Match or exceed original: same µF, same or higher voltage rating, low ESR, 105°C rated preferred.

---

### REP-003: Feedback Resistor R2 Replacement

**Procedure:**
1. Locate R2 (typically 470Ω near optocoupler)
2. Measure in-circuit resistance
3. Desolder one end to measure accurately
4. Replace with 470Ω ±1% metal film resistor

---

## 11. Safety Notes

⚠️ **DANGER: Lethal voltages present on primary side.**

| Zone | Voltage | Risk |
|------|---------|------|
| AC input, F1, BR1 | 110-240V AC | Lethal, AC shock |
| Bulk capacitors, TP1 | 155-380V DC | Lethal, cardiac arrest risk |
| MOSFET, transformer primary | 155-380V DC | Lethal |

**Safety Rules:**
1. ALWAYS disconnect AC before working on board
2. Wait minimum 5 minutes after disconnect for capacitor discharge
3. Verify DC bus <50V with meter before touching
4. Use one hand only when measuring high voltages
5. Use insulated probes rated for 600V CAT II minimum
6. Never replace fuse with higher rating
7. Discharge capacitors before desoldering

---

## 12. Common Failure Modes

| Rank | Component | Failure Mode | Signature | Frequency |
|------|-----------|--------------|-----------|-----------|
| 1 | MOSFET | D-S short | Fuse blows | 35% |
| 2 | Output Capacitor C12 | High ESR | Ripple, low voltage | 20% |
| 3 | Output Schottky | Short/open | Low output, MOSFET damage | 15% |
| 4 | PWM Controller U5 | No output | Dead unit | 10% |
| 5 | Bridge Rectifier | Diode short | Fuse blows, half-wave DC | 10% |
| 6 | Bulk Capacitor | ESR increase | Ripple, instability | 5% |
| 7 | Feedback Resistor R2 | Open | High output | 3% |
| 8 | Optocoupler | CTR degraded | High output | 2% |

---

## 13. Measurement Interpretation Guide

### DC Bus Voltage (TP1)

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| 310-330V | Normal (230V input) | Proceed to switching section |
| 155-165V | Normal (115V input) | Proceed to switching section |
| 0V | Input path fault | Test fuse, bridge |
| 50-100V | Bulk cap degraded | Test bulk cap ESR |

### Output Voltage (TP2)

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| 11.4-12.6V | Normal | Check load/cables |
| 10.8-11.4V | Marginally low | Test C12 ESR |
| <10.8V | Under-voltage fault | Test feedback, Schottky |
| 12.6-13.2V | Marginally high | Test feedback reference |
| >13.2V | Over-voltage fault | Disconnect load, test R2 |
| 0V | No output | Test DC bus, MOSFET |

### Feedback Reference (TP3)

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| 2.4-2.6V | Normal | Check optocoupler |
| <2.2V | Low | Check R2, feedback network |
| >2.8V | High | R2 may be open |
| 0V | Failed reference | Replace TL431 or R2 |

### MOSFET D-S Resistance

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| >100kΩ both directions | Normal | Check controller |
| <10Ω both directions | Shorted | Replace, find root cause |
| 0.3-0.7V forward drop | Normal body diode | MOSFET OK |

### Output Capacitor ESR

| ESR | Status | Action |
|-----|--------|--------|
| <0.1Ω | Good | No action |
| 0.1-0.2Ω | Acceptable | Monitor |
| 0.2-0.5Ω | Degraded | Replace soon |
| >0.5Ω | Failed | Replace immediately |

---

## Quick Reference Decision Tree

```
Unit dead?
├─► Yes → Output voltage = 0V?
│       ├─► Yes → DC bus = 0V?
│       │       ├─► Yes → Fuse blown?
│       │       │       ├─► Yes → MOSFET shorted? → Test Schottky
│       │       │       └─► No → Bridge failed
│       │       └─► No → Bulk cap failed
│       │
│       └─► No → (unit not dead, go to degraded)
│
├─► No (has output) → Output voltage?
        ├─► Low (<10.8V) → Feedback ref normal? → C12 ESR test
        ├─► High (>13.2V) → Feedback ref high? → R2 replacement
        ├─► Ripple >200mV → C12 ESR test
        └─► Cycling → Load test → Internal fault
```

---

**Document Version:** 2.0  
**Equipment:** CCTV-PSU-24W-V1 (PCB: SP-80M)  
**Generated:** 2026-03-21  
**Target System:** ChromaDB RAG Vector Store
