RAG-Optimized Diagnostic Documentation
CCTV Power Supply Unit (12V SMPS)

RETRIEVAL INDEX
System & Subsystem Gates (SYS-, SUB-, SG-*)
IDTitleSYS-001System Not Powering On (Complete Failure)SUB-001Input/Power Section Diagnostic GateSUB-002Switching Section Diagnostic GateSG-001DC Bus Present Gate — Eliminates Input Path
Failure Signatures (SIG-*)
IDTitleSIG-001Unit Completely Dead — No LED, No OutputSIG-002Fuse Blows Immediately On Power-Up
Measurement Rules (MEAS-*)
IDTitleMEAS-001DC Bus Voltage Measurement (TP1)MEAS-002Primary Fuse Continuity TestMEAS-003Primary MOSFET/Switcher Resistance Verification
Component Fault Models (COMP-*)
IDTitleCOMP-001Primary Switching IC / MOSFET Fault Model (U5)COMP-002Output Filter Capacitor Fault Model (C12)
Causality & Physics (CAUS-, AMB-, PJ-*)
IDTitleCAUS-001Secondary Diode Short Cascade ChainAMB-001Differentiating Causes of Output Cycling/HiccupPJ-001Probability Justification — Why MOSFETs Blow Fuses
Documentation & Metrics (FIELD-, YD-, TE-, VI-, RM-, REP-)
IDTitleFIELD-001DC Output Cable Voltage DropYD-001Diagnostic Yield Note — DC Bus MeasurementTE-001Time Estimate — Fast Triage Path (Bench)VI-001Visual Indicators — Primary Side CatastropheRM-001Recurrence Risk Matrix — Blown FuseREP-001Primary Switcher (U5) Replacement Procedure

SECTION 1: SYSTEM & SUBSYSTEM GATES (SYS-, SUB-, SG-*)
SYS-001: System Not Powering On (Complete Failure)
Symptom: Complete system failure - no LED, no output voltage
System State: Completely unresponsive
IMG: IMG_REF_TERMINAL_BLOCK (No output at V+ / V-), IMG_REF_LED (Off)
Subsystem Probability Ranking:
SubsystemProbabilityReasoningInput/Power Section60%No power reaching the DC bus; typically surge or fuse related.Switching Section (U5)25%Controller failure prevents PWM switching; no energy transfer.Output Section15%A hard short on the secondary can clamp the output to 0V.
Diagnostic Sequence:

1. Test subsystems in probability order.
2. Start with SUB-001 (Input/Power Section Diagnostic Gate).
3. If Input/Power eliminated, proceed to SUB-002 (Switching Section).

First Test: MEAS-001 (DC Bus Voltage) - Highest leverage measurement.
Related Chunks: SUB-001, SUB-002, SIG-001, MEAS-001, YD-001

SUB-001: Input/Power Section Diagnostic Gate
Subsystem: Input/Power Section
Components: AC terminal blocks, EMI choke, Fuse (F1), Bridge Rectifier (Diodes), Bulk Capacitor (TP1).
IMG: IMG_REF_PRIMARY_ZONE
Component Probability Ranking (when subsystem is faulty):
ComponentProbabilityFailure ModeMechanismFuse (F1)45%Open circuitOvercurrent protection mechanism; victim of downstream short.Bridge Rectifier25%Diode shortAC inrush stress; voltage surge > Peak Inverse Voltage rating.Bulk Capacitor20%Open/High ESRElectrolyte dry-out; thermal stress.Thermistor (NTC)10%Open circuitThermal cycling fatigue; inrush damage.
Diagnostic Sequence:

1. Visual inspection (VI-001).
2. MEAS-002 (Fuse F1 continuity).
3. MEAS-001 (DC Bus Voltage at TP1).

Exit Criteria: DC bus voltage is normal (155V DC for 115V AC input, or 310V DC for 230V AC input) -> Eliminates this subsystem.
Related Chunks: SYS-001, SG-001, MEAS-001, MEAS-002, COMP-001

