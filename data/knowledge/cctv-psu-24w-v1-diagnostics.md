# RAG-Optimized Diagnostic Documentation

**Equipment:** CCTV-PSU-24W-V1 (PCB Marking: SP-80M) — 12V 30A SMPS  
**Document Version:** 1.0  
**Generated:** 2026-02-25  
**Purpose:** RAG retrieval for biomedical equipment troubleshooting AI agent  
**Target System:** ChromaDB Vector Store

---

## IMAGE ANALYSIS — PCB Component Identification

Based on visual inspection of `docs/CCTV Power Supply Unit.jpeg`, the following component layout was identified:

**Board Overview:** The SP-80M PCB is mounted in a metal chassis/enclosure. The board follows a classic flyback/forward converter topology.

**Physical Zones Identified:**

| Zone | Location | Components |
|------|----------|------------|
| Upper-left quadrant | Primary side | Cluster of 3–4 small electrolytic capacitors (input filter/bulk caps), blue disc ceramic capacitors (snubber/EMI filter), small inductors |
| Center-left | Primary side | Large wound transformer with yellow/gold bobbin — primary power transformer |
| Upper-right | Primary/secondary boundary | Yellow block component — likely auxiliary supply transformer or relay; green terminal block for AC/DC connections |
| Lower-center | Primary side | 8-pin DIP IC — PWM controller (U5 candidate) |
| Lower-right | Secondary side | Large black cylindrical electrolytic capacitor — primary output bulk/filter capacitor (C12 candidate) |
| Right edge | Mixed | Multiple 3-terminal devices — likely MOSFETs, Schottky diodes, and/or BJTs on heatsink tabs |
| Center-bottom | Secondary side | Small signal transistors and resistor network — feedback/optocoupler zone |

**Safety Zone Demarcation:**

| Zone | Voltage Level | Risk |
|------|---------------|------|
| PRIMARY SIDE (Left half) | HIGH VOLTAGE — LETHAL | Transformer primary, bridge rectifier area, upper-left bulk capacitors, fuse location |
| SECONDARY SIDE (Right half) | LOW VOLTAGE — SAFER | Large output capacitor, output Schottky diode, output terminal connections |

---

## RETRIEVAL INDEX

### Failure Signatures (SIG-*)

| ID | Title |
|----|-------|
| SIG-001 | Unit Completely Dead — No LED, No Fan, No Output |
| SIG-002 | Fuse Blows Immediately On Power-Up |
| SIG-003 | Output Cycling / Hiccup Mode — 0.5–2 Hz |
| SIG-004 | Low Output Voltage — Below 10.8V |
| SIG-005 | High Output Voltage — Above 13.2V |
| SIG-006 | Excessive Output Ripple / Noise |
| SIG-007 | Thermal Shutdown — Works Cold, Fails Hot |

### System-Level Diagnostic Gates (SYS-*)

| ID | Title |
|----|-------|
| SYS-001 | System Not Powering On — Complete Failure |
| SYS-002 | System Powers On But Output Degraded |
| SYS-003 | System Intermittent — Temperature or Load Dependent |

### Subsystem Diagnostic Gates (SUB-*)

| ID | Title |
|----|-------|
| SUB-001 | Input/Power Section Diagnostic Gate |
| SUB-002 | Switching Section Diagnostic Gate |
| SUB-003 | Output/Feedback Section Diagnostic Gate |

### Measurement Rules (MEAS-*)

| ID | Title |
|----|-------|
| MEAS-001 | DC Bus Voltage Measurement |
| MEAS-002 | Fuse Continuity Test |
| MEAS-003 | MOSFET Drain-Source Resistance Test |
| MEAS-004 | Bridge Rectifier Diode Test |
| MEAS-005 | Output Schottky Diode Test |
| MEAS-006 | Output Voltage Measurement (TP2) |
| MEAS-007 | Feedback Reference Voltage (TP3) |
| MEAS-008 | Output Capacitor ESR Test (C12) |

### Component Fault Models (COMP-*)

| ID | Title |
|----|-------|
| COMP-001 | Primary MOSFET Fault Model |
| COMP-002 | Bridge Rectifier Fault Model |
| COMP-003 | Bulk Input Capacitor Fault Model |
| COMP-004 | Output Schottky Diode Fault Model |
| COMP-005 | PWM Controller (U5) Fault Model |
| COMP-006 | Output Capacitor (C12) Fault Model |

### Subsystem Gates (SG-*)

| ID | Title |
|----|-------|
| SG-001 | DC Bus Present Gate — Eliminates Input Path |
| SG-002 | DC Bus Absent Gate — Confirms Input Path Fault |
| SG-003 | Gate Drive Present Gate — Eliminates Controller |
| SG-004 | Output Voltage Gate — Secondary Section Check |

### Causality Chains (CAUS-*)

| ID | Title |
|----|-------|
| CAUS-001 | Secondary Schottky Short → Fuse Blow Cascade |
| CAUS-002 | Bulk Capacitor ESR Degradation → Output Instability |
| CAUS-003 | Optocoupler Degradation → Overvoltage Cascade |

### Field-Induced Faults (FIELD-*)

| ID | Title |
|----|-------|
| FIELD-001 | DC Output Cable Voltage Drop |
| FIELD-002 | Input Voltage Mismatch (230V vs 115V) |
| FIELD-003 | Inadequate Ventilation — Thermal Shutdown |

### Ambiguity Resolution (AMB-*)

| ID | Title |
|----|-------|
| AMB-001 | Differentiating OCP Activation vs. Component Failure |
| AMB-002 | Differentiating OVP Activation vs. Feedback Failure |

### Diagnostic Yield Notes (YD-*)

| ID | Title |
|----|-------|
| YD-001 | Yield Note — DC Bus Voltage Test |
| YD-002 | Yield Note — Output Voltage Test |
| YD-003 | Yield Note — MOSFET D-S Resistance Test |

### Time Estimates (TE-*)

| ID | Title |
|----|-------|
| TE-001 | Fast Triage Path — Dead Unit (Bench) |
| TE-002 | Full Diagnostic Sequence — Output Degraded |

### Visual Indicators (VI-*)

| ID | Title |
|----|-------|
| VI-001 | Primary MOSFET Catastrophic Failure — Visual |
| VI-002 | Blown Fuse — Visual Identification |
| VI-003 | Electrolytic Capacitor Failure — Visual |
| VI-004 | Transformer Overheating — Visual |

### Recurrence Risk Matrices (RM-*)

| ID | Title |
|----|-------|
| RM-001 | Recurrence Risk — Fuse Blows Symptom |
| RM-002 | Recurrence Risk — Low Output Voltage |

### Repair Procedures (REP-*)

| ID | Title |
|----|-------|
| REP-001 | MOSFET Replacement Procedure |
| REP-002 | Output Capacitor (C12) Replacement Procedure |

---

## SECTION 1: FAILURE SIGNATURES (SIG-*)

### SIG-001: Unit Completely Dead — No LED, No Fan, No Output

**Symptom Class:** Total Power Failure

**Observable:** No indication of any electrical activity; no indicator LED, no audible relay click, zero output at terminals

**Acoustic:** Complete silence on power-up

**Thermal:** Board remains cold after several seconds with AC applied

**IMG:** IMG_REF_DEAD_UNIT

**Diagnostic Implication:**
Either no power is reaching the board, the primary stage is not converting, or the secondary stage is not delivering. This symptom does not discriminate between primary and secondary failure — the DC Bus test is the critical discriminator.

**Subsystem Probability Ranking:**

| Subsystem | Probability | Reasoning |
|-----------|-------------|-----------|
| Input/Power Section | 60% | Most failures here prevent any output |
| Switching Section | 25% | Controller or MOSFET failure prevents startup |
| Output/Feedback Section | 15% | Secondary-only fault rarely produces total silence |

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Blown fuse (F1) | 35% | Sacrificial overcurrent device; first-fail point |
| MOSFET D-S short | 25% | Prevents switching; may have also blown fuse |
| PWM controller (U5) failure | 20% | No gate drive; no switching |
| Bridge rectifier open | 15% | No DC bus; no downstream power |
| Bulk capacitor open | 5% | Rare but eliminates DC bus |

**Critical Rule:** Do NOT assume the fuse is the cause. Test MOSFET before replacing fuse.

**First Test:** MEAS-001 (DC Bus Voltage) — highest leverage

**Diagnostic Sequence:** MEAS-001 → SG-001 → SG-002 → MEAS-002 → MEAS-003

**Recurrence Risk:**

| Action | Risk | Outcome |
|--------|------|---------|
| Replace fuse only | 95%+ | Immediate re-blow if downstream short exists |
| Replace fuse + MOSFET | 40–70% | Secondary diode may still be shorted |
| Full root cause analysis | <5% | Durable repair |

**Related Chunks:** SYS-001, SUB-001, MEAS-001, MEAS-002, MEAS-003, SG-001, VI-002, RM-001

---

### SIG-002: Fuse Blows Immediately On Power-Up

**Symptom Class:** Instantaneous Overcurrent / Hard Short

**Observable:** Fuse element ruptures within <100ms of AC power application; board remains dead

**Acoustic:** Possible audible pop on power-up

**Thermal:** Fuse glass envelope may show blackening or heat discoloration

**Visual:** Broken or vaporized fuse element

**IMG:** IMG_REF_BLOWN_FUSE

**Diagnostic Implication:**
A hard short exists on the DC bus. The short completes the path: AC → Bridge Rectifier → DC Bus → Short → Earth/Return. The fuse is the victim, not the cause.

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| MOSFET Drain-Source short | 60% | Highest stress component; avalanche breakdown or thermal runaway |
| Bridge rectifier diode short | 25% | Surge damage; inrush stress; one arm conducting DC |
| Bulk capacitor internal short | 10% | Dielectric breakdown from overvoltage event |
| Primary transformer winding short | 5% | Insulation failure; rare |