SG-001: DC Bus Present Gate — Eliminates Input Path
Gate Measurement: MEAS-001 (DC Bus Voltage)
Time Cost: 10–30 seconds
IMG: IMG_REF_BULK_CAP
Decision Logic:
DC BUS VOLTAGE (TP1) = 155V or 310V (normal)?
    │
    ├─► YES (Present)
    │   └─► ELIMINATES: AC input block, Fuse (F1), EMI filter, Bridge Rectifier.
    │       └─► PROCEED TO: SUB-002 (Switching Section)
    │
    └─► NO (Absent/Low)
        └─► FAULT IN: Input path
            └─► PROCEED TO: MEAS-002 (Fuse Test)

Diagnostic Yield: Eliminates ~50% of circuit in one measurement.
Related Chunks: MEAS-001, SUB-001, YD-001

SECTION 2: FAILURE SIGNATURES (SIG-*)
SIG-001: Unit Completely Dead — No LED, No Output
Symptom Class: Total Power Failure
Observable: No electrical activity. Green LED is off. Output across TP2 is 0V.
IMG: IMG_REF_LED
Diagnostic Implication: Energy is either not reaching the primary switching stage, the switching stage is dead, or a secondary short is triggering constant overcurrent protection (hiccup/latch).
First Test: MEAS-001 (DC Bus Voltage).
Expected If Fault Here: 0V on bulk capacitor implies input failure; 310V implies switching or secondary failure.
Related Chunks: SYS-001, SG-001, MEAS-001

SIG-002: Fuse Blows Immediately On Power-Up
Symptom Class: Instantaneous Primary Overcurrent
Observable: Glass fuse (F1) ruptures within <100ms of AC application.
Visual: Glass envelope is blackened or metallic vapor deposited on inside.
IMG: IMG_REF_PRIMARY_FUSE
Diagnostic Implication: Hard short exists on the primary side. Current path: AC → Rectifier → DC Bus → Short.
Root Cause Candidates:
CauseProbabilityMechanismSwitcher/MOSFET short60%Avalanche breakdown; high thermal stress (COMP-001).Bridge rectifier short30%Surge damage; forward overcurrent.Bulk cap internal short10%Dielectric breakdown (rare but possible).
⚠️ Critical Rule: Do NOT replace fuse before testing primary switching IC / MOSFET for short circuit.
Next Actions: MEAS-003, CAUS-001, RM-001
Related Chunks: MEAS-002, COMP-001, PJ-001

SECTION 3: MEASUREMENT RULES (MEAS-*)
MEAS-001: DC Bus Voltage Measurement (TP1)
Test Point: Across the legs of the large bulk electrolytic capacitor (TP1).
Instrument: Multimeter in DC voltage mode, 600V or 1000V range.
IMG: IMG_REF_BULK_CAP
⚠️ SAFETY: Lethal voltage (155–340V DC). Use one-handed probing method. Discharge capacitor before physical contact if system is unplugged.
Expected Values:
VDC​≈VAC_RMS​×2​
For 230VAC input -> ~325VDC expected.
Decision Logic:
ResultInterpretationNext Action310V - 330V DCInput section OK.Proceed to SUB-002 (Switching).0VInput fault.Unplug, test Fuse F1 (MEAS-002).< 200V (on 230V AC)Degraded bulk cap.Test capacitor ESR/replace.
Diagnostic Yield: Highest leverage point in the half-split method.
Related Chunks: SG-001, YD-001, SUB-001

MEAS-002: Primary Fuse Continuity Test
Test Point: Across F1 (glass cartridge).
Instrument: Multimeter in continuity/resistance mode.
IMG: IMG_REF_PRIMARY_FUSE
⚠️ SAFETY: Ensure AC cord is completely removed from terminal block before testing. Verify DC bus is discharged.
Decision Logic:
ResultInterpretationNext Action< 2 Ω (Beep)Fuse is good.Input failure exists elsewhere (cord, thermistor, bridge trace).Open (O.L)Fuse is blown.DO NOT REPLACE YET. Proceed to MEAS-003 to find root cause.
Related Chunks: SIG-002, MEAS-003, RM-001