**Critical Rule:** Do NOT replace fuse before measuring MOSFET D-S resistance. Replacing fuse alone results in 95%+ immediate re-blow.

**Recurrence Risk:**

| Action | Risk | Outcome |
|--------|------|---------|
| Replace fuse only | 95%+ | Immediate re-blow |
| Replace fuse + MOSFET | 40–70% | Re-blow if Schottky diode caused MOSFET failure |
| Replace fuse + MOSFET + secondary Schottky | 5–15% | Check bulk cap ESR also |
| Full cascade analysis + all affected components | <5% | Successful repair |

**Next Actions:** MEAS-003 (MOSFET D-S) → MEAS-004 (Bridge) → MEAS-005 (Schottky) → CAUS-001

**Related Chunks:** SYS-001, MEAS-002, MEAS-003, MEAS-004, COMP-001, COMP-002, CAUS-001, VI-001, VI-002, RM-001

---

### SIG-003: Output Cycling / Hiccup Mode — 0.5–2 Hz

**Symptom Class:** Protection Activation / Overload Response

**Observable:** Output voltage pulses on/off at approximately 0.5–2 Hz; brief output then collapse, repeating

**Acoustic:** Possible faint clicking from switching activity

**Thermal:** MOSFET and transformer may be warm from repeated startup attempts

**IMG:** IMG_REF_HICCUP_MODE

**Diagnostic Implication:**
The PSU is starting, detecting an overload or fault condition, shutting down (OCP or OVP), recovering, and restarting. The root cause may be in the PSU itself or in the connected load.

**Differentiation Tests:**

| Test | Result | Interpretation |
|------|--------|----------------|
| Disconnect load, observe output | Cycling stops, stable output | Load is shorted or drawing excess current |
| Disconnect load, cycling continues | PSU internal fault | Feedback loop, output capacitor, or winding issue |
| DC bus voltage during cycling | Stable 155/310V | Feedback or controller issue |
| DC bus during cycling droops | Bulk capacitor degraded | ESR failure |
| Output voltage at peak of cycle | Reaches ~12V briefly | OCP activating (normal output then shutdown) |
| Output never reaches 12V | Internal short or severe overload | Output Schottky or transformer issue |

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Load short or overload | 40% | OCP triggering repeatedly |
| Output capacitor high ESR (C12) | 25% | Ripple causes false OVP/OCP trigger |
| Feedback network fault | 20% | Loop instability causing oscillation |
| Output Schottky degraded | 15% | High forward drop causing regulation issue |

**First Action:** Disconnect load entirely; observe output

**Related Chunks:** AMB-001, MEAS-006, MEAS-007, MEAS-008, COMP-006, CAUS-002, SG-004

---

### SIG-004: Low Output Voltage — Below 10.8V (Fault Threshold)

**Symptom Class:** Regulation Failure — Under-Voltage

**Observable:** Output measured at TP2 reads below 10.8V under normal load; may be 8–11V range

**Signal:** output_12v reads in "degraded" or "under_voltage" state

**Threshold:** Fault state defined as <10.8V per equipment configuration

**IMG:** IMG_REF_LOW_OUTPUT

**Diagnostic Implication:**
The PSU is operating but not regulating to the correct set point. Could be output-section degradation, feedback loop failure, or input-side marginal operation.

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Output capacitor (C12) high ESR | 30% | Increased ripple + voltage drop under load |
| Output Schottky diode degraded | 25% | Increased forward voltage reduces output |
| Feedback network fault | 25% | Loop not correcting to set point |
| Transformer degraded (shorted turns) | 15% | Reduced coupling, lower secondary voltage |
| Bulk capacitor degraded | 5% | Insufficient DC bus under load |

**Distinguishing Tests:**

| Test | Outcome | Interpretation |
|------|---------|----------------|
| Measure voltage at no-load | Normal (12V) | Load regulation failure → capacitor ESR |
| Measure voltage at no-load | Still low | Set-point or feedback issue |
| Measure TP3 (feedback ref) | < 2.4V | Feedback pulling controller down |
| Measure TP3 | > 2.6V | Controller not receiving correct feedback |
| ESR test on C12 | High ESR | Output capacitor primary cause |

**Diagnostic Sequence:** MEAS-006 → MEAS-007 → MEAS-008

**Related Chunks:** MEAS-006, MEAS-007, MEAS-008, COMP-004, COMP-006, CAUS-002, RM-002

---

### SIG-005: High Output Voltage — Above 13.2V (Fault Threshold)

**Symptom Class:** Regulation Failure — Over-Voltage

**Observable:** Output measured at TP2 reads above 13.2V; may trigger connected equipment damage

**Signal:** output_12v reads "over_voltage" per equipment configuration (>13.2V)

**IMG:** IMG_REF_HIGH_OUTPUT

**Diagnostic Implication:**
The feedback loop is not correcting the output voltage downward. Either the feedback path is broken, the optocoupler is degraded, or the feedback resistor (R2) has changed value.

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Optocoupler degraded | 40% | Reduced CTR means less feedback signal; controller increases duty cycle |
| Feedback resistor (R2) value change | 30% | Altered divider ratio changes set point |
| Reference voltage (TP3) fault | 20% | Shunt regulator (TL431 or equivalent) failed |
| OVP circuit not activating | 10% | OVP threshold too high or OVP circuit failed |

**Defined Fault:** overvoltage_output — Primary Component: R2 (Feedback resistor) per equipment config

**Critical Safety:** Overvoltage can damage connected CCTV cameras. Disconnect load immediately if >13.2V detected.

**Diagnostic Sequence:** MEAS-007 → MEAS-006 → visual inspection R2 area

**Related Chunks:** MEAS-006, MEAS-007, COMP-005, CAUS-003, AMB-002

---

### SIG-006: Excessive Output Ripple / Noise

**Symptom Class:** Output Quality Degradation

**Observable:** AC ripple superimposed on 12V DC output; may cause CCTV camera interference, image noise, or equipment instability

**Defined Fault:** excessive_ripple — Primary Component: C12 (Output capacitor)

**IMG:** IMG_REF_RIPPLE

**Diagnostic Implication:**
Ripple exceeds specification. The output filtering capacitor is most often responsible, but could also reflect input-side degradation causing excessive switching ripple.

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Output capacitor C12 high ESR | 50% | High ESR allows ripple current to create voltage ripple |
| Output capacitor C12 low capacitance | 20% | Reduced capacitance increases ripple |
| Bulk input capacitor degraded | 20% | Increased input ripple modulates output |
| Output Schottky diode degraded | 10% | Non-ideal switching increases ripple |

**Measurement:** Use oscilloscope on TP2 with AC coupling, 20MHz BW limit. Ripple >200mVpp on 12V rail is excessive.

**Related Chunks:** MEAS-008, COMP-003, COMP-006, CAUS-002, REP-002

---

### SIG-007: Thermal Shutdown — Works Cold, Fails Hot

**Symptom Class:** Temperature-Dependent Failure

**Observable:** Unit operates normally when cold; fails (output drops or unit shuts down) after 5–30 minutes of operation

**Defined Fault:** thermal_shutdown — Primary Component: U5 (Thermal management)

**Signal:** u5_temperature — Critical threshold >95°C per equipment config

**IMG:** IMG_REF_THERMAL

**Diagnostic Implication:**
Component U5 (PWM controller/buck converter) is reaching thermal shutdown threshold. Root cause is either excessive power dissipation or inadequate heat removal.

**Root Cause Candidates:**

| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| Inadequate ventilation (installation) | 35% | Blocked airflow in enclosure |
| U5 degraded, higher dissipation | 25% | Internal resistance increased; more heat per watt |
| Output overload | 20% | Load drawing more than rated current |
| Thermal interface degraded | 15% | Dried thermal compound between component and heatsink |
| Input voltage too high | 5% | Higher input → more dissipation in linear elements |

**Distinguishing Test:** Operate with enclosure open; if runtime extends significantly, ventilation is primary cause.

**Related Chunks:** FIELD-003, COMP-005, MEAS-006, RM-002

---

## SECTION 2: SYSTEM-LEVEL DIAGNOSTIC GATES (SYS-*)

### SYS-001: System Not Powering On — Complete Failure

**Symptom:** Complete system failure — no LED, no fan, zero output

**System State:** Completely unresponsive; AC applied, no response

**Entry Point:** SIG-001

**Subsystem Probability Ranking:**

| Subsystem | Probability | Reasoning |
|-----------|-------------|-----------|
| Input/Power Section | 60% | Power never reaches converter stage |
| Switching Section | 25% | Power present but conversion fails |
| Output/Feedback Section | 15% | Secondary fault rarely causes total silence |

**Diagnostic Entry — Half-Split Test:**
The DC Bus Voltage test (MEAS-001) is the optimal entry point. It divides the circuit at its natural midpoint, eliminating either the input or output half with one measurement.

**Diagnostic Sequence:**

1. Visual inspection (zero risk — always first) → VI-001, VI-002
2. DC Bus Voltage test → MEAS-001 → SG-001 / SG-002
3. If DC bus absent → SUB-001 (Input/Power Section)
4. If DC bus present → SUB-002 (Switching Section)

**Time Estimate:** See TE-001

**Related Chunks:** SUB-001, SUB-002, SUB-003, SIG-001, SIG-002, MEAS-001, TE-001

---

### SYS-002: System Powers On But Output Degraded

**Symptom:** Unit has partial function; output present but out of specification

**System State:** Switching activity present; output voltage outside 11.4–12.6V normal range

**Subsystem Probability Ranking:**

| Subsystem | Probability | Reasoning |
|-----------|-------------|-----------|
| Output/Feedback Section | 55% | Degraded output is classic secondary/feedback failure |
| Switching Section | 30% | Controller or MOSFET degradation affects regulation |
| Input/Power Section | 15% | Marginal input affects regulation under load |

**Diagnostic Sequence:**

1. Output Voltage test → MEAS-006 (confirm reading and severity)
2. Feedback Reference test → MEAS-007 (is control loop working?)
3. If feedback OK, test output capacitor ESR → MEAS-008
4. If feedback not OK, trace to optocoupler / feedback network

**Related Chunks:** SUB-003, SIG-004, SIG-005, SIG-006, MEAS-006, MEAS-007, MEAS-008

---

### SYS-003: System Intermittent — Temperature or Load Dependent

**Symptom:** Unit works under some conditions, fails under others

**System State:** Functional at rest; fails at temperature or under load

**Subsystem Probability Ranking:**

| Subsystem | Probability | Reasoning |
|-----------|-------------|-----------|
| Switching Section | 45% | Thermal issues commonly in U5, MOSFET |
| Output/Feedback Section | 35% | Capacitor ESR worsens with temperature |
| Input/Power Section | 20% | Marginal bulk cap causes input instability under load |

**Diagnostic Approach:** Use thermal profiling and load variation testing (stimulus-response) to force the fault condition reproducibly.

**Related Chunks:** SIG-003, SIG-007, MEAS-008, COMP-001, COMP-005, FIELD-003

---

## SECTION 3: SUBSYSTEM DIAGNOSTIC GATES (SUB-*)

### SUB-001: Input/Power Section Diagnostic Gate

**Subsystem:** Input/Power Section

**Components:** F1 (fuse), bridge rectifier, bulk input capacitors, EMI filter, AC input terminals

**IMG:** IMG_REF_PRIMARY_ZONE

**Component Probability Ranking (when this subsystem is faulty):**

| Component | Probability | Failure Mode | Mechanism |
|-----------|-------------|--------------|-----------|
| Fuse F1 | 40% | Open circuit | Sacrificial overcurrent device; failed last in cascade |
| Bridge Rectifier | 30% | Diode short | Inrush/surge stress; thermal breakdown |
| Bulk Input Capacitors | 20% | Open or high ESR | Age-related degradation; thermal |
| AC Input / EMI Filter | 10% | Connection fault | Connector corrosion; wiring break |

**Diagnostic Sequence:**

1. Visual inspection of fuse F1 → VI-002
2. Fuse continuity → MEAS-002 (fastest test, 15 seconds)
3. DC Bus Voltage → MEAS-001 (confirms or eliminates subsystem)
4. If fuse OK and DC bus absent → MEAS-004 (Bridge rectifier)
5. If DC bus low → MEAS-008 variant (bulk capacitor)

**Entry Criteria:** SYS-001 identifies Input/Power as most probable, or DC bus absent per SG-002

**Exit Criteria:** DC Bus voltage normal (155V/310V) — subsystem is functional

⚠️ **SAFETY:** All components in this subsystem operate at lethal voltages (115–310V DC). Discharge bulk capacitors before physical contact.

**Related Chunks:** SYS-001, SG-001, SG-002, MEAS-001, MEAS-002, MEAS-004, COMP-002, COMP-003, VI-002

---

### SUB-002: Switching Section Diagnostic Gate

**Subsystem:** Switching/Conversion Section

**Components:** Primary MOSFET, PWM Controller (U5), gate drive circuit, snubber network, power transformer

**IMG:** IMG_REF_PRIMARY_ZONE

**Component Probability Ranking (when this subsystem is faulty):**

| Component | Probability | Failure Mode | Mechanism |
|-----------|-------------|--------------|-----------|
| Primary MOSFET | 50% | D-S short or open | Highest electrical/thermal stress |
| PWM Controller U5 | 30% | No output / wrong duty cycle | Thermal damage; VCC failure; latch-up |
| Power Transformer | 15% | Shorted turns / open winding | Insulation failure; thermal stress |
| Snubber Network | 5% | Component failure | Diode/capacitor degradation |

**Entry Criteria:** DC bus is present (SG-001 gate passed), but no output

**Diagnostic Sequence:**

1. MOSFET D-S resistance (powered off) → MEAS-003
2. PWM Controller Vcc voltage → MEAS-007
3. Gate drive waveform (requires oscilloscope + isolation transformer)
4. Transformer ring test if needed

⚠️ **SAFETY:** DC bus is present (lethal voltage). Discharge before any physical contact.

**Related Chunks:** SYS-001, SG-001, SG-003, MEAS-003, COMP-001, COMP-005

---

### SUB-003: Output/Feedback Section Diagnostic Gate

**Subsystem:** Output and Feedback Section

**Components:** Output Schottky diode, output capacitor C12, feedback resistor R2, optocoupler, TL431 (or equivalent shunt reference)

**IMG:** IMG_REF_SECONDARY_ZONE

**Component Probability Ranking (when this subsystem is faulty):**

| Component | Probability | Failure Mode | Mechanism |
|-----------|-------------|--------------|-----------|
| Output Capacitor C12 | 35% | High ESR | Electrolyte degradation; thermal aging |
| Output Schottky Diode | 35% | Short circuit | Overcurrent; thermal runaway |
| Feedback Network (R2, optocoupler) | 30% | Open / degraded CTR | Aging; thermal stress |

**Entry Criteria:** DC bus present, switching active, but output is missing or degraded

**Diagnostic Sequence:**

1. Output Voltage → MEAS-006
2. Feedback Reference → MEAS-007
3. Output Schottky test → MEAS-005
4. Output Capacitor ESR → MEAS-008

**Related Chunks:** SYS-002, SG-004, MEAS-005, MEAS-006, MEAS-007, MEAS-008, COMP-004, COMP-006

---

## SECTION 4: MEASUREMENT RULES (MEAS-*)

### MEAS-001: DC Bus Voltage Measurement

**Test Point:** Positive terminal of bulk input electrolytic capacitor to negative terminal (or to chassis ground)

**Instrument:** Multimeter, DC voltage mode, 400V or 600V range

**IMG:** IMG_REF_DC_BUS_TESTPOINT

⚠️ **SAFETY:** Lethal voltage present (155–310V DC). Use insulated probes rated for 600V CAT II minimum. One hand only. Do not touch board while measuring.

**Expected Values:**

| AC Input | Expected DC Bus |
|----------|-----------------|
| 115V AC input | 155–165V DC |
| 230V AC input | 310–330V DC |

**Decision Logic:**

| Result | Interpretation | Next Action | Eliminates |
|--------|----------------|-------------|------------|
| 155V or 310V (normal) | Input path fully functional | Proceed to SG-001, test switching | AC input, F1, bridge rectifier, bulk cap |
| 0V | Input path fault | Test fuse MEAS-002, then bridge MEAS-004 | Secondary, feedback, MOSFET |
| 50–100V (low) | Bulk cap degraded or selector mismatch | Test bulk cap ESR; check selector | — |
| Correct voltage with high ripple (>30Vpp AC) | Bulk cap ESR failure | Replace bulk capacitor | — |

**Diagnostic Yield:** Highest single test — eliminates ~50% of circuit in 10–30 seconds

**Time Estimate:** 30–60 seconds (with meter ready and cover open)

**Related Chunks:** SG-001, SG-002, COMP-002, COMP-003, YD-001, TE-001

---

### MEAS-002: Fuse Continuity Test (F1)

**Test Point:** Across fuse F1 terminals (fuse removed from circuit, or in-circuit with AC disconnected)

**Instrument:** Multimeter, continuity mode or resistance mode

**IMG:** IMG_REF_BLOWN_FUSE

⚠️ **SAFETY:** AC power must be disconnected before testing fuse in-circuit. Discharge bulk capacitor first.

**Procedure:**

1. Disconnect AC power
2. Wait 2 minutes minimum; verify DC bus <50V
3. Set meter to continuity or resistance mode
4. Probe across fuse terminals

**Decision Logic:**

| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| Continuity (0–2Ω) | Fuse intact | Fault is not fuse; proceed to MEAS-003 |
| Open circuit | Fuse blown | Do NOT replace yet; find root cause first → MEAS-003 |
| Fuse visually blackened | Catastrophic overcurrent | Hard short downstream → MEAS-003 priority |

**Critical Rule:** A blown fuse is never the root cause. Always test MOSFET D-S (MEAS-003) before replacing fuse.

**Time Estimate:** 15–30 seconds

**Related Chunks:** SIG-001, SIG-002, COMP-001, COMP-002, MEAS-003, VI-002, RM-001

---

### MEAS-003: MOSFET Drain-Source Resistance Test

**Test Point:** MOSFET drain and source pins (or drain tab and source pin)

**Instrument:** Multimeter, resistance mode, 200Ω range

**IMG:** IMG_REF_MOSFET_COMPONENT

⚠️ **SAFETY:** AC power disconnected. DC bus MUST be discharged to <5V before probing MOSFET leads. Follow discharge procedure.

**Prerequisite:** MEAS-001 confirmed DC bus discharged, or 5-minute wait after AC disconnect + voltage verification.

**Procedure:**

1. Discharge DC bus
2. Verify bus voltage <5V with meter
3. Set meter to resistance mode, 200Ω range
4. Black probe to MOSFET source (typically center pin of TO-220 or source pad)
5. Red probe to MOSFET drain (typically outer pin or tab)
6. Record reading; try both probe orientations

**Decision Logic:**

| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| <10Ω (both orientations) | D-S short — MOSFET failed | MEAS-005 (find root cause), then REP-001 |
| 10Ω–100kΩ | Degraded / marginal | COMP-001 analysis; consider replacement |
| >100kΩ (and >1MΩ with probes reversed) | Normal MOSFET | Proceed to check controller |
| 0.3–0.7V forward drop (body diode) | Normal body diode behavior | Normal; MOSFET likely OK |