MEAS-003: Primary MOSFET/Switcher Resistance Verification
Test Point: Across the Drain and Source pins of the primary switcher (U5) or discrete MOSFET attached to primary heatsink.
Instrument: Multimeter in resistance mode.
IMG: IMG_REF_CONTROLLER_IC
⚠️ SAFETY: Wait 5 minutes after AC disconnection. Verify TP1 (DC Bus) is < 5V DC before probing.
Decision Logic:
ResultInterpretationNext Action< 10 ΩFatal short (Failed).Replace Switcher. Trace causality (CAUS-001).> 100 kΩNot shorted.Check start-up resistors or PWM Vcc cap.
Related Chunks: COMP-001, CAUS-001, REP-001

SECTION 4: COMPONENT FAULT MODELS (COMP-*)
COMP-001: Primary Switching IC / MOSFET Fault Model (U5)
Component: Primary-side power switcher (Integrated 8-pin DIP U5 or external TO-220).
IMG: IMG_REF_CONTROLLER_IC
Failure Probability: 35% (Highest root-cause probability after fuse).
Why 35% — Mechanistic Reasoning:
Stress FactorSeverityExplanationElectricalExtremeMust sustain 340V DC + transformer leakage inductance spikes (>500V).ThermalHighConstantly dissipates switching/conduction losses.
Primary Failure Modes:

1. Drain-Source Short (70%): Avalanche breakdown. Signature: 0Ω D-S, blows F1 instantly.
2. Open Circuit (10%): Thermal bond wire failure. Signature: DC bus present, 0V output, U5 runs cold.

Recurrence Prevention: If U5 fails short, check the secondary Schottky diode and primary snubber diode. A shorted secondary diode destroys the primary switcher via reflected overcurrent.
Related Chunks: MEAS-003, CAUS-001, REP-001, PJ-001

COMP-002: Output Filter Capacitor Fault Model (C12)
Component: High-frequency, low-ESR electrolytic capacitors on secondary side.
IMG: IMG_REF_OUTPUT_CAPS
Failure Probability: 40% (Most common delayed/wear-out failure).
Mechanistic Reasoning:
High frequency ripple current (30kHz - 100kHz) flowing through the capacitor's internal Equivalent Series Resistance (ESR) generates internal heat P=I2×R. This heat evaporates the liquid electrolyte over years of 24/7 operation.
Signatures:

* Bulging tops or pushed-out rubber bungs.
* Output voltage reads normal (12V) on DMM with no load, but drops to 8V under camera load (Output Rail Collapse).
* CCTV cameras show rolling lines or lose night-vision (IR LED spike causes voltage droop).

Related Chunks: FIELD-001, AMB-001

SECTION 5: CAUSALITY, AMBIGUITY, AND YIELD (CAUS-, AMB-, YD-*)
CAUS-001: Secondary Diode Short Cascade Chain
Key Insight: Components rarely die in isolation.
ROOT CAUSE: Secondary Output Diode Rectifier Shorts (from heat/age)
    └─► EFFECT 1: Transformer secondary is effectively short-circuited.
        └─► EFFECT 2: Reflected impedance to primary drops to near zero.
            └─► EFFECT 3: Primary current through U5 increases exponentially.
                └─► EFFECT 4: U5 Switcher fails short (D-S short).
                    └─► EFFECT 5: DC bus is short-circuited.
                        └─► SYMPTOM: F1 Fuse Blows (SIG-002).

Diagnostic Mandate: If U5 is shorted, you MUST test the secondary output diode before powering on the repaired primary.
Related Chunks: COMP-001, SIG-002, REP-001

AMB-001: Differentiating Causes of Output Cycling/Hiccup
Symptom: LED flashes, output pulses between ~3V and 12V at 1-2 Hz.
Differentiation Tests:
TestResultImplies Root CauseRemove all field wiring from V+/V-LED stabilizes solid green.External field short circuit. PSU is fine.Remove load, cycling continuesVoltage across U1/U5 Vcc pin fluctuates wildly.Primary start-up cap degraded.Remove load, cycling continuesOutput barely reaches 5V before resetting.Secondary Schottky diode leaky/shorted.
Related Chunks: FIELD-001