**Note:** A healthy N-channel MOSFET will show body diode forward drop (~0.5–0.7V) in one direction and high resistance in the other. A shorted MOSFET shows near-zero resistance in both directions.

**Diagnostic Yield:** High — definitively identifies most common failure mode in 1–2 minutes

**Time Estimate:** 1–2 minutes

**Related Chunks:** COMP-001, SIG-002, CAUS-001, MEAS-005, REP-001, VI-001, YD-003, RM-001

---

### MEAS-004: Bridge Rectifier Diode Test

**Test Point:** AC input terminals and DC output terminals of bridge rectifier

**Instrument:** Multimeter, diode test mode

**IMG:** IMG_REF_PRIMARY_ZONE

⚠️ **SAFETY:** AC disconnected. DC bus discharged. Bridge rectifier is on primary (high-voltage) side.

**Procedure:**

1. Disconnect AC power and discharge DC bus
2. Identify bridge rectifier (4-terminal device or 4 discrete diodes)
3. Set meter to diode test mode
4. Test each diode arm: probe in forward then reverse direction
5. Each diode should show 0.5–0.8V forward, OL (open) reverse

**Decision Logic:**

| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| All arms 0.5–0.8V forward, OL reverse | Bridge OK | Fault not in bridge |
| Any arm shows 0V both directions | Diode shorted | Replace bridge rectifier |
| Any arm shows OL both directions | Diode open | Replace bridge rectifier |
| Two adjacent arms shorted | Full bridge short | Immediate fuse blow cause |

**Time Estimate:** 2–3 minutes

**Related Chunks:** COMP-002, SIG-002, SUB-001, MEAS-002, CAUS-001

---

### MEAS-005: Output Schottky Diode Test

**Test Point:** Anode and cathode terminals of output Schottky diode (on secondary side, near output capacitor C12)

**Instrument:** Multimeter, diode test mode

**IMG:** IMG_REF_SECONDARY_ZONE

**Note:** This is a low-voltage secondary side test. Primary side discharge precautions still apply if testing with power off, but this component is isolated from lethal voltages in normal operation.

**Expected Schottky Values:**

| Measurement | Expected | Indicates |
|-------------|----------|-----------|
| Forward voltage (anode+, cathode−) | 0.15–0.45V | Normal Schottky junction |
| Reverse (cathode+, anode−) | OL (open) | Normal |
| Both directions near 0V | Shorted | Failed diode — root cause of MOSFET damage |
| Both directions OL | Open | Failed diode — no output rectification |

**Critical Importance:** A shorted Schottky diode is the most common root cause of MOSFET failure (CAUS-001). Always test this diode when MOSFET has failed.

**Time Estimate:** 1–2 minutes

**Related Chunks:** COMP-004, CAUS-001, MEAS-003, SIG-002, SIG-004

---

### MEAS-006: Output Voltage Measurement (TP2)

**Test Point:** TP2 — Output terminals / output capacitor C12 positive and negative

**Instrument:** Multimeter, DC voltage mode, 20V range

**IMG:** IMG_REF_OUTPUT_TERMINAL

**Normal Operating Range:** 11.4–12.6V (per output_12v signal specification)

**Degraded Range:** 10.8–13.2V

**Fault Thresholds:** Under-voltage <10.8V | Over-voltage >13.2V

**Decision Logic:**

| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| 11.4–12.6V | Output normal | Check load, cables; fault may be downstream |
| 10.8–11.4V (degraded-low) | Output marginally low | MEAS-008 (C12 ESR), MEAS-007 (feedback) |
| <10.8V (under-voltage fault) | Output regulation failure | MEAS-007, MEAS-005, MEAS-008 |
| 12.6–13.2V (degraded-high) | Output marginally high | MEAS-007 (feedback reference) |
| >13.2V (over-voltage fault) | Feedback loop failure | MEAS-007 priority; risk to connected equipment |
| 0V | No output | Verify DC bus present (MEAS-001); check switching |

**Diagnostic Yield:** Medium — confirms/rules out output section; safe low-risk test

**Time Estimate:** 20–30 seconds

**Related Chunks:** SYS-002, SIG-004, SIG-005, SG-004, MEAS-007, MEAS-008, YD-002

---

### MEAS-007: Feedback Reference Voltage Test (TP3)

**Test Point:** TP3 — Feedback reference node; typically cathode of TL431 or equivalent shunt reference on secondary side

**Instrument:** Multimeter, DC voltage mode, 5V range

**IMG:** IMG_REF_SECONDARY_ZONE

**Normal Range:** 2.4–2.6V (per feedback_ref signal specification)

**Fault Threshold:** <0.2V indicates failed state

**Decision Logic:**

| Result | Interpretation | Next Action |
|--------|----------------|-------------|
| 2.4–2.6V | Reference normal | Feedback reference OK; check optocoupler, output voltage |
| 2.2–2.4V or 2.6–2.8V | Degraded | Monitor under load; check R2 value |
| <0.2V | Reference failed | Shunt reference IC failed; replace |
| >3.0V | Reference over-voltage | R2 or divider fault |
| 0V with output voltage present | Open in reference circuit | Check R2, connections |

**Relationship to Output Voltage:** If TP3 reads correctly but output is wrong, the fault is likely in the optocoupler or primary-side control loop. If TP3 is wrong, the secondary-side feedback network (R2, shunt reference) is the fault.

**Time Estimate:** 30–60 seconds

**Related Chunks:** SIG-004, SIG-005, CAUS-003, AMB-002

---

### MEAS-008: Output Capacitor ESR Test (C12)

**Test Point:** C12 positive and negative terminals

**Instrument:** ESR meter (preferred) or LCR meter (out-of-circuit)

**IMG:** IMG_REF_SECONDARY_ZONE

⚠️ **SAFETY:** Discharge C12 before connecting ESR meter leads. Although C12 is on the secondary (12V) side, stored charge can affect measurements.

**ESR Reference Values for C12 (typical 1000–2200µF, 16–25V electrolytic):**

| ESR | Status | Action |
|-----|--------|--------|
| <0.1Ω | Good | No action required |
| 0.1–0.2Ω | Acceptable | Monitor |
| 0.2–0.5Ω | Degraded | Plan replacement |
| >0.5Ω | Failed | Replace immediately |

**In-Circuit Caveats:**

- Output Schottky diode may provide parallel path; disconnect or account for
- Compare to known-good unit when possible
- If ESR meter unavailable, measure output ripple with oscilloscope as indirect indicator

**Decision Logic:**

| ESR Result | Interpretation | Next Action |
|------------|----------------|-------------|
| <0.1Ω | C12 OK | Look elsewhere for ripple/voltage issues |
| 0.1–0.5Ω | Marginal | Replace C12 as preventive measure |
| >0.5Ω | High ESR — faulty | REP-002 (C12 replacement) |

**Defined Fault:** excessive_ripple maps to C12 failure

**Time Estimate:** 2–3 minutes

**Related Chunks:** SIG-006, COMP-006, CAUS-002, REP-002

---

## SECTION 5: COMPONENT FAULT MODELS (COMP-*)

### COMP-001: Primary MOSFET Fault Model

**Component:** Primary-side power MOSFET (N-channel, 600–800V rated, TO-220 or TO-262 package)

**Location on PCB:** Right-side area, possibly mounted to metal chassis as heatsink; visible 3-terminal device

**IMG:** IMG_REF_MOSFET_COMPONENT

**Failure Probability:** ~35% (highest single-component failure rate in system)

**Why 35% — Mechanistic Reasoning:**

| Stress Factor | Severity | Explanation |
|---------------|----------|-------------|
| Voltage stress | Extreme | Sustains 310V DC bus + 400–600V switching spikes (transformer leakage) |
| Thermal stress | High | On/off switching causes I²R heating; heatsink interface critical |
| Avalanche stress | High | Repeated avalanche from leakage inductance spikes |
| Current stress | High | Full primary current (2–5A peak in this power range) |

**Primary Failure Modes:**

| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| Drain-Source short | 70% | Avalanche breakdown; thermal runaway; EOS | D-S < 10Ω; fuse blows |
| Gate-Source short | 20% | Gate oxide puncture from ESD or dV/dt events | G-S < 100Ω; no switching |
| Open (drain or gate) | 10% | Bond wire lift from thermal cycling | DC bus present; no switching; MOSFET cold |

**Visual Indicators:**

- Cracked or exploded plastic package body
- Burn marks or carbon on heatsink surface
- Discolored or dried thermal compound
- PCB discoloration under or near device
- Melted solder at drain connection

**Cascading Damage When MOSFET Fails Short:**

```
MOSFET D-S shorts
  └─► DC bus connected to transformer primary constantly
      └─► Transformer primary saturates
          └─► Current spikes massively
              └─► Fuse F1 blows (protective sacrifice)
```

**Cascading Damage When MOSFET Fails From Upstream Cause:**

```
Secondary Schottky shorts (CAUS-001)
  └─► Excessive primary current
      └─► MOSFET thermal stress exceeds limits
          └─► MOSFET fails D-S short
              └─► MOSFET is VICTIM, not root cause
```

**Recurrence Prevention:** After replacement, always verify: secondary Schottky (MEAS-005), snubber integrity (visual + resistance), bulk capacitor ESR (MEAS-001 ripple check), gate drive resistor value.

**Related Chunks:** SIG-002, MEAS-003, CAUS-001, VI-001, REP-001, RM-001

---

### COMP-002: Bridge Rectifier Fault Model

**Component:** Full-wave bridge rectifier (single package or 4 discrete diodes); converts AC input to DC

**Location:** Primary side, near AC input terminals; upper-left area of PCB

**IMG:** IMG_REF_PRIMARY_ZONE

**Failure Probability:** ~15% of all failures; 30% when input section is faulty

**Primary Failure Modes:**

| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| One diode short | 50% | Inrush surge; EOS; thermal | Fuse blows; half-wave DC output |
| One diode open | 30% | Bond wire; thermal fatigue | Low DC bus (half-wave rectification only) |
| Full bridge short | 10% | Catastrophic surge | Massive fuse blow; possible PCB damage |
| High forward drop | 10% | Junction degradation | Lower DC bus voltage under load |

**Diagnostic:** Test with diode test mode in both directions across each arm (MEAS-004). All four diodes should show 0.5–0.8V forward, OL reverse.

**Visual Indicators:**

- Case cracking or discoloration (single package)
- Burn marks on PCB near rectifier
- Bulging or swollen package

**Related Chunks:** MEAS-004, SUB-001, SIG-002, CAUS-001

---

### COMP-003: Bulk Input Capacitor Fault Model

**Component:** Electrolytic bulk capacitor(s) on primary/DC bus side; smooths rectified DC

**Location:** Upper-left cluster of electrolytic capacitors (PCB primary side)

**IMG:** IMG_REF_SMALL_CAPS

**Failure Probability:** ~10% of all failures; more common as contributing factor

**Primary Failure Modes:**

| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| High ESR | 40% | Electrolyte evaporation with age/heat | Increased DC bus ripple; MOSFET stress |
| Capacitance loss | 30% | Electrolyte depletion | Lower effective filtering; ripple increase |
| Open circuit | 20% | Lead connection failure | Near-zero DC bus; complete failure |
| Short circuit | 10% | Dielectric breakdown | Fuse blow; DC bus collapse |

**Failure Progression:**

```
Normal → ESR increases → DC bus ripple increases → MOSFET avalanche stress increases → MOSFET failure → Fuse blows
```

**Visual Indicators:**

- Top of capacitor bulging (pressure vent dome) — definitive failure sign
- Electrolyte residue (brown/dark stain at top or base)
- Swollen cylindrical body
- Capacitor leaning (lead stress from swelling)

**Related Chunks:** SIG-001, SIG-006, MEAS-001, CAUS-002, VI-003

---

### COMP-004: Output Schottky Diode Fault Model

**Component:** Output rectifier Schottky diode on secondary side; rectifies transformer secondary to DC output

**Location:** Secondary side, near output capacitor C12; may be TO-220 or TO-263 package

**IMG:** IMG_REF_SECONDARY_ZONE

**Failure Probability:** ~20% of all failures; ~35% of output section failures

**Why Schottky Diodes Fail:**

- Lower voltage rating headroom than standard diodes
- High sensitivity to reverse voltage spikes
- Forward current rating must handle full output current continuously

**Primary Failure Modes:**

| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| Short circuit | 60% | Thermal runaway; overcurrent; reverse overvoltage | Near-zero resistance both directions |
| Open circuit | 30% | Bond wire failure; thermal fatigue | High resistance both directions; no output |
| Increased leakage | 10% | Junction damage | Low reverse resistance; output slightly low |

**Critical Impact:** A shorted Schottky diode is the most common root cause of upstream MOSFET failure (see CAUS-001). When MOSFET fails, always test Schottky.

**Recurrence:** Replacing MOSFET without replacing shorted Schottky = 40–70% recurrence.

**Related Chunks:** MEAS-005, COMP-001, CAUS-001, SIG-002, SIG-004

---

### COMP-005: PWM Controller U5 Fault Model

**Component:** U5 — PWM controller IC (8-pin DIP, likely UC384x family or equivalent)

**Location:** Lower-center of PCB; visible 8-pin DIP package

**Defined Fault:** thermal_shutdown — primary component per equipment config

**Signal:** u5_temperature with critical threshold >95°C

**IMG:** IMG_REF_PWM_IC

**Failure Probability:** ~15% of all failures

**Primary Failure Modes:**

| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| Latch-up / overcurrent protection | 40% | Protection activated; not reset | No switching; Vcc present but no gate output |
| Internal oscillator failure | 25% | Thermal damage; aging | No switching; Vcc present |
| Reference voltage degraded | 20% | Internal bandgap aging | Wrong duty cycle; output regulation off |
| Complete internal failure | 15% | EOS; overvoltage on pins | No Vcc, no function |

**Thermal Behavior:** U5 generates heat proportional to switching frequency and gate charge. Normal operating temperature is <60°C on case. At >95°C, internal thermal protection shuts down the controller.

**Distinguishing U5 failure from MOSFET failure:**

- MOSFET failed: D-S resistance low (<10Ω); gate drive may be present
- U5 failed: MOSFET resistance normal (>100kΩ D-S); no gate drive waveform

**Related Chunks:** MEAS-007, SUB-002, SIG-007, SIG-001, FIELD-003

---

### COMP-006: Output Capacitor C12 Fault Model

**Component:** C12 — Large output electrolytic capacitor (secondary side, 12V rail filter)

**Location:** Lower-right area of PCB; the prominent large black cylindrical capacitor

**Defined Fault:** excessive_ripple per equipment configuration

**IMG:** IMG_REF_SECONDARY_ZONE

**Failure Probability:** ~20% of all failures; ~35% of output section failures

**Primary Failure Modes:**

| Mode | Probability | Mechanism | Signature |
|------|-------------|-----------|-----------|
| High ESR | 50% | Electrolyte drying; thermal cycling | Excessive output ripple; voltage sag under load |
| Capacitance loss | 30% | Electrolyte depletion | Reduced filtering; intermittent instability |
| Open circuit | 15% | Lead failure | Complete output loss or severe ripple |
| Short circuit | 5% | Dielectric breakdown | Output shorted; secondary Schottky may also fail |

**ESR Impact on Ripple:**

```
Ripple Voltage = Ripple Current × ESR
```

As ESR increases → Ripple voltage increases → Connected cameras may show interference

**Visual Indicators:** Bulging top vent, electrolyte staining, leaning body, corrosion at leads.

**Related Chunks:** MEAS-008, SIG-006, SIG-004, CAUS-002, REP-002, VI-003

---

## SECTION 6: SUBSYSTEM GATES (SG-*)

### SG-001: DC Bus Present Gate — Eliminates Input Path

**Gate Measurement:** MEAS-001 (DC Bus Voltage)

**Time Cost:** 10–30 seconds

**Decision Logic:**

```
DC BUS VOLTAGE = 155V or 310V (normal)?
    │
    ├─► YES (Present and correct)
    │   └─► ELIMINATES: AC input wiring, F1 fuse, EMI filter,
    │       bridge rectifier, bulk input capacitors
    │       └─► PROCEED TO: SG-003 (Gate Drive Check)
    │           or SUB-002 (Switching Section)
    │
    └─► NO (Absent, low, or high ripple)
        └─► FAULT IN: Input path
            └─► PROCEED TO: SG-002, MEAS-002, MEAS-004
```

**Diagnostic Yield:** Eliminates ~50% of the circuit's fault space in one measurement.

⚠️ **SAFETY:** Lethal voltage measurement. Isolation from earth ground recommended if oscilloscope is used. Multimeter is safer for this test.

**Related Chunks:** MEAS-001, SG-002, SUB-001, SUB-002, YD-001

---

### SG-002: DC Bus Absent Gate — Confirms Input Path Fault

**Gate Measurement:** MEAS-001 (DC Bus = 0V result)

**Time Cost:** Follows immediately from SG-001

**Decision Logic:**

```
DC BUS = 0V?
    │
    ├─► Fuse F1 continuity test (MEAS-002)
    │   ├─► Fuse blown → Root cause investigation (SIG-002)
    │   │   └─► Test MOSFET first (MEAS-003) before replacing fuse
    │   │
    │   └─► Fuse intact
    │       └─► Bridge rectifier test (MEAS-004)
    │           ├─► Bridge shorted → Replace bridge; check fuse
    │           └─► Bridge OK → Check AC input supply, EMI filter
    │
    └─► DC Bus low (50–100V, not 0V)
        └─► Bulk capacitor ESR test or input selector check
```

**Related Chunks:** MEAS-001, MEAS-002, MEAS-004, SIG-002, SUB-001, FIELD-002

---

### SG-003: Gate Drive Present Gate — Eliminates Controller Fault

**Gate Measurement:** PWM gate drive waveform at MOSFET gate pin

**Instrument Required:** Oscilloscope + isolation transformer

**Time Cost:** 3–5 minutes (oscilloscope setup)

⚠️ **SAFETY:** Live primary-side measurement. Isolation transformer mandatory with grounded oscilloscope.

**Decision Logic:**

```
GATE DRIVE WAVEFORM PRESENT (square wave, correct frequency)?
    │
    ├─► YES (Gate drive present and correct)
    │   └─► ELIMINATES: U5 controller, Vcc supply, startup circuit
    │       └─► FAULT IN: MOSFET, transformer, or secondary section
    │           └─► PROCEED TO: MEAS-003 (MOSFET)
    │
    └─► NO (No gate drive, or incorrect)
        └─► FAULT IN: U5 controller or Vcc supply
            └─► PROCEED TO: MEAS-007 (Vcc voltage), COMP-005
```

**Related Chunks:** MEAS-007, COMP-001, COMP-005, SUB-002

---

### SG-004: Output Voltage Gate — Secondary Section Status

**Gate Measurement:** MEAS-006 (Output Voltage at TP2)

**Time Cost:** 20–30 seconds (safe low-voltage test)

**Decision Logic:**