YD-001: Diagnostic Yield Note — DC Bus Measurement
Applies To: MEAS-001, SG-001
Diagnostic Yield: Eliminates ~40–50% of the power chain in 10 seconds.
Risk/Cost of Error: High (Requires measuring live primary HV up to 340V DC).
Why Ordered Early: It is the perfect O(log n) binary search midpoint for an SMPS. It immediately tells the technician whether to look left (Input/AC) or right (Switching/Secondary) on the schematic.
Related Chunks: SG-001

SECTION 6: METRICS AND FIELD PROCEDURES (FIELD-, TE-, RM-, REP-)
FIELD-001: DC Output Cable Voltage Drop
Symptom: Power supply TP2 measures 12.0V, but cameras go offline at night.
IMG: IMG_REF_TERMINAL_BLOCK
Cause: Excessive cable length or undersized gauge (AWG).
Mechanism: I×R voltage drop. When IR LEDs turn on at night, current increases, raising the voltage drop in the cable, crashing the camera.
Resolution:

1. Adjust the Trimpot (VR1) strictly while measuring voltage at the camera end under maximum load (IR on).
2. Do not exceed 13.5V at the PSU terminals to avoid OVP triggers.
Related Chunks: COMP-002


RM-001: Recurrence Risk Matrix — Blown Fuse
Symptom: SIG-002 (Fuse Blows Immediately).
If Technician Replaces...Recurrence RiskResulting OutcomeOnly Fuse (F1)95%+Immediate flash/bang. Fuse blows again.Fuse + U5 Switcher40%Switcher fails again if secondary diode is root cause.Fuse + Switcher + Diode< 5%Highly verified, successful repair.
Related Chunks: CAUS-001, COMP-001, PJ-001

REP-001: Primary Switcher (U5) Replacement Procedure
Applies To: COMP-001 (Switcher shorted).
⚠️ SAFETY: Disconnect AC. Wait 5 minutes. Verify 0V across TP1 (Bulk Cap) before touching board.
Procedure:

1. Desolder the 8-pin DIP U5 or heatsink-mounted power IC.
2. Clean pads with solder wick.
3. Install matching replacement part.

Root Cause Verification Checklist (CRITICAL):

*  MEAS-002: New fuse installed.
*  MEAS-003: New switcher reading > 100kΩ D-S.
*  Secondary Check: Measured output Schottky diode (heatsink, top left) to ensure it is not shorted.
*  Snubber Check: Measured primary snubber diode (near transformer) to ensure it is not open/short.

Power-On Protocol:
Use a Dim-Bulb Tester (series 60W incandescent bulb on AC line) for the first power-up. If the bulb stays brightly lit, a short still exists, but the bulb prevents the new components from exploding.
Related Chunks: COMP-001, CAUS-001, RM-001

IMAGE REFERENCE INDEX
Image IDVisual Description & LocationRelated ChunksIMG_REF_TERMINAL_BLOCKTop orange/green block (AC in right, DC out left).SYS-001, FIELD-001IMG_REF_PRIMARY_ZONERight side of PCB, characterized by warning labels and high-clearance traces.SUB-001IMG_REF_PRIMARY_FUSEGlass cartridge fuse (F1), middle right edge.SIG-002, MEAS-002IMG_REF_BULK_CAPLarge black cylinder, bottom right (TP1 test point).MEAS-001, SG-001IMG_REF_CONTROLLER_IC8-pin DIP IC (U1/U5), bottom left of primary zone.MEAS-003, COMP-001IMG_REF_OUTPUT_CAPSCluster of three capacitors, top left (C12).COMP-002IMG_REF_LEDSmall green component near terminal block, top left.SIG-001

Document Version: 1.0
Equipment: CCTV-PSU-24W-V1 / SP-80W
Generated for: RAG-Enhanced AI Diagnostic Engine