```
OUTPUT VOLTAGE = 11.4–12.6V?
    │
    ├─► YES (Normal)
    │   └─► Output section functional; fault may be in load or cabling
    │       └─► PROCEED TO: FIELD-001 (cable drop check)
    │
    ├─► LOW (<10.8V)
    │   └─► PROCEED TO: MEAS-007 (feedback), MEAS-005 (Schottky), MEAS-008 (ESR)
    │
    ├─► HIGH (>13.2V)
    │   └─► PROCEED TO: MEAS-007 (feedback reference), check optocoupler
    │
    └─► ZERO (0V)
        └─► PROCEED TO: MEAS-001 (confirm DC bus), MEAS-005 (Schottky)
```

**Related Chunks:** MEAS-006, SIG-004, SIG-005, SUB-003

---

## SECTION 7: CAUSALITY CHAINS (CAUS-*)

### CAUS-001: Secondary Schottky Short → Fuse Blow Cascade

**Trigger:** Secondary output Schottky diode fails to short circuit

**Key Insight:** Components rarely die in isolation. The fuse is the VICTIM, not the cause.

```
ROOT CAUSE: Secondary Schottky diode shorts
    │
    └─► EFFECT 1: Transformer secondary winding effectively shorted
        │
        └─► EFFECT 2: Reflected impedance to primary drops dramatically
            │
            └─► EFFECT 3: Primary current increases beyond rated limits
                │
                └─► EFFECT 4: MOSFET thermal stress rises sharply
                    │
                    └─► EFFECT 5: MOSFET fails D-S short (victim, not root cause)
                        │
                        └─► EFFECT 6: DC bus connected hard to transformer primary
                            │
                            └─► EFFECT 7: Massive current through bridge rectifier
                                │
                                └─► SYMPTOM: Fuse F1 blows (OBSERVED)
```

**Key Diagnostic Insight:** The fuse is the LAST component to fail. The MOSFET is the SECOND-TO-LAST. The secondary Schottky is the ROOT CAUSE. Replacing fuse + MOSFET without replacing Schottky guarantees recurrence.

**Diagnostic Mandate:** If MOSFET is shorted, you MUST test the secondary output diode before powering on the repaired primary.

**Repair Sequence:** Replace Schottky → Replace MOSFET (REP-001) → Replace Fuse → Verify.

**Related Chunks:** SIG-002, COMP-001, COMP-004, MEAS-003, MEAS-005, REP-001, RM-001

---

### CAUS-002: Bulk Capacitor ESR Degradation → Output Instability

**Trigger:** Primary-side bulk capacitor ESR increases with age/temperature

```
ROOT CAUSE: Bulk capacitor ESR increases over time
    │
    └─► EFFECT 1: DC bus ripple increases (Vripple = Iripple × ESR)
        │
        └─► EFFECT 2: MOSFET drain voltage shows increased ripple spikes
            │
            └─► EFFECT 3: Increased avalanche stress on MOSFET
                │
                ├─► EFFECT 4a: MOSFET degradation (long-term) → eventual MOSFET failure
                │
                └─► EFFECT 4b: Output ripple increases (through transformer)
                    │
                    └─► SYMPTOM: Intermittent output, instability, noise
```

**Detection:** Measure DC bus ripple with oscilloscope. >30Vpp ripple with 230VAC input suggests capacitor failure. ESR test on bulk caps.

**Related Chunks:** COMP-003, MEAS-001, MEAS-008, SIG-006, SIG-003

---

### CAUS-003: Optocoupler CTR Degradation → Overvoltage Cascade

**Trigger:** Feedback optocoupler CTR (Current Transfer Ratio) degrades with age

```
ROOT CAUSE: Optocoupler LED efficiency decreases (CTR drops)
    │
    └─► EFFECT 1: Less photocurrent reaching primary-side phototransistor
        │
        └─► EFFECT 2: Controller sees reduced feedback signal
            │
            └─► EFFECT 3: Controller interprets signal as "output too low"
                │
                └─► EFFECT 4: Controller increases duty cycle to compensate
                    │
                    └─► EFFECT 5: Output voltage rises above set point
                        │
                        ├─► OUTCOME A: OVP may activate → output shuts down → SIG-003
                        │
                        └─► OUTCOME B: SYMPTOM: Output high (>13.2V) → SIG-005
```

**Key Insight:** Overvoltage from optocoupler degradation is a gradual failure — output slowly drifts upward over weeks/months before becoming fault-level.

**Related Chunks:** SIG-005, MEAS-007, AMB-002

---

## SECTION 8: FIELD-INDUCED FAULTS (FIELD-*)

### FIELD-001: DC Output Cable Voltage Drop

**Symptom:** Output voltage correct at PSU terminals (TP2) but low at CCTV camera load

**Cause:** Excessive cable resistance (length or undersized gauge)

**Mechanism:** V_drop = I_load × R_cable

**IMG:** IMG_REF_CABLE_DROP

**Test Procedure:**

1. Measure voltage at PSU output terminals (TP2) under full load
2. Measure voltage at camera end of cable under same load
3. Calculate: V_drop = V_psu − V_camera

**Decision Logic:**

| V_drop | Interpretation | Action |
|--------|----------------|--------|
| <0.3V | Normal for typical installation | Look elsewhere |
| 0.3–0.8V | Marginal; acceptable for short runs | Consider cable upgrade for reliability |
| >0.8V | Excessive | Shorten cable, increase wire gauge, or use higher voltage PSU |
| >1.5V | Severe | Likely undersized or damaged cable |

**Common CCTV Scenario:** Long cable runs (>20m) with 18AWG or thinner cable to cameras drawing 500mA–1A each can create significant voltage drop. The PSU may be functioning correctly while cameras receive under-voltage.

**Resolution:**

1. Adjust the Trimpot (VR1) strictly while measuring voltage at the camera end under maximum load (IR LEDs on)
2. Do not exceed 13.5V at the PSU terminals to avoid OVP triggers

**Related Chunks:** SIG-004, MEAS-006, AMB-001

---

### FIELD-002: Input Voltage Mismatch (230V vs 115V Selector)

**Symptom:** Unit completely dead, or output grossly incorrect

**Cause:** Input voltage selector (if present) set incorrectly, or wrong supply voltage applied

**IMG:** IMG_REF_PRIMARY_ZONE

**Mechanism — 115V on 230V-selected PSU:**

- DC bus will be ~155V instead of ~310V
- Output may be ~6V instead of ~12V
- Unit may attempt to operate at reduced efficiency

**Mechanism — 230V on 115V-selected PSU:**

- DC bus will be ~310V instead of ~155V
- Overvoltage on primary components
- Immediate component failure (bulk cap, MOSFET breakdown)
- Fuse may blow; catastrophic damage possible

**Test:** Verify AC input voltage with multimeter at AC_IN test point. Verify selector switch position matches supply voltage.

**Decision Logic:**

| Condition | DC Bus Result | Action |
|-----------|---------------|--------|
| 230V supply, correct selector | 310–330V | Normal |
| 115V supply, correct selector | 155–165V | Normal |
| 230V supply, selector at 115V | 310–330V but unit designed for 155V | Unit may be damaged |
| 115V supply, selector at 230V | 155V appears as 310V range miss | Output ~6V; set selector correctly |

**Related Chunks:** MEAS-001, SG-002, SUB-001

---

### FIELD-003: Inadequate Ventilation — Thermal Shutdown

**Symptom:** Unit powers on, operates for 5–30 minutes, then shuts down; recovers after cooling

**Cause:** Insufficient airflow in installation; ambient temperature too high

**Defined Fault:** thermal_shutdown — U5 temperature

**IMG:** IMG_REF_THERMAL

**Common Causes:**

- PSU mounted inside sealed metal enclosure with no ventilation slots
- PSU mounted with ventilation slots blocked
- Installation in high-ambient-temperature environment (roof space, outdoor cabinet in summer)
- Multiple heat sources in same enclosure

**Verification Test:**

1. Operate unit with cover removed (open-air)
2. If runtime increases significantly → ventilation is primary cause
3. If still shuts down with cover removed → component fault (U5, MOSFET degradation)

**Resolution Options:**

| Severity | Resolution |
|----------|------------|
| Mild | Ensure ventilation slots unobstructed |
| Moderate | Add ventilation holes to enclosure, reposition PSU |
| Severe | Add active cooling (small fan), or derate load |
| Component fault | Address U5 or heatsink thermal interface |

**Related Chunks:** SIG-007, COMP-005

---

## SECTION 9: AMBIGUITY RESOLUTION (AMB-*)

### AMB-001: Differentiating OCP Activation vs. Component Failure

**Symptom:** Output cycling (hiccup mode) — SIG-003

**Test Sequence:**

| Test | Result | Conclusion |
|------|--------|------------|
| Disconnect all load | Cycling stops; output stable at 12V | Load-side fault (overload or short) |
| Disconnect all load | Cycling continues | PSU internal fault |
| Reconnect one camera at a time | Cycling starts at specific camera | That camera or its cable is faulty |
| Measure DC bus during cycling | Stable 310V during both on/off phases | Controller/feedback issue |
| Measure DC bus during cycling | Droops during on-phase | Bulk capacitor degraded |

**Conclusion Paths:**

- **Load fault:** Inspect camera wiring, test cameras individually
- **Internal fault:** Proceed to MEAS-008 (C12 ESR), MEAS-007 (feedback), MEAS-005 (Schottky)

**Related Chunks:** SIG-003, MEAS-001, MEAS-006, MEAS-007, MEAS-008, FIELD-001

---

### AMB-002: Differentiating OVP Activation vs. Feedback Failure

**Symptom:** Output drops suddenly to zero; power cycle restores briefly then drops again

**Test:**

| Test | Result | Interpretation |
|------|--------|----------------|
| Measure output before shutdown (fast scope) | Voltage spikes to >13.2V then drops | OVP activated; feedback or optocoupler issue |
| Measure output before shutdown | Voltage collapses without spike | OVP not involved; controller or supply failure |
| Measure TP3 (feedback ref) during operation | Reads 2.4–2.6V | Secondary feedback sensing OK |
| Measure TP3 | Reads low or drifting | Secondary feedback network faulty |
| Power cycle, measure TP3 immediately | Correct then drifts | Optocoupler thermal degradation |

**Related Chunks:** SIG-005, SIG-003, MEAS-007, CAUS-003

---

## SECTION 10: DIAGNOSTIC YIELD NOTES (YD-*)

### YD-001: Diagnostic Yield Note — DC Bus Voltage Test

**Applies To:** MEAS-001, SG-001, SG-002

**Yield Analysis:**

```
TOTAL MAJOR FAULT LOCATIONS IN THIS SMPS: ~12 key components

DC Bus PRESENT eliminates: F1, bridge rectifier, bulk cap, AC input, EMI filter = 5 components
DC Bus ABSENT eliminates: MOSFET, U5, transformer, Schottky, C12, feedback = 6 components

YIELD (bus absent): 6/12 = 50%
YIELD (bus present): 5/12 = 42%
MINIMUM YIELD: 42% regardless of result
```

**Measurement Cost:** 30–60 seconds, basic multimeter

**Risk:** High (lethal voltage) — mitigated by proper probe technique and isolation awareness

**Why Ordered After Visual:** Visual inspection (zero risk) comes first; DC bus test provides maximum yield for acceptable risk second.

**Related Chunks:** MEAS-001, SG-001, TE-001

---

### YD-002: Diagnostic Yield Note — Output Voltage Test

**Applies To:** MEAS-006, SG-004

**Yield Analysis:**

Output voltage test is the safest "first electrical test" because it is on the secondary (low-voltage) side. Even before DC bus test, this can reveal whether the PSU has any output at all.

```
OUTPUT PRESENT (any voltage) → Eliminates: total primary failure, fuse blow, bridge failure
OUTPUT ABSENT              → Narrows to: severe fault (primary, switching, or secondary)
```

**YIELD:** Medium (~30%) but achieved at zero safety risk on secondary side

**EFFICIENCY:** Highest efficiency test due to very low risk/time cost

**Why Important:** Many technicians skip this "obvious" test. Output voltage measurement provides quick confirmation that the fault is upstream (no output) or downstream (low/high output). This directs the entire subsequent diagnostic path.

**Related Chunks:** MEAS-006, SG-004

---

### YD-003: Diagnostic Yield Note — MOSFET D-S Resistance Test

**Applies To:** MEAS-003, COMP-001

**Yield Analysis:**

When symptom is SIG-002 (fuse blown), MOSFET D-S test is the highest-yield powered-off test:

```
MOSFET SHORTED (D-S <10Ω): 
  → Confirms major failure; directs to cascade tracing (CAUS-001)
  → Yield: ~60% probability correct → high yield for the symptom context

MOSFET NORMAL (D-S >100kΩ):
  → Eliminates MOSFET; directs to bridge rectifier or bulk cap
  → Eliminates ~60% of fuse-blow candidates
```

**Cost:** 1–2 minutes, powered-off, requires discharge confirmation

**Risk:** Low (powered off, discharged circuit)

**Skill:** Basic — multimeter in resistance mode

**Related Chunks:** MEAS-003, SIG-002, COMP-001

---

## SECTION 11: TIME ESTIMATES (TE-*)

### TE-001: Time Estimate — Fast Triage Path (Dead Unit, Bench)

**Goal:** Reach a dominant root-cause bucket quickly for "completely dead" symptom

**Target Time:** 3–7 minutes (cover open, tools ready)

| Step | Action | Time |
|------|--------|------|
| 1 | Visual inspection — fuse, MOSFET, capacitors, burn marks | 1–2 min |
| 2 | Output voltage test (MEAS-006) — confirm zero output | 20 sec |
| 3 | Fuse continuity (MEAS-002) — check fuse before DC bus | 15 sec |
| 4 | DC bus measurement (MEAS-001) — half-split the circuit | 30–60 sec |
| 5a | If DC bus absent: MOSFET D-S test (MEAS-003) | 1–2 min |
| 5b | If DC bus present: check Vcc (MEAS-007) | 1–2 min |
| 6 | Decision: root cause bucket identified | — |

**Decision Outcome:** By end of this sequence, fault is localized to one subsystem with specific component probability ranking.

**Related Chunks:** SYS-001, MEAS-001, MEAS-002, MEAS-003, MEAS-006, YD-001

---

### TE-002: Time Estimate — Full Diagnostic Sequence (Output Degraded)

**Goal:** Fully diagnose degraded output (low/high/ripple)

**Target Time:** 15–25 minutes (oscilloscope preferred)

| Step | Action | Time |
|------|--------|------|
| 1 | Output voltage measurement (MEAS-006) | 30 sec |
| 2 | Feedback reference measurement (MEAS-007) | 30 sec |
| 3 | Output capacitor ESR test (MEAS-008) | 2–3 min |
| 4 | Output Schottky test (MEAS-005) | 1–2 min |
| 5 | DC bus voltage + ripple check (MEAS-001 with oscilloscope) | 2–3 min |
| 6 | Controller Vcc check (MEAS-007) | 1–2 min |

**Related Chunks:** SYS-002, SUB-003, MEAS-005, MEAS-006, MEAS-007, MEAS-008

---

## SECTION 12: VISUAL INDICATORS (VI-*)

### VI-001: Visual Indicators — Primary MOSFET Catastrophic Failure

**Applies To:** COMP-001, SIG-002

**IMG:** IMG_REF_MOSFET_COMPONENT

**Clues (Ranked by Reliability):**

1. **Definitive:** Cracked, holed, or exploded MOSFET plastic package — component clearly destroyed
2. **High Confidence:** Carbon/soot trail from MOSFET toward heatsink or surrounding PCB area
3. **Supporting:** Adjacent gate resistor (small resistor near MOSFET gate pin) shows burn discoloration
4. **Supporting:** PCB trace discoloration around drain pad or snubber network area
5. **Possible:** Melted solder joints at MOSFET leads (excessive heat from fault current)
6. **Secondary sign:** Thermal compound between MOSFET and heatsink appears cracked or absent (from thermal shock)

**Interpretation Rule:** Visual damage to MOSFET strongly correlates with hard primary short. Still run MEAS-003 to confirm, and MEAS-005 to check Schottky (often the root cause of MOSFET destruction).

**Related Chunks:** COMP-001, MEAS-003, MEAS-005, SIG-002, CAUS-001

---

### VI-002: Blown Fuse — Visual Identification

**Applies To:** MEAS-002, SIG-002

**IMG:** IMG_REF_BLOWN_FUSE

**Identification Clues:**

1. **Definitive:** Visible break in the fuse wire element (inspect with magnification or bright light through glass)
2. **Definitive:** Fuse element vaporized — dark/black deposit inside glass envelope
3. **High Confidence:** Black carbonized deposit on one end of glass envelope
4. **Supporting:** Slight discoloration or yellowing of normally clear glass
5. **Note:** A fuse can appear intact visually but still be open — always confirm with continuity test (MEAS-002)

**Fuse Rating Identification:** Note the fuse body markings (current rating in A, voltage rating, type T=slow/F=fast) before replacement. Replace only with identical rated fuse after root cause resolved.

**Critical Rule:** Never replace with higher-rated fuse. The fuse rating is calculated to protect the circuit. A higher-rated fuse may allow damage to propagate further.

**Related Chunks:** MEAS-002, SIG-002, SUB-001

---

### VI-003: Electrolytic Capacitor Failure — Visual Identification

**Applies To:** COMP-003, COMP-006

**IMG:** IMG_REF_SMALL_CAPS (bulk), IMG_REF_SECONDARY_ZONE (C12)

**Failure Clues (Ranked by Severity/Reliability):**

1. **Definitive:** Top of capacitor bulging outward — pressure relief vent has expanded; immediate replacement required
2. **Definitive:** Electrolyte leak — brown, dry, crystalline or sticky residue at top seam or base of capacitor
3. **High Confidence:** Capacitor body visibly swollen compared to new component
4. **Supporting:** Capacitor leaning at an angle (internal pressure causing mechanical deformation)
5. **Supporting:** Corrosion at lead entry points (electrolyte migration causes oxidation)
6. **Note:** A failing capacitor (high ESR) may show NO visual symptoms — ESR testing (MEAS-008) is required for definitive evaluation

**Observation:** On this specific board, look closely at the upper-left cluster of electrolytics (primary side bulk caps) and the large lower-right capacitor (C12, output). Both locations are common failure sites.

**Related Chunks:** COMP-003, COMP-006, MEAS-008, SIG-006

---

### VI-004: Transformer Overheating — Visual Identification

**Applies To:** COMP-008

**IMG:** IMG_REF_TRANSFORMER

**Failure Clues:**

1. **Definitive:** Windings visibly charred or melted — overheating damage
2. **High Confidence:** Brown discoloration of varnish/potting compound on bobbin (normally yellow/cream)
3. **High Confidence:** Crack or split in ferrite core (physical damage from thermal stress)
4. **Supporting:** Strong smell of burnt varnish during/after operation
5. **Supporting:** PCB discoloration around transformer footprint
6. **Supporting:** Delamination or bubbling of insulation tape between winding layers

**Note on This Board:** The transformer uses a yellow/gold wound bobbin. Discoloration from this original yellow toward brown or black indicates thermal damage.

**Related Chunks:** COMP-008, SIG-004, CAUS-001

---

## SECTION 13: RECURRENCE RISK MATRICES (RM-*)

### RM-001: Recurrence Risk Matrix — Fuse Blows Symptom

**Symptom:** SIG-002 — Fuse Blows Immediately on Power-Up

| If you replace only... | Recurrence Risk | Why it comes back |
|------------------------|-----------------|-------------------|
| Fuse only | 95%+ | Hard short remains; immediate re-blow |
| Fuse + MOSFET (without checking Schottky) | 40–70% | If Schottky was root cause, it will destroy new MOSFET |
| Fuse + MOSFET + Schottky (without ESR check) | 10–20% | Degraded bulk cap may stress new MOSFET over weeks |
| Fuse + MOSFET + Schottky + bulk cap ESR verified | 5–10% | Possible unidentified cascade component |
| Full root cause analysis + all cascade components | <5% | Comprehensive repair |

**Key Insight:** Every component in the CAUS-001 cascade must be evaluated. The fuse is always a symptom.

**Related Chunks:** SIG-002, CAUS-001, COMP-001, COMP-004, REP-001

---

### RM-002: Recurrence Risk Matrix — Low Output Voltage

**Symptom:** SIG-004 — Output Below 10.8V

| If you replace only... | Recurrence Risk | Why it comes back |
|------------------------|-----------------|-------------------|
| Output capacitor C12 only | 50% | If root cause is Schottky or feedback, C12 will fail again |
| Output Schottky diode only | 40% | If C12 ESR caused overheating of Schottky, C12 must also be replaced |
| C12 + Schottky | 15% | Possible feedback network contribution |
| C12 + Schottky + feedback verified | <5% | Comprehensive repair |

**Related Chunks:** SIG-004, COMP-004, COMP-006, CAUS-002

---

## SECTION 14: REPAIR PROCEDURES (REP-*)

### REP-001: MOSFET Replacement Procedure

**Applies To:** COMP-001, SIG-002

**IMG:** IMG_REF_MOSFET_COMPONENT

⚠️ **SAFETY:**

- Disconnect AC power and wait minimum 5 minutes
- Verify DC bus voltage is <5V (MEAS-001) before any physical contact
- Use ESD wrist strap when handling replacement MOSFET
- Work on non-conductive surface

**Prerequisites:** Complete cascade analysis — verify Schottky diode (MEAS-005), verify no other shorted components, identify root cause before replacing MOSFET.

**Required Tools:** Temperature-controlled soldering iron (350°C), desoldering braid or vacuum pump, thermal compound (non-conductive), multimeter, ESD strap, replacement MOSFET (match original part number or approved equivalent with ≥ voltage rating, ≥ current rating, same package).

**Repair Procedure:**

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Confirm DC bus discharged (<5V) | Meter reading |
| 2 | Photograph/note MOSFET orientation before removal | Photo taken |
| 3 | Remove MOSFET: desolder all three leads | All leads free from PCB |
| 4 | Clean pads with desoldering braid | Clean, flat copper pads, no bridges |
| 5 | Inspect PCB for damage from fault current | No burnt traces; repair if found |
| 6 | Apply thin even layer of thermal compound to back of new MOSFET | Even coverage, no air gaps |
| 7 | Install new MOSFET in correct orientation | Gate, Drain, Source matches original |
| 8 | Solder all three leads | Good solder fillet, no bridges |
| 9 | Trim leads flush | No excessive lead protrusion |

**Pre-Power-On Verification:**

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| G-S resistance | >1MΩ | Pass if >1MΩ |
| D-S resistance | >100kΩ | Pass if >100kΩ |
| Visual solder inspection | No bridges | Pass if clean |

**Root Cause Checklist (BEFORE powering on):**

- [ ] Secondary Schottky diode tested normal (MEAS-005) — root cause of MOSFET damage confirmed/resolved
- [ ] Snubber network components measured (visual + resistance) — pass
- [ ] Bulk capacitor ESR measured — acceptable (<0.5Ω)
- [ ] Gate drive resistor measured — within spec
- [ ] Fuse replaced with correct-rated device

**Power-On Test Procedure (Dim-Bulb Tester Method):**

1. Connect AC through 60W incandescent bulb in series (current limiter)
2. Apply AC; observe bulb briefly illuminating then dimming (normal startup)
3. If bulb stays brightly lit, a short still exists — the bulb prevents new components from exploding
4. Monitor DC bus voltage — should stabilize at 155V or 310V
5. Measure output voltage (MEAS-006) — should reach 11.4–12.6V
6. If stable, remove current limiter bulb
7. Apply rated load for 10 minutes; monitor MOSFET temperature

**Related Chunks:** COMP-001, MEAS-003, MEAS-005, CAUS-001, RM-001

---

### REP-002: Output Capacitor C12 Replacement Procedure

**Applies To:** COMP-006, SIG-006, SIG-004

**IMG:** IMG_REF_SECONDARY_ZONE

⚠️ **SAFETY:** Secondary side — lower voltage risk, but discharge C12 before desoldering (stored charge at 12–16V; minimal shock risk but prevents arcing during desoldering).

**Replacement Specification:** Match or exceed original capacitor: same capacitance (µF), same or higher voltage rating (V), same or lower ESR, same physical dimensions to fit PCB. Use 105°C-rated capacitor for improved longevity.

**Repair Procedure:**

| Step | Action |
|------|--------|
| 1 | Discharge C12 (short terminals briefly with insulated probe) |
| 2 | Note polarity markings (negative stripe = negative lead) |
| 3 | Desolder both leads; remove capacitor |
| 4 | Clean pads |
| 5 | Install new capacitor with correct polarity |
| 6 | Solder leads; trim |

**Polarity Warning:** Electrolytic capacitors are polarized. Incorrect installation (reverse polarity) causes immediate failure and possible rupture. The negative lead is marked with a stripe on the capacitor body; the PCB silkscreen shows the positive (+) pad.

**Verification After Repair:**

1. ESR test on new capacitor (MEAS-008) — should be <0.1Ω
2. Power on, measure output ripple — should be <100mVpp
3. Load test at rated current for 5 minutes

**Related Chunks:** COMP-006, MEAS-008, SIG-006, CAUS-002

---

## IMAGE REFERENCE INDEX

| Image ID | Description | Location on PCB | Related Chunks |
|----------|-------------|-----------------|----------------|
| IMG_REF_BOARD_OVERVIEW | Full board top-down view; SP-80M visible; complete component layout | Entire PCB | SYS-001, VI-001 through VI-004 |
| IMG_REF_PRIMARY_ZONE | Left half of PCB; high-voltage primary side with transformer, bridge area, bulk caps, MOSFET | Left/center PCB area | SUB-001, SUB-002, COMP-001, COMP-002, COMP-003 |
| IMG_REF_SECONDARY_ZONE | Right half of PCB; low-voltage secondary side with C12, Schottky, feedback components, terminal | Right PCB area | SUB-003, COMP-004, COMP-006 |
| IMG_REF_TRANSFORMER | Large wound transformer component with yellow/gold bobbin (center-left PCB) | Center-left PCB | VI-004 |
| IMG_REF_SMALL_CAPS | Cluster of small electrolytic capacitors (upper-left area, primary side) | Upper-left PCB | COMP-003, VI-003, MEAS-001 |
| IMG_REF_DC_BUS_TESTPOINT | Test point at bulk capacitor positive terminal for DC bus measurement | Primary side, bulk cap | MEAS-001, SG-001, YD-001 |
| IMG_REF_BLOWN_FUSE | Fuse component location and visual identification reference | Primary side input | MEAS-002, SIG-002, VI-002 |
| IMG_REF_MOSFET_COMPONENT | Primary MOSFET location; right-side board area, 3-terminal device | Right edge, primary side | COMP-001, MEAS-003, VI-001, REP-001 |
| IMG_REF_PWM_IC | U5 PWM controller IC (8-pin DIP, lower-center board) | Lower-center PCB | COMP-005, MEAS-007 |
| IMG_REF_OUTPUT_TERMINAL | Green terminal block at top of board; AC/DC connection points | Top edge PCB | MEAS-006, FIELD-001 |
| IMG_REF_DEAD_UNIT | Reference view of non-powered unit for baseline visual | Entire board | SIG-001 |
| IMG_REF_THERMAL | Thermal imaging reference zones on PCB | Multiple locations | SIG-007, FIELD-003 |
| IMG_REF_CABLE_DROP | Cable connection at output terminals | Terminal block area | FIELD-001 |
| IMG_REF_HICCUP_MODE | Oscilloscope capture reference for cycling output | Output terminal / scope | SIG-003 |
| IMG_REF_LOW_OUTPUT | Meter reading reference for low output voltage condition | TP2 output | SIG-004 |
| IMG_REF_HIGH_OUTPUT | Meter reading reference for overvoltage condition | TP2 output | SIG-005 |
| IMG_REF_RIPPLE | Oscilloscope waveform reference showing excessive ripple | TP2 with AC coupling | SIG-006 |

---

## JSON SCHEMA OFFER

This documentation is available in structured JSON format for programmatic ingestion. The JSON schema includes:

- **Chunk ID**: Stable identifier (e.g., "SIG-001", "MEAS-003")
- **Chunk Type**: Category (SIG, MEAS, COMP, etc.)
- **Title**: Human-readable title
- **Content**: Full chunk content in markdown
- **Related Chunks**: Array of cross-reference IDs
- **Keywords**: Array of searchable keywords
- **Equipment ID**: CCTV-PSU-24W-V1
- **Image References**: Array of related image IDs

To request the JSON version, contact the documentation maintainer or run the ingestion script with the `--export-json` flag.

---

**Document Version:** 1.0  
**Generated:** 2026-02-25  
**Equipment:** CCTV-PSU-24W-V1 (PCB: SP-80M)  
**Image Source:** `docs/CCTV Power Supply Unit.jpeg` — PCB visual analysis included  
**Target System:** ChromaDB RAG Vector Store  
**Total Chunks:** 52 (SIG×7, SYS×3, SUB×3, MEAS×8, COMP×6, SG×4, CAUS×3, FIELD×3, AMB×2, YD×3, TE×2, VI×4, RM×2, REP×2)