RAG-Optimized Diagnostic Documentation
CCTV Power Supply Unit — SP-80M SMPS (12V Output)
Document Version: 1.0
Equipment ID: CCTV-PSU-24W-V1 (PCB Marking: SP-80M)
Generated: 2026-02-24

IMAGE ANALYSIS — PCB Component Identification
Based on visual inspection of the provided image, the following component layout was identified:
Board Overview: The SP-80M PCB is mounted in a metal chassis/enclosure. The image is captured with the board slightly rotated; the PCB silkscreen "SP-80M" and "S0S" are visible (inverted in image). The board follows a classic flyback/forward converter topology.
Physical Zones Identified:

* Upper-left quadrant: Cluster of 3–4 small electrolytic capacitors (likely input filter/bulk caps), blue disc ceramic capacitors (snubber/EMI filter), and small inductors
* Center-left: Large wound transformer with yellow/gold bobbin — primary power transformer
* Upper-right: Yellow block component — likely auxiliary supply transformer or relay; green terminal block for AC/DC connections
* Lower-center: 8-pin DIP IC — PWM controller (U5 candidate)
* Lower-right: Large black cylindrical electrolytic capacitor — primary output bulk/filter capacitor (C12 candidate)
* Right edge: Multiple 3-terminal devices — likely MOSFETs, Schottky diodes, and/or BJTs on heatsink tabs
* Center-bottom (near IC): Small signal transistors and resistor network — feedback/optocoupler zone

Safety Zone Demarcation:

* PRIMARY SIDE (HIGH VOLTAGE — LETHAL): Left half of board, transformer primary, bridge rectifier area, upper-left bulk capacitors, fuse location
* SECONDARY SIDE (LOW VOLTAGE — SAFER): Right half of board, large output capacitor, output Schottky diode, output terminal connections


RETRIEVAL INDEX
Failure Signatures (SIG-*)
IDTitleSIG-001Unit Completely Dead — No LED, No Fan, No OutputSIG-002Fuse Blows Immediately On Power-UpSIG-003Output Cycling / Hiccup Mode — 0.5–2 HzSIG-004Low Output Voltage — Below 10.8VSIG-005High Output Voltage — Above 13.2VSIG-006Excessive Output Ripple / NoiseSIG-007Thermal Shutdown — Works Cold, Fails Hot
System-Level Diagnostic Gates (SYS-*)
IDTitleSYS-001System Not Powering On — Complete FailureSYS-002System Powers On But Output DegradedSYS-003System Intermittent — Temperature or Load Dependent
Subsystem Diagnostic Gates (SUB-*)
IDTitleSUB-001Input/Power Section Diagnostic GateSUB-002Switching Section Diagnostic GateSUB-003Output/Feedback Section Diagnostic Gate
Measurement Rules (MEAS-*)
IDTitleMEAS-001DC Bus Voltage MeasurementMEAS-002Fuse Continuity TestMEAS-003MOSFET Drain-Source Resistance TestMEAS-004Bridge Rectifier Diode TestMEAS-005Output Schottky Diode TestMEAS-006Output Voltage Measurement (TP2)MEAS-007Feedback Reference Voltage (TP3)MEAS-008Output Capacitor ESR Test (C12)MEAS-009PWM Controller Vcc Voltage TestMEAS-010Transformer Ring Test
Component Fault Models (COMP-*)
IDTitleCOMP-001Primary MOSFET Fault ModelCOMP-002Bridge Rectifier Fault ModelCOMP-003Bulk Input Capacitor Fault ModelCOMP-004Output Schottky Diode Fault ModelCOMP-005PWM Controller (U5) Fault ModelCOMP-006Output Capacitor (C12) Fault ModelCOMP-007Feedback Optocoupler Fault ModelCOMP-008Power Transformer Fault Model
Subsystem Gates (SG-*)
IDTitleSG-001DC Bus Present Gate — Eliminates Input PathSG-002DC Bus Absent Gate — Confirms Input Path FaultSG-003Gate Drive Present Gate — Eliminates ControllerSG-004Output Voltage Gate — Secondary Section CheckSG-005Feedback Reference Gate — Control Loop Check
Causality Chains (CAUS-*)
IDTitleCAUS-001Secondary Schottky Short → Fuse Blow CascadeCAUS-002Bulk Capacitor ESR Degradation → Output InstabilityCAUS-003Optocoupler Degradation → Overvoltage CascadeCAUS-004MOSFET Gate Drive Failure → Cold MOSFET CascadeCAUS-005Output Capacitor ESR → Ripple Cascade
Field-Induced Faults (FIELD-*)
IDTitleFIELD-001DC Output Cable Voltage DropFIELD-002Input Voltage Mismatch (230V vs 115V)FIELD-003Inadequate Ventilation — Thermal Shutdown
Ambiguity Resolution (AMB-*)
IDTitleAMB-001Differentiating OCP Activation vs. Component FailureAMB-002Differentiating OVP Activation vs. Feedback FailureAMB-003MOSFET Root Cause vs. Victim — Secondary Diode Check
Diagnostic Strategies (DS-*)
IDTitleDS-001Half-Split Strategy — DC Bus as MidpointDS-002Cascade Tracing Strategy — Work Backwards from FuseDS-003Latent Failure Strategy — Post-Repair Stress Check
Diagnostic Yield Notes (YD-*)
IDTitleYD-001Yield Note — DC Bus Voltage TestYD-002Yield Note — Output Voltage TestYD-003Yield Note — MOSFET D-S Resistance Test
Time Estimates (TE-*)
IDTitleTE-001Fast Triage Path — Dead Unit (Bench)TE-002Full Diagnostic Sequence — Output Degraded
Visual Indicators (VI-*)
IDTitleVI-001Primary MOSFET Catastrophic Failure — VisualVI-002Blown Fuse — Visual IdentificationVI-003Electrolytic Capacitor Failure — VisualVI-004Transformer Overheating — VisualVI-005Output Schottky Diode Failure — Visual
Recurrence Risk Matrices (RM-*)
IDTitleRM-001Recurrence Risk — Fuse Blows SymptomRM-002Recurrence Risk — Low Output VoltageRM-003Recurrence Risk — Thermal Shutdown
Probability Justifications (PJ-*)
IDTitlePJ-001Why MOSFET is 60% Probable When Fuse BlowsPJ-002Why Output Capacitor is 35% Probable for RipplePJ-003Why Optocoupler Causes Overvoltage
Repair Procedures (REP-*)
IDTitleREP-001MOSFET Replacement ProcedureREP-002Output Capacitor (C12) Replacement ProcedureREP-003Output Schottky Diode Replacement ProcedureREP-004Fuse Replacement (Post Root-Cause Confirmation)

SECTION 1: FAILURE SIGNATURES (SIG-*)

SIG-001: Unit Completely Dead — No LED, No Fan, No Output
Symptom Class: Total Power Failure
Observable: No indication of any electrical activity; no indicator LED, no audible relay click, zero output at terminals
Acoustic: Complete silence on power-up
Thermal: Board remains cold after several seconds with AC applied
IMG: IMG_REF_DEAD_UNIT
Diagnostic Implication:
Either no power is reaching the board, the primary stage is not converting, or the secondary stage is not delivering. This symptom does not discriminate between primary and secondary failure — the DC Bus test is the critical discriminator.
Subsystem Probability Ranking:
SubsystemProbabilityReasoningInput/Power Section60%Most failures here prevent any outputSwitching Section25%Controller or MOSFET failure prevents startupOutput/Feedback Section15%Secondary-only fault rarely produces total silence
Root Cause Candidates:
CauseProbabilityMechanismBlown fuse (F1)35%Sacrificial overcurrent device; first-fail pointMOSFET D-S short25%Prevents switching; may have also blown fusePWM controller (U5) failure20%No gate drive; no switchingBridge rectifier open15%No DC bus; no downstream powerBulk capacitor open5%Rare but eliminates DC bus
Critical Rule: Do NOT assume the fuse is the cause. Test MOSFET before replacing fuse.
First Test: MEAS-001 (DC Bus Voltage) — highest leverage
Diagnostic Sequence: MEAS-001 → SG-001 → SG-002 → MEAS-002 → MEAS-003
Recurrence Risk:
ActionRiskOutcomeReplace fuse only95%+Immediate re-blow if downstream short existsReplace fuse + MOSFET40–70%Secondary diode may still be shortedFull root cause analysis<5%Durable repair
Related Chunks: SYS-001, SUB-001, MEAS-001, MEAS-002, MEAS-003, SG-001, VI-002, RM-001

SIG-002: Fuse Blows Immediately On Power-Up
Symptom Class: Instantaneous Overcurrent / Hard Short
Observable: Fuse element ruptures within <100ms of AC power application; board remains dead
Acoustic: Possible audible pop on power-up
Thermal: Fuse glass envelope may show blackening or heat discoloration
Visual: Broken or vaporized fuse element
IMG: IMG_REF_BLOWN_FUSE
Diagnostic Implication:
A hard short exists on the DC bus. The short completes the path: AC → Bridge Rectifier → DC Bus → Short → Earth/Return. The fuse is the victim, not the cause.
Root Cause Candidates:
CauseProbabilityMechanismMOSFET Drain-Source short60%Highest stress component; avalanche breakdown or thermal runawayBridge rectifier diode short25%Surge damage; inrush stress; one arm conducting DCBulk capacitor internal short10%Dielectric breakdown from overvoltage eventPrimary transformer winding short5%Insulation failure; rare
Critical Rule: Do NOT replace fuse before measuring MOSFET D-S resistance. Replacing fuse alone results in 95%+ immediate re-blow.
Recurrence Risk:
ActionRiskOutcomeReplace fuse only95%+Immediate re-blowReplace fuse + MOSFET40–70%Re-blow if Schottky diode caused MOSFET failureReplace fuse + MOSFET + secondary Schottky5–15%Check bulk cap ESR alsoFull cascade analysis + all affected components<5%Successful repair
Next Actions: MEAS-003 (MOSFET D-S) → MEAS-004 (Bridge) → MEAS-005 (Schottky) → CAUS-001
Related Chunks: SYS-001, MEAS-002, MEAS-003, MEAS-004, COMP-001, COMP-002, CAUS-001, VI-001, VI-002, RM-001, PJ-001

SIG-003: Output Cycling / Hiccup Mode — 0.5–2 Hz
Symptom Class: Protection Activation / Overload Response
Observable: Output voltage pulses on/off at approximately 0.5–2 Hz; brief output then collapse, repeating
Acoustic: Possible faint clicking from switching activity
Thermal: MOSFET and transformer may be warm from repeated startup attempts
IMG: IMG_REF_HICCUP_MODE
Diagnostic Implication:
The PSU is starting, detecting an overload or fault condition, shutting down (OCP or OVP), recovering, and restarting. The root cause may be in the PSU itself or in the connected load.
Differentiation Tests:
TestResultInterpretationDisconnect load, observe outputCycling stops, stable outputLoad is shorted or drawing excess currentDisconnect load, cycling continuesPSU internal faultFeedback loop, output capacitor, or winding issueDC bus voltage during cyclingStable 155/310VFeedback or controller issueDC bus during cycling droopsBulk capacitor degradedESR failureOutput voltage at peak of cycleReaches ~12V brieflyOCP activating (normal output then shutdown)Output never reaches 12VInternal short or severe overloadOutput Schottky or transformer issue
Root Cause Candidates:
CauseProbabilityMechanismLoad short or overload40%OCP triggering repeatedlyOutput capacitor high ESR (C12)25%Ripple causes false OVP/OCP triggerFeedback network fault20%Loop instability causing oscillationOutput Schottky degraded15%High forward drop causing regulation issue
First Action: Disconnect load entirely; observe output
Related Chunks: AMB-001, MEAS-006, MEAS-007, MEAS-008, COMP-006, COMP-007, CAUS-005, SG-004, SG-005

SIG-004: Low Output Voltage — Below 10.8V (Fault Threshold)
Symptom Class: Regulation Failure — Under-Voltage
Observable: Output measured at TP2 reads below 10.8V under normal load; may be 8–11V range
Signal: output_12v reads in "degraded" or "under_voltage" state
Threshold: Fault state defined as <10.8V per equipment configuration
IMG: IMG_REF_LOW_OUTPUT
Diagnostic Implication:
The PSU is operating but not regulating to the correct set point. Could be output-section degradation, feedback loop failure, or input-side marginal operation.
Root Cause Candidates:
CauseProbabilityMechanismOutput capacitor (C12) high ESR30%Increased ripple + voltage drop under loadOutput Schottky diode degraded25%Increased forward voltage reduces outputFeedback network fault25%Loop not correcting to set pointTransformer degraded (shorted turns)15%Reduced coupling, lower secondary voltageBulk capacitor degraded5%Insufficient DC bus under load
Distinguishing Tests:
TestOutcomeInterpretationMeasure voltage at no-loadNormal (12V)Load regulation failure → capacitor ESRMeasure voltage at no-loadStill lowSet-point or feedback issueMeasure TP3 (feedback ref)< 2.4VFeedback pulling controller downMeasure TP3> 2.6VController not receiving correct feedbackESR test on C12High ESROutput capacitor primary cause
Diagnostic Sequence: MEAS-006 → MEAS-007 → MEAS-008 → MEAS-009
Related Chunks: MEAS-006, MEAS-007, MEAS-008, COMP-004, COMP-006, COMP-007, CAUS-002, CAUS-005, RM-002

SIG-005: High Output Voltage — Above 13.2V (Fault Threshold)
Symptom Class: Regulation Failure — Over-Voltage
Observable: Output measured at TP2 reads above 13.2V; may trigger connected equipment damage
Signal: output_12v reads "over_voltage" per equipment configuration (>13.2V)
IMG: IMG_REF_HIGH_OUTPUT
Diagnostic Implication:
The feedback loop is not correcting the output voltage downward. Either the feedback path is broken, the optocoupler is degraded, or the feedback resistor (R2) has changed value.
Root Cause Candidates:
CauseProbabilityMechanismOptocoupler degraded40%Reduced CTR means less feedback signal; controller increases duty cycleFeedback resistor (R2) value change30%Altered divider ratio changes set pointReference voltage (TP3) fault20%Shunt regulator (TL431 or equivalent) failedOVP circuit not activating10%OVP threshold too high or OVP circuit failed
Defined Fault: overvoltage_output — Primary Component: R2 (Feedback resistor) per equipment config
Critical Safety: Overvoltage can damage connected CCTV cameras. Disconnect load immediately if >13.2V detected.
Diagnostic Sequence: MEAS-007 → MEAS-006 → visual inspection R2 area
Related Chunks: MEAS-006, MEAS-007, COMP-005, COMP-007, CAUS-003, AMB-002, PJ-003

SIG-006: Excessive Output Ripple / Noise
Symptom Class: Output Quality Degradation
Observable: AC ripple superimposed on 12V DC output; may cause CCTV camera interference, image noise, or equipment instability
Defined Fault: excessive_ripple — Primary Component: C12 (Output capacitor)
IMG: IMG_REF_RIPPLE
Diagnostic Implication:
Ripple exceeds specification. The output filtering capacitor is most often responsible, but could also reflect input-side degradation causing excessive switching ripple.
Root Cause Candidates:
CauseProbabilityMechanismOutput capacitor C12 high ESR50%High ESR allows ripple current to create voltage rippleOutput capacitor C12 low capacitance20%Reduced capacitance increases rippleBulk input capacitor degraded20%Increased input ripple modulates outputOutput Schottky diode degraded10%Non-ideal switching increases ripple
Measurement: Use oscilloscope on TP2 with AC coupling, 20MHz BW limit. Ripple >200mVpp on 12V rail is excessive.
Related Chunks: MEAS-008, COMP-003, COMP-006, CAUS-005, REP-002

SIG-007: Thermal Shutdown — Works Cold, Fails Hot
Symptom Class: Temperature-Dependent Failure
Observable: Unit operates normally when cold; fails (output drops or unit shuts down) after 5–30 minutes of operation
Defined Fault: thermal_shutdown — Primary Component: U5 (Thermal management)
Signal: u5_temperature — Critical threshold >95°C per equipment config
IMG: IMG_REF_THERMAL
Diagnostic Implication:
Component U5 (PWM controller/buck converter) is reaching thermal shutdown threshold. Root cause is either excessive power dissipation or inadequate heat removal.
Root Cause Candidates:
CauseProbabilityMechanismInadequate ventilation (installation)35%Blocked airflow in enclosureU5 degraded, higher dissipation25%Internal resistance increased; more heat per wattOutput overload20%Load drawing more than rated currentThermal interface degraded15%Dried thermal compound between component and heatsinkInput voltage too high5%Higher input → more dissipation in linear elements
Distinguishing Test: Operate with enclosure open; if runtime extends significantly, ventilation is primary cause.
Related Chunks: FIELD-003, COMP-005, MEAS-006, RM-003

SECTION 2: SYSTEM-LEVEL DIAGNOSTIC GATES (SYS-*)

SYS-001: System Not Powering On — Complete Failure
Symptom: Complete system failure — no LED, no fan, zero output
System State: Completely unresponsive; AC applied, no response
Entry Point: SIG-001
Subsystem Probability Ranking:
SubsystemProbabilityReasoningInput/Power Section60%Power never reaches converter stageSwitching Section25%Power present but conversion failsOutput/Feedback Section15%Secondary fault rarely causes total silence
Diagnostic Entry — Half-Split Test:
The DC Bus Voltage test (MEAS-001) is the optimal entry point. It divides the circuit at its natural midpoint, eliminating either the input or output half with one measurement.
Diagnostic Sequence:

1. Visual inspection (zero risk — always first) → VI-001, VI-002
2. DC Bus Voltage test → MEAS-001 → SG-001 / SG-002
3. If DC bus absent → SUB-001 (Input/Power Section)
4. If DC bus present → SUB-002 (Switching Section)

Time Estimate: See TE-001
Related Chunks: SUB-001, SUB-002, SUB-003, SIG-001, SIG-002, MEAS-001, DS-001, TE-001

SYS-002: System Powers On But Output Degraded
Symptom: Unit has partial function; output present but out of specification
System State: Switching activity present; output voltage outside 11.4–12.6V normal range
Subsystem Probability Ranking:
SubsystemProbabilityReasoningOutput/Feedback Section55%Degraded output is classic secondary/feedback failureSwitching Section30%Controller or MOSFET degradation affects regulationInput/Power Section15%Marginal input affects regulation under load
Diagnostic Sequence:

1. Output Voltage test → MEAS-006 (confirm reading and severity)
2. Feedback Reference test → MEAS-007 (is control loop working?)
3. If feedback OK, test output capacitor ESR → MEAS-008
4. If feedback not OK, trace to optocoupler / feedback network

Related Chunks: SUB-003, SIG-004, SIG-005, SIG-006, MEAS-006, MEAS-007, MEAS-008

SYS-003: System Intermittent — Temperature or Load Dependent
Symptom: Unit works under some conditions, fails under others
System State: Functional at rest; fails at temperature or under load
Subsystem Probability Ranking:
SubsystemProbabilityReasoningSwitching Section45%Thermal issues commonly in U5, MOSFETOutput/Feedback Section35%Capacitor ESR worsens with temperatureInput/Power Section20%Marginal bulk cap causes input instability under load
Diagnostic Approach: Use thermal profiling and load variation testing (stimulus-response) to force the fault condition reproducibly.
Related Chunks: SIG-003, SIG-007, MEAS-008, COMP-001, COMP-005, FIELD-003, DS-003

SECTION 3: SUBSYSTEM DIAGNOSTIC GATES (SUB-*)

SUB-001: Input/Power Section Diagnostic Gate
Subsystem: Input/Power Section
Components: F1 (fuse), bridge rectifier, bulk input capacitors, EMI filter, AC input terminals
IMG: IMG_REF_PRIMARY_ZONE
Component Probability Ranking (when this subsystem is faulty):
ComponentProbabilityFailure ModeMechanismFuse F140%Open circuitSacrificial overcurrent device; failed last in cascadeBridge Rectifier30%Diode shortInrush/surge stress; thermal breakdownBulk Input Capacitors20%Open or high ESRAge-related degradation; thermalAC Input / EMI Filter10%Connection faultConnector corrosion; wiring break
Diagnostic Sequence:

1. Visual inspection of fuse F1 → VI-002
2. Fuse continuity → MEAS-002 (fastest test, 15 seconds)
3. DC Bus Voltage → MEAS-001 (confirms or eliminates subsystem)
4. If fuse OK and DC bus absent → MEAS-004 (Bridge rectifier)
5. If DC bus low → MEAS-008 variant (bulk capacitor)

Entry Criteria: SYS-001 identifies Input/Power as most probable, or DC bus absent per SG-002
Exit Criteria: DC Bus voltage normal (155V/310V) — subsystem is functional
⚠️ SAFETY: All components in this subsystem operate at lethal voltages (115–310V DC). Discharge bulk capacitors before physical contact (SAFETY-001 procedure).
Related Chunks: SYS-001, SG-001, SG-002, MEAS-001, MEAS-002, MEAS-004, COMP-002, COMP-003, VI-002

SUB-002: Switching Section Diagnostic Gate
Subsystem: Switching/Conversion Section
Components: Primary MOSFET, PWM Controller (U5), gate drive circuit, snubber network, power transformer
IMG: IMG_REF_PRIMARY_ZONE
Component Probability Ranking (when this subsystem is faulty):
ComponentProbabilityFailure ModeMechanismPrimary MOSFET50%D-S short or openHighest electrical/thermal stressPWM Controller U530%No output / wrong duty cycleThermal damage; VCC failure; latch-upPower Transformer15%Shorted turns / open windingInsulation failure; thermal stressSnubber Network5%Component failureDiode/capacitor degradation
Entry Criteria: DC bus is present (SG-001 gate passed), but no output
Diagnostic Sequence:

1. MOSFET D-S resistance (powered off) → MEAS-003
2. PWM Controller Vcc voltage → MEAS-009
3. Gate drive waveform (requires oscilloscope + isolation transformer)
4. Transformer ring test → MEAS-010

⚠️ SAFETY: DC bus is present (lethal voltage). Discharge before any physical contact.
Related Chunks: SYS-001, SG-001, SG-003, MEAS-003, MEAS-009, MEAS-010, COMP-001, COMP-005, COMP-008

SUB-003: Output/Feedback Section Diagnostic Gate
Subsystem: Output and Feedback Section
Components: Output Schottky diode, output capacitor C12, feedback resistor R2, optocoupler, TL431 (or equivalent shunt reference)
IMG: IMG_REF_SECONDARY_ZONE
Component Probability Ranking (when this subsystem is faulty):
ComponentProbabilityFailure ModeMechanismOutput Capacitor C1235%High ESRElectrolyte degradation; thermal agingOutput Schottky Diode35%Short circuitOvercurrent; thermal runawayFeedback Network (R2, optocoupler)30%Open / degraded CTRAging; thermal stress
Entry Criteria: DC bus present, switching active, but output is missing or degraded
Diagnostic Sequence:

1. Output Voltage → MEAS-006
2. Feedback Reference → MEAS-007
3. Output Schottky test → MEAS-005
4. Output Capacitor ESR → MEAS-008

Related Chunks: SYS-002, SG-004, SG-005, MEAS-005, MEAS-006, MEAS-007, MEAS-008, COMP-004, COMP-006, COMP-007

SECTION 4: MEASUREMENT RULES (MEAS-*)

MEAS-001: DC Bus Voltage Measurement
Test Point: Positive terminal of bulk input electrolytic capacitor to negative terminal (or to chassis ground)
Instrument: Multimeter, DC voltage mode, 400V or 600V range
IMG: IMG_REF_DC_BUS_TESTPOINT
⚠️ SAFETY: Lethal voltage present (155–310V DC). Use insulated probes rated for 600V CAT II minimum. One hand only. Do not touch board while measuring.
Expected Values:
AC InputExpected DC Bus115VAC input155–165V DC230VAC input310–330V DC
Decision Logic:
ResultInterpretationNext ActionEliminates155V or 310V (normal)Input path fully functionalProceed to SG-001, test switchingAC input, F1, bridge rectifier, bulk cap0VInput path faultTest fuse MEAS-002, then bridge MEAS-004Secondary, feedback, MOSFET50–100V (low)Bulk cap degraded or selector mismatchTest bulk cap ESR; check selector—Correct voltage with high ripple (>30Vpp AC)Bulk cap ESR failureReplace bulk capacitor—
Diagnostic Yield: Highest single test — eliminates ~50% of circuit in 10–30 seconds
Time Estimate: 30–60 seconds (with meter ready and cover open)
Related Chunks: SG-001, SG-002, COMP-002, COMP-003, YD-001, TE-001

MEAS-002: Fuse Continuity Test (F1)
Test Point: Across fuse F1 terminals (fuse removed from circuit, or in-circuit with AC disconnected)
Instrument: Multimeter, continuity mode or resistance mode
IMG: IMG_REF_BLOWN_FUSE
⚠️ SAFETY: AC power must be disconnected before testing fuse in-circuit. Discharge bulk capacitor first (see SAFETY-001).
Procedure:

1. Disconnect AC power
2. Wait 2 minutes minimum; verify DC bus <50V
3. Set meter to continuity or resistance mode
4. Probe across fuse terminals

Decision Logic:
ResultInterpretationNext ActionContinuity (0–2Ω)Fuse intactFault is not fuse; proceed to MEAS-003Open circuitFuse blownDo NOT replace yet; find root cause first → MEAS-003Fuse visually blackenedCatastrophic overcurrentHard short downstream → MEAS-003 priority
Critical Rule: A blown fuse is never the root cause. Always test MOSFET D-S (MEAS-003) before replacing fuse.
Time Estimate: 15–30 seconds
Related Chunks: SIG-001, SIG-002, COMP-001, COMP-002, MEAS-003, VI-002, RM-001

MEAS-003: MOSFET Drain-Source Resistance Test
Test Point: MOSFET drain and source pins (or drain tab and source pin)
Instrument: Multimeter, resistance mode, 200Ω range
IMG: IMG_REF_MOSFET_COMPONENT
⚠️ SAFETY: AC power disconnected. DC bus MUST be discharged to <5V before probing MOSFET leads. Follow SAFETY-001 discharge procedure.
Prerequisite: MEAS-001 confirmed DC bus discharged, or 5-minute wait after AC disconnect + voltage verification.
Procedure:

1. Discharge DC bus (SAFETY-001)
2. Verify bus voltage <5V with meter
3. Set meter to resistance mode, 200Ω range
4. Black probe to MOSFET source (typically center pin of TO-220 or source pad)
5. Red probe to MOSFET drain (typically outer pin or tab)
6. Record reading; try both probe orientations

Decision Logic:
ResultInterpretationNext Action<10Ω (both orientations)D-S short — MOSFET failedMEAS-005 (find root cause), then REP-00110Ω–100kΩDegraded / marginalCOMP-001 analysis; consider replacement>100kΩ (and >1MΩ with probes reversed)Normal MOSFETProceed to MEAS-009 (controller Vcc)0.3–0.7V forward drop (body diode)Normal body diode behaviorNormal; MOSFET likely OK
Note: A healthy N-channel MOSFET will show body diode forward drop (~0.5–0.7V) in one direction and high resistance in the other. A shorted MOSFET shows near-zero resistance in both directions.
Diagnostic Yield: High — definitively identifies most common failure mode in 1–2 minutes
Time Estimate: 1–2 minutes
Related Chunks: COMP-001, SIG-002, CAUS-001, MEAS-005, REP-001, VI-001, YD-003, RM-001

MEAS-004: Bridge Rectifier Diode Test
Test Point: AC input terminals and DC output terminals of bridge rectifier
Instrument: Multimeter, diode test mode
IMG: IMG_REF_PRIMARY_ZONE
⚠️ SAFETY: AC disconnected. DC bus discharged. Bridge rectifier is on primary (high-voltage) side.
Procedure:

1. Disconnect AC power and discharge DC bus
2. Identify bridge rectifier (4-terminal device or 4 discrete diodes)
3. Set meter to diode test mode
4. Test each diode arm: probe in forward then reverse direction
5. Each diode should show 0.5–0.8V forward, OL (open) reverse

Decision Logic:
ResultInterpretationNext ActionAll arms 0.5–0.8V forward, OL reverseBridge OKFault not in bridgeAny arm shows 0V both directionsDiode shortedReplace bridge rectifierAny arm shows OL both directionsDiode openReplace bridge rectifierTwo adjacent arms shortedFull bridge shortImmediate fuse blow cause
Time Estimate: 2–3 minutes
Related Chunks: COMP-002, SIG-002, SUB-001, MEAS-002, CAUS-001

MEAS-005: Output Schottky Diode Test
Test Point: Anode and cathode terminals of output Schottky diode (on secondary side, near output capacitor C12)
Instrument: Multimeter, diode test mode
IMG: IMG_REF_SECONDARY_ZONE
Note: This is a low-voltage secondary side test. Primary side discharge precautions still apply if testing with power off, but this component is isolated from lethal voltages in normal operation.
Expected Schottky Values:
MeasurementExpectedIndicatesForward voltage (anode+, cathode−)0.15–0.45VNormal Schottky junctionReverse (cathode+, anode−)OL (open)NormalBoth directions near 0VShortedFailed diode — root cause of MOSFET damageBoth directions OLOpenFailed diode — no output rectification
Critical Importance: A shorted Schottky diode is the most common root cause of MOSFET failure (CAUS-001). Always test this diode when MOSFET has failed.
Time Estimate: 1–2 minutes
Related Chunks: COMP-004, CAUS-001, MEAS-003, REP-003, SIG-002, SIG-004

MEAS-006: Output Voltage Measurement (TP2)
Test Point: TP2 — Output terminals / output capacitor C12 positive and negative
Instrument: Multimeter, DC voltage mode, 20V range
IMG: IMG_REF_OUTPUT_TERMINAL
Normal Operating Range: 11.4–12.6V (per output_12v signal specification)
Degraded Range: 10.8–13.2V
Fault Thresholds: Under-voltage <10.8V | Over-voltage >13.2V
Decision Logic:
ResultInterpretationNext Action11.4–12.6VOutput normalCheck load, cables; fault may be downstream10.8–11.4V (degraded-low)Output marginally lowMEAS-008 (C12 ESR), MEAS-007 (feedback)<10.8V (under-voltage fault)Output regulation failureMEAS-007, MEAS-005, MEAS-00812.6–13.2V (degraded-high)Output marginally highMEAS-007 (feedback reference)>13.2V (over-voltage fault)Feedback loop failureMEAS-007 priority; risk to connected equipment0VNo outputVerify DC bus present (MEAS-001); check switching
Diagnostic Yield: Medium — confirms/rules out output section; safe low-risk test
Time Estimate: 20–30 seconds
Related Chunks: SYS-002, SIG-004, SIG-005, SG-004, MEAS-007, MEAS-008, YD-002

MEAS-007: Feedback Reference Voltage Test (TP3)
Test Point: TP3 — Feedback reference node; typically cathode of TL431 or equivalent shunt reference on secondary side
Instrument: Multimeter, DC voltage mode, 5V range
IMG: IMG_REF_SECONDARY_ZONE
Normal Range: 2.4–2.6V (per feedback_ref signal specification)
Fault Threshold: <0.2V indicates failed state
Decision Logic:
ResultInterpretationNext Action2.4–2.6VReference normalFeedback reference OK; check optocoupler, output voltage2.2–2.4V or 2.6–2.8VDegradedMonitor under load; check R2 value<0.2VReference failedShunt reference IC failed; replace>3.0VReference over-voltageR2 or divider fault0V with output voltage presentOpen in reference circuitCheck R2, connections
Relationship to Output Voltage: If TP3 reads correctly but output is wrong, the fault is likely in the optocoupler or primary-side control loop. If TP3 is wrong, the secondary-side feedback network (R2, shunt reference) is the fault.
Time Estimate: 30–60 seconds
Related Chunks: SIG-004, SIG-005, COMP-007, CAUS-003, AMB-002

MEAS-008: Output Capacitor ESR Test (C12)
Test Point: C12 positive and negative terminals
Instrument: ESR meter (preferred) or LCR meter (out-of-circuit)
IMG: IMG_REF_SECONDARY_ZONE
⚠️ SAFETY: Discharge C12 before connecting ESR meter leads. Although C12 is on the secondary (12V) side, stored charge can affect measurements.
ESR Reference Values for C12 (typical 1000–2200µF, 16–25V electrolytic):
ESRStatusAction<0.1ΩGoodNo action required0.1–0.2ΩAcceptableMonitor0.2–0.5ΩDegradedPlan replacement>0.5ΩFailedReplace immediately
In-Circuit Caveats:

* Output Schottky diode may provide parallel path; disconnect or account for
* Compare to known-good unit when possible
* If ESR meter unavailable, measure output ripple with oscilloscope as indirect indicator

Decision Logic:
ESR ResultInterpretationNext Action<0.1ΩC12 OKLook elsewhere for ripple/voltage issues0.1–0.5ΩMarginalReplace C12 as preventive measure>0.5ΩHigh ESR — faultyREP-002 (C12 replacement)
Defined Fault: excessive_ripple maps to C12 failure
Time Estimate: 2–3 minutes
Related Chunks: SIG-006, COMP-006, CAUS-005, REP-002, PJ-002

MEAS-009: PWM Controller Vcc Voltage Test (U5)
Test Point: VCC pin of U5 (PWM controller IC, 8-pin DIP) — typically pin 8 on UC384x family or equivalent
Instrument: Multimeter, DC voltage mode, 20V range
IMG: IMG_REF_PWM_IC
⚠️ SAFETY: Primary-side component. Live measurement requires isolation transformer. Discharge protocol if power-off test.
Expected Values (common PWM controllers):
Controller TypeVcc RangeUndervoltage LockoutUC3842 / UC384410–25V<8.5V (UVLO shuts down)UC3843 / UC38458–25V<7.5V (UVLO)TNY / TOP seriesPer datasheetBuilt-in UVLO
Decision Logic:
Vcc ReadingInterpretationNext ActionWithin 10–20V rangeController powered; may be functionalCheck gate drive waveform<8V (below UVLO)Controller not starting — auxiliary supply issueCheck auxiliary winding, startup resistors0VNo startup powerCheck startup resistors from DC bus to VccCorrect but no switchingController internal fault or protection latchedPower cycle; test gate output
Signal: u5_temperature measured here; critical threshold >95°C
Time Estimate: 1–2 minutes (power-on measurement)
Related Chunks: COMP-005, SUB-002, SG-003, MEAS-003

MEAS-010: Transformer Ring Test
Test Point: Primary winding terminals of power transformer
Instrument: Function generator + oscilloscope, or dedicated ring tester
IMG: IMG_REF_TRANSFORMER
⚠️ SAFETY: Perform with AC disconnected and DC bus fully discharged. Transformer is on primary side.
Setup: Apply 1–10kHz square wave pulse to primary winding; observe ringing on oscilloscope.
Interpretation:
Ring CountStatusInterpretation3+ clean rings, exponential decayGoodTransformer winding intact1–2 rings, quick decaySuspectPossible shorted turns0–1 ring, very rapid decayFailedShorted turns confirmedNo ringing, pulse passes throughOpen windingWinding break or connection failure
Shorted Turns Indicators:

* Reduced inductance (measurable with LCR meter)
* Overheating during operation
* Reduced output voltage under load

When to Use: After all other tests pass but output is still missing or low; after MOSFET replacement as verification of no upstream damage.
Time Estimate: 5–10 minutes (oscilloscope setup required)
Related Chunks: COMP-008, CAUS-001, VI-004

SECTION 5: COMPONENT FAULT MODELS (COMP-*)

COMP-001: Primary MOSFET Fault Model
Component: Primary-side power MOSFET (N-channel, 600–800V rated, TO-220 or TO-262 package)
Location on PCB: Right-side area, possibly mounted to metal chassis as heatsink; visible 3-terminal device
IMG: IMG_REF_MOSFET_COMPONENT
Failure Probability: ~35% (highest single-component failure rate in system)
Why 35% — Mechanistic Reasoning:
Stress FactorSeverityExplanationVoltage stressExtremeSustains 310V DC bus + 400–600V switching spikes (transformer leakage)Thermal stressHighOn/off switching causes I²R heating; heatsink interface criticalAvalanche stressHighRepeated avalanche from leakage inductance spikesCurrent stressHighFull primary current (2–5A peak in this power range)
Primary Failure Modes:
ModeProbabilityMechanismSignatureDrain-Source short70%Avalanche breakdown; thermal runaway; EOSD-S < 10Ω; fuse blowsGate-Source short20%Gate oxide puncture from ESD or dV/dt eventsG-S < 100Ω; no switchingOpen (drain or gate)10%Bond wire lift from thermal cyclingDC bus present; no switching; MOSFET cold
Visual Indicators:

* Cracked or exploded plastic package body
* Burn marks or carbon on heatsink surface
* Discolored or dried thermal compound
* PCB discoloration under or near device
* Melted solder at drain connection

Cascading Damage When MOSFET Fails Short:
MOSFET D-S shorts
  └─► DC bus connected to transformer primary constantly
      └─► Transformer primary saturates
          └─► Current spikes massively
              └─► Fuse F1 blows (protective sacrifice)

Cascading Damage When MOSFET Fails From Upstream Cause:
Secondary Schottky shorts (CAUS-001)
  └─► Excessive primary current
      └─► MOSFET thermal stress exceeds limits
          └─► MOSFET fails D-S short
              └─► MOSFET is VICTIM, not root cause

Recurrence Prevention: After replacement, always verify: secondary Schottky (MEAS-005), snubber integrity (visual + resistance), bulk capacitor ESR (MEAS-001 ripple check), gate drive resistor value.
Related Chunks: SIG-002, MEAS-003, CAUS-001, VI-001, REP-001, RM-001, PJ-001

COMP-002: Bridge Rectifier Fault Model
Component: Full-wave bridge rectifier (single package or 4 discrete diodes); converts AC input to DC
Location: Primary side, near AC input terminals; upper-left area of PCB
IMG: IMG_REF_PRIMARY_ZONE
Failure Probability: ~15% of all failures; 30% when input section is faulty
Primary Failure Modes:
ModeProbabilityMechanismSignatureOne diode short50%Inrush surge; EOS; thermalFuse blows; half-wave DC outputOne diode open30%Bond wire; thermal fatigueLow DC bus (half-wave rectification only)Full bridge short10%Catastrophic surgeMassive fuse blow; possible PCB damageHigh forward drop10%Junction degradationLower DC bus voltage under load
Diagnostic: Test with diode test mode in both directions across each arm (MEAS-004). All four diodes should show 0.5–0.8V forward, OL reverse.
Visual Indicators:

* Case cracking or discoloration (single package)
* Burn marks on PCB near rectifier
* Bulging or swollen package

Related Chunks: MEAS-004, SUB-001, SIG-002, CAUS-001

COMP-003: Bulk Input Capacitor Fault Model
Component: Electrolytic bulk capacitor(s) on primary/DC bus side; smooths rectified DC
Location: Upper-left cluster of electrolytic capacitors (PCB primary side)
IMG: IMG_REF_SMALL_CAPS
Failure Probability: ~10% of all failures; more common as contributing factor
Primary Failure Modes:
ModeProbabilityMechanismSignatureHigh ESR40%Electrolyte evaporation with age/heatIncreased DC bus ripple; MOSFET stressCapacitance loss30%Electrolyte depletionLower effective filtering; ripple increaseOpen circuit20%Lead connection failureNear-zero DC bus; complete failureShort circuit10%Dielectric breakdownFuse blow; DC bus collapse
Failure Progression:
Normal → ESR increases → DC bus ripple increases → MOSFET avalanche stress increases → MOSFET failure → Fuse blows
Visual Indicators:

* Top of capacitor bulging (pressure vent dome) — definitive failure sign
* Electrolyte residue (brown/dark stain at top or base)
* Swollen cylindrical body
* Capacitor leaning (lead stress from swelling)

Related Chunks: SIG-001, SIG-006, MEAS-001, CAUS-002, VI-003

COMP-004: Output Schottky Diode Fault Model
Component: Output rectifier Schottky diode on secondary side; rectifies transformer secondary to DC output
Location: Secondary side, near output capacitor C12; may be TO-220 or TO-263 package
IMG: IMG_REF_SECONDARY_ZONE
Failure Probability: ~20% of all failures; ~35% of output section failures
Why Schottky Diodes Fail:

* Lower voltage rating headroom than standard diodes
* High sensitivity to reverse voltage spikes
* Forward current rating must handle full output current continuously

Primary Failure Modes:
ModeProbabilityMechanismSignatureShort circuit60%Thermal runaway; overcurrent; reverse overvoltageNear-zero resistance both directionsOpen circuit30%Bond wire failure; thermal fatigueHigh resistance both directions; no outputIncreased leakage10%Junction damageLow reverse resistance; output slightly low
Critical Impact: A shorted Schottky diode is the most common root cause of upstream MOSFET failure (see CAUS-001). When MOSFET fails, always test Schottky.
Recurrence: Replacing MOSFET without replacing shorted Schottky = 40–70% recurrence.
Related Chunks: MEAS-005, COMP-001, CAUS-001, SIG-002, SIG-004, REP-003

COMP-005: PWM Controller U5 Fault Model
Component: U5 — PWM controller IC (8-pin DIP, likely UC384x family or equivalent)
Location: Lower-center of PCB; visible 8-pin DIP package
Defined Fault: thermal_shutdown — primary component per equipment config
Signal: u5_temperature with critical threshold >95°C
IMG: IMG_REF_PWM_IC
Failure Probability: ~15% of all failures
Primary Failure Modes:
ModeProbabilityMechanismSignatureLatch-up / overcurrent protection40%Protection activated; not resetNo switching; Vcc present but no gate outputInternal oscillator failure25%Thermal damage; agingNo switching; Vcc presentReference voltage degraded20%Internal bandgap agingWrong duty cycle; output regulation offComplete internal failure15%EOS; overvoltage on pinsNo Vcc, no function
Thermal Behavior: U5 generates heat proportional to switching frequency and gate charge. Normal operating temperature is <60°C on case. At >95°C, internal thermal protection shuts down the controller.
Distinguishing U5 failure from MOSFET failure:

* MOSFET failed: D-S resistance low (<10Ω); gate drive may be present
* U5 failed: MOSFET resistance normal (>100kΩ D-S); no gate drive waveform

Related Chunks: MEAS-009, SUB-002, SIG-007, SIG-001, FIELD-003, RM-003

COMP-006: Output Capacitor C12 Fault Model
Component: C12 — Large output electrolytic capacitor (secondary side, 12V rail filter)
Location: Lower-right area of PCB; the prominent large black cylindrical capacitor
Defined Fault: excessive_ripple per equipment configuration
IMG: IMG_REF_SECONDARY_ZONE
Failure Probability: ~20% of all failures; ~35% of output section failures
Primary Failure Modes:
ModeProbabilityMechanismSignatureHigh ESR50%Electrolyte drying; thermal cyclingExcessive output ripple; voltage sag under loadCapacitance loss30%Electrolyte depletionReduced filtering; intermittent instabilityOpen circuit15%Lead failureComplete output loss or severe rippleShort circuit5%Dielectric breakdownOutput shorted; secondary Schottky may also fail
ESR Impact on Ripple:
Ripple Voltage = Ripple Current × ESR
As ESR increases → Ripple voltage increases → Connected cameras may show interference

Visual Indicators: Bulging top vent, electrolyte staining, leaning body, corrosion at leads.
Related Chunks: MEAS-008, SIG-006, SIG-004, CAUS-005, REP-002, VI-003, PJ-002

COMP-007: Feedback Optocoupler Fault Model
Component: Feedback optocoupler — provides galvanic isolation between secondary-side voltage sensing and primary-side PWM controller
Location: Secondary side, small 4-pin DIP component near feedback resistors
Defined Fault: Contributes to overvoltage_output (R2/optocoupler path)
Failure Probability: ~10% of all failures; increases significantly with age (>5 years)
Primary Failure Modes:
ModeProbabilityMechanismSignatureCTR degradation (reduced)60%LED die degradation; reduced photocurrentOutput voltage creeps high; overvoltageLED open25%Thermal stress; aging; EOSNo feedback; output rises to OVPPhototransistor leakage15%Junction damageIncorrect duty cycle; instability
CTR (Current Transfer Ratio) Degradation: As optocoupler ages, the LED output efficiency drops. Less photocurrent reaches the controller, which interprets this as low output and increases duty cycle, causing output voltage to rise.
Relationship to R2: The overvoltage_output fault lists R2 as primary component, but optocoupler degradation produces identical symptoms. Both must be checked.
Related Chunks: SIG-005, MEAS-007, CAUS-003, COMP-005, AMB-002

COMP-008: Power Transformer Fault Model
Component: Power transformer — converts primary switching voltage to secondary output voltage
Location: Center-left of PCB; the large wound component with yellow/gold bobbin
IMG: IMG_REF_TRANSFORMER
Failure Probability: ~8% of all failures; typically a secondary failure from primary fault
Primary Failure Modes:
ModeProbabilityMechanismSignatureShorted turns40%Insulation breakdown from overheatingReduced inductance; overheating; low outputOpen primary winding30%Wire break; thermal fatigueDC bus present; no switching output; no outputOpen secondary winding20%Wire break; connection failureNo output; Schottky no inputPrimary-secondary insulation10%Insulation failureSafety hazard; mains voltage on output
Critical Safety — Primary-Secondary Short: If transformer insulation fails between primary and secondary, mains voltage (115/230V AC) can appear on the 12V output rail. This is extremely dangerous and requires immediate replacement and safety verification.
Detection: Ring test (MEAS-010), inductance measurement (LCR meter), continuity between primary and secondary (should be open circuit, >10MΩ).
Related Chunks: MEAS-010, SIG-004, CAUS-001, VI-004

SECTION 6: SUBSYSTEM GATES (SG-*)

SG-001: DC Bus Present Gate — Eliminates Input Path
Gate Measurement: MEAS-001 (DC Bus Voltage)
Time Cost: 10–30 seconds
Decision Logic:
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

Diagnostic Yield: Eliminates ~50% of the circuit's fault space in one measurement.
⚠️ SAFETY: Lethal voltage measurement. Isolation from earth ground recommended if oscilloscope is used. Multimeter is safer for this test.
Related Chunks: MEAS-001, SG-002, SUB-001, SUB-002, YD-001

SG-002: DC Bus Absent Gate — Confirms Input Path Fault
Gate Measurement: MEAS-001 (DC Bus = 0V result)
Time Cost: Follows immediately from SG-001
Decision Logic:
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

Related Chunks: MEAS-001, MEAS-002, MEAS-004, SIG-002, SUB-001, FIELD-002

SG-003: Gate Drive Present Gate — Eliminates Controller Fault
Gate Measurement: PWM gate drive waveform at MOSFET gate pin
Instrument Required: Oscilloscope + isolation transformer
Time Cost: 3–5 minutes (oscilloscope setup)
⚠️ SAFETY: Live primary-side measurement. Isolation transformer mandatory with grounded oscilloscope.
Decision Logic:
GATE DRIVE WAVEFORM PRESENT (square wave, correct frequency)?
    │
    ├─► YES (Gate drive present and correct)
    │   └─► ELIMINATES: U5 controller, Vcc supply, startup circuit
    │       └─► FAULT IN: MOSFET, transformer, or secondary section
    │           └─► PROCEED TO: MEAS-003 (MOSFET), MEAS-010 (Transformer)
    │
    └─► NO (No gate drive, or incorrect)
        └─► FAULT IN: U5 controller or Vcc supply
            └─► PROCEED TO: MEAS-009 (Vcc voltage), COMP-005

Related Chunks: MEAS-009, COMP-001, COMP-005, SUB-002

SG-004: Output Voltage Gate — Secondary Section Status
Gate Measurement: MEAS-006 (Output Voltage at TP2)
Time Cost: 20–30 seconds (safe low-voltage test)
Decision Logic:
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
    │   └─► PROCEED TO: MEAS-007 (feedback reference), COMP-007 (optocoupler)
    │
    └─► ZERO (0V)
        └─► PROCEED TO: MEAS-001 (confirm DC bus), MEAS-005 (Schottky)

Related Chunks: MEAS-006, SIG-004, SIG-005, SG-005, SUB-003

SG-005: Feedback Reference Gate — Control Loop Check
Gate Measurement: MEAS-007 (Feedback Reference at TP3)
Time Cost: 30–60 seconds
Decision Logic:
FEEDBACK REFERENCE (TP3) = 2.4–2.6V?
    │
    ├─► YES (Normal)
    │   └─► Secondary feedback sensing correct
    │       └─► Fault in optocoupler or primary control loop
    │           └─► PROCEED TO: COMP-007, MEAS-009
    │
    └─► NO (Wrong value)
        └─► Fault in secondary feedback network
            ├─► <0.2V → Shunt reference IC failed (TL431 equiv.)
            ├─► Wrong value but not zero → R2 value changed (COMP-007)
            └─► PROCEED TO: visual inspection of R2, shunt reference IC

Related Chunks: MEAS-007, COMP-007, SIG-005, AMB-002, CAUS-003

SECTION 7: CAUSALITY CHAINS (CAUS-*)

CAUS-001: Secondary Schottky Short → Fuse Blow Cascade
Trigger: Secondary output Schottky diode fails to short circuit
ROOT CAUSE: Secondary Schottky diode shorts
    │
    └─► Transformer secondary winding effectively shorted
        │
        └─► Reflected impedance to primary drops dramatically
            │
            └─► Primary current increases beyond rated limits
                │
                └─► MOSFET thermal stress rises sharply
                    │
                    └─► MOSFET fails D-S short (victim, not root cause)
                        │
                        └─► DC bus connected hard to transformer primary
                            │
                            └─► Massive current through bridge rectifier
                                │
                                └─► Fuse F1 blows (OBSERVED SYMPTOM)

Key Diagnostic Insight: The fuse is the LAST component to fail. The MOSFET is the SECOND-TO-LAST. The secondary Schottky is the ROOT CAUSE. Replacing fuse + MOSFET without replacing Schottky guarantees recurrence.
Repair Sequence: Replace Schottky (REP-003) → Replace MOSFET (REP-001) → Replace Fuse (REP-004) → Verify.
Related Chunks: SIG-002, COMP-001, COMP-004, MEAS-003, MEAS-005, REP-001, REP-003, REP-004, RM-001, PJ-001

CAUS-002: Bulk Capacitor ESR Degradation → Output Instability
Trigger: Primary-side bulk capacitor ESR increases with age/temperature
ROOT CAUSE: Bulk capacitor ESR increases over time
    │
    └─► DC bus ripple increases (Vripple = Iripple × ESR)
        │
        └─► MOSFET drain voltage shows increased ripple spikes
            │
            └─► Increased avalanche stress on MOSFET
                │
                ├─► MOSFET degradation (long-term) → eventual MOSFET failure
                │
                └─► Output ripple increases (through transformer)
                    │
                    └─► OBSERVED SYMPTOM: Intermittent output, instability, noise

Detection: Measure DC bus ripple with oscilloscope. >30Vpp ripple with 230VAC input suggests capacitor failure. ESR test on bulk caps.
Related Chunks: COMP-003, MEAS-001, MEAS-008, SIG-006, SIG-003

CAUS-003: Optocoupler CTR Degradation → Overvoltage Cascade
Trigger: Feedback optocoupler CTR (Current Transfer Ratio) degrades with age
ROOT CAUSE: Optocoupler LED efficiency decreases (CTR drops)
    │
    └─► Less photocurrent reaching primary-side phototransistor
        │
        └─► Controller sees reduced feedback signal
            │
            └─► Controller interprets signal as "output too low"
                │
                └─► Controller increases duty cycle to compensate
                    │
                    └─► Output voltage rises above set point
                        │
                        ├─► OVP may activate → output shuts down → SIG-003
                        │
                        └─► OBSERVED SYMPTOM: Output high (>13.2V) → SIG-005

Key Insight: Overvoltage from optocoupler degradation is a gradual failure — output slowly drifts upward over weeks/months before becoming fault-level.
Related Chunks: SIG-005, COMP-007, MEAS-007, AMB-002

CAUS-004: PWM Controller Vcc Failure → Cold Dead Unit
Trigger: Controller startup circuit or Vcc supply fails
ROOT CAUSE: Startup resistors (primary-to-Vcc path) fail open or Vcc capacitor fails
    │
    └─► U5 Vcc drops below UVLO threshold
        │
        └─► U5 shuts down (UVLO protection)
            │
            └─► No gate drive output from U5
                │
                └─► MOSFET does not switch (appears open)
                    │
                    └─► No energy transfer through transformer
                        │
                        └─► OBSERVED SYMPTOM: DC bus present, MOSFET cold,
                            no output (identical to open MOSFET but MOSFET is OK)

Distinguishing Test: If MOSFET D-S resistance is normal (>100kΩ) but no output, measure Vcc (MEAS-009). If Vcc < UVLO threshold, controller startup is the fault.
Related Chunks: COMP-005, MEAS-009, SG-003, SIG-001

CAUS-005: Output Capacitor ESR → Ripple and Regulation Cascade
Trigger: C12 output capacitor ESR increases
ROOT CAUSE: C12 ESR increases (electrolyte drying)
    │
    └─► Ripple voltage = Ripple current × ESR increases
        │
        ├─► Output ripple exceeds specification → SIG-006
        │
        └─► Voltage sag under load transients increases
            │
            └─► Feedback sees voltage dip, overcompensates
                │
                └─► Control loop instability
                    │
                    └─► OBSERVED SYMPTOMS: Output cycling (SIG-003),
                        Low average voltage (SIG-004), Ripple (SIG-006)

Related Chunks: COMP-006, MEAS-008, SIG-004, SIG-006, SIG-003, REP-002

SECTION 8: FIELD-INDUCED FAULTS (FIELD-*)

FIELD-001: DC Output Cable Voltage Drop
Symptom: Output voltage correct at PSU terminals (TP2) but low at CCTV camera load
Cause: Excessive cable resistance (length or undersized gauge)
Mechanism: V_drop = I_load × R_cable
IMG: IMG_REF_CABLE_DROP
Test Procedure:

1. Measure voltage at PSU output terminals (TP2) under full load
2. Measure voltage at camera end of cable under same load
3. Calculate: V_drop = V_psu − V_camera

Decision Logic:
V_dropInterpretationAction<0.3VNormal for typical installationLook elsewhere0.3–0.8VMarginal; acceptable for short runsConsider cable upgrade for reliability>0.8VExcessiveShorten cable, increase wire gauge, or use higher voltage PSU>1.5VSevereLikely undersized or damaged cable
Common CCTV Scenario: Long cable runs (>20m) with 18AWG or thinner cable to cameras drawing 500mA–1A each can create significant voltage drop. The PSU may be functioning correctly while cameras receive under-voltage.
Related Chunks: SIG-004, MEAS-006, AMB-001

FIELD-002: Input Voltage Mismatch (230V vs 115V Selector)
Symptom: Unit completely dead, or output grossly incorrect
Cause: Input voltage selector (if present) set incorrectly, or wrong supply voltage applied
IMG: IMG_REF_PRIMARY_ZONE
Mechanism — 115V on 230V-selected PSU:

* DC bus will be ~155V instead of ~310V
* Output may be ~6V instead of ~12V
* Unit may attempt to operate at reduced efficiency

Mechanism — 230V on 115V-selected PSU:

* DC bus will be ~310V instead of ~155V
* Overvoltage on primary components
* Immediate component failure (bulk cap, MOSFET breakdown)
* Fuse may blow; catastrophic damage possible

Test: Verify AC input voltage with multimeter at AC_IN test point. Verify selector switch position matches supply voltage.
Decision Logic:
ConditionDC Bus ResultAction230V supply, correct selector310–330VNormal115V supply, correct selector155–165VNormal230V supply, selector at 115V310–330V but unit designed for 155VUnit may be damaged115V supply, selector at 230V155V appears as 310V range missOutput ~6V; set selector correctly
Related Chunks: MEAS-001, SG-002, SUB-001

FIELD-003: Inadequate Ventilation — Thermal Shutdown
Symptom: Unit powers on, operates for 5–30 minutes, then shuts down; recovers after cooling
Cause: Insufficient airflow in installation; ambient temperature too high
Defined Fault: thermal_shutdown — U5 temperature
IMG: IMG_REF_THERMAL
Common Causes:

* PSU mounted inside sealed metal enclosure with no ventilation slots
* PSU mounted with ventilation slots blocked
* Installation in high-ambient-temperature environment (roof space, outdoor cabinet in summer)
* Multiple heat sources in same enclosure

Verification Test:

1. Operate unit with cover removed (open-air)
2. If runtime increases significantly → ventilation is primary cause
3. If still shuts down with cover removed → component fault (U5, MOSFET degradation)

Resolution Options:
SeverityResolutionMildEnsure ventilation slots unobstructedModerateAdd ventilation holes to enclosure, reposition PSUSevereAdd active cooling (small fan), or derate loadComponent faultAddress U5 or heatsink thermal interface
Related Chunks: SIG-007, COMP-005, RM-003

SECTION 9: AMBIGUITY RESOLUTION (AMB-*)

AMB-001: Differentiating OCP Activation vs. Component Failure
Symptom: Output cycling (hiccup mode) — SIG-003
Test Sequence:
TestResultConclusionDisconnect all loadCycling stops; output stable at 12VLoad-side fault (overload or short)Disconnect all loadCycling continuesPSU internal faultReconnect one camera at a timeCycling starts at specific cameraThat camera or its cable is faultyMeasure DC bus during cyclingStable 310V during both on/off phasesController/feedback issueMeasure DC bus during cyclingDroops during on-phaseBulk capacitor degraded
Conclusion Paths:

* Load fault: inspect camera wiring, test cameras individually
* Internal fault: proceed to MEAS-008 (C12 ESR), MEAS-007 (feedback), MEAS-005 (Schottky)

Related Chunks: SIG-003, MEAS-001, MEAS-006, MEAS-007, MEAS-008, FIELD-001

AMB-002: Differentiating OVP Activation vs. Feedback Failure
Symptom: Output drops suddenly to zero; power cycle restores briefly then drops again
TestResultInterpretationMeasure output before shutdown (fast scope)Voltage spikes to >13.2V then dropsOVP activated; feedback or optocoupler issueMeasure output before shutdownVoltage collapses without spikeOVP not involved; controller or supply failureMeasure TP3 (feedback ref) during operationReads 2.4–2.6VSecondary feedback sensing OKMeasure TP3Reads low or driftingSecondary feedback network faultyPower cycle, measure TP3 immediatelyCorrect then driftsOptocoupler thermal degradation
Related Chunks: SIG-005, SIG-003, MEAS-007, COMP-007, CAUS-003, SG-005

AMB-003: MOSFET Root Cause vs. Victim — Secondary Diode Verification
Situation: MOSFET tested as shorted (D-S < 10Ω); need to determine if MOSFET is root cause or victim of secondary Schottky short
Differentiation Logic:
MOSFET shorted found
    │
    └─► Test secondary Schottky (MEAS-005)
        │
        ├─► Schottky also shorted
        │   └─► Schottky is likely ROOT CAUSE; MOSFET is VICTIM
        │       └─► Replace Schottky + MOSFET + Fuse
        │           └─► Verify no other cascade damage (MEAS-010, transformer)
        │
        └─► Schottky tests normal
            └─► MOSFET failure may be primary
                └─► Still check: bulk cap ESR, snubber, gate drive resistor
                    └─► Consider: ESD event, overvoltage surge, thermal runaway

Probability: When both MOSFET and Schottky are failed, Schottky is root cause in ~70% of cases.
Related Chunks: COMP-001, COMP-004, MEAS-003, MEAS-005, CAUS-001, REP-001, REP-003, RM-001

SECTION 10: DIAGNOSTIC STRATEGIES (DS-*)

DS-001: Half-Split Strategy — DC Bus as Midpoint
Principle: The DC bus node sits at the natural functional midpoint of the SMPS power path. One measurement at this node divides the entire circuit into two roughly equal fault probability regions.
Circuit Midpoint:
[AC INPUT] → [BRIDGE] → [BULK CAP] → [DC BUS] → [MOSFET] → [TRANSFORMER] → [OUTPUT]
                                          ↑
                                    MEASUREMENT POINT
                                    Eliminates LEFT or RIGHT half

Application:

* If DC bus is present and correct → fault is in the right half (switching, transformer, output, feedback)
* If DC bus is absent or wrong → fault is in the left half (AC input, fuse, rectifier, bulk cap)

Why This Is Optimal First Test After Visual Inspection:
Despite being a higher-risk test (lethal voltage), the DC bus test has the highest diagnostic yield of any single measurement. Combined with the visual inspection (zero risk), these two tests together resolve the vast majority of failure cases.
When to Deviate: If visual inspection reveals an obviously blown component (e.g., exploded MOSFET, visibly blackened Schottky), proceed directly to that component test rather than DC bus first.
Related Chunks: MEAS-001, SG-001, SG-002, YD-001, TE-001

DS-002: Cascade Tracing Strategy — Work Backwards From Fuse
Principle: When a protection device (fuse) has operated, work backwards through the likely cascade chain to find the root cause, not just the most visible victim.
Cascade Tracing Template:
1. IDENTIFY SYMPTOM: Fuse blown
2. IDENTIFY IMMEDIATE CAUSE: What directly caused fuse to blow?
   → Answer: Hard short on DC bus
3. IDENTIFY COMPONENTS THAT COULD CREATE THIS SHORT:
   → MOSFET D-S, Bridge rectifier, Bulk capacitor
4. TEST IN PROBABILITY ORDER:
   → MOSFET first (60%), Bridge second (25%), Bulk cap third (10%)
5. WHEN FAILED COMPONENT FOUND, ASK: Why did this fail?
   → If MOSFET: Was it secondary Schottky that caused overload?
   → Test Schottky, snubber, bulk capacitor ESR
6. REPAIR ALL COMPONENTS IN CASCADE PATH
7. VERIFY REPAIR ELIMINATES ROOT CAUSE

Related Chunks: SIG-002, CAUS-001, COMP-001, COMP-004, MEAS-003, MEAS-005, RM-001

DS-003: Latent Failure Strategy — Post-Repair Stress Check
Principle: After repairing a confirmed fault, perform additional checks to identify components that were stressed by the fault but have not yet failed.
Latent Failure Checklist (post MOSFET replacement):
ComponentTestWhy CheckOutput SchottkyMEAS-005May have partial damage if it was root causeBulk capacitorMEAS-001 ripple checkHigh primary current may have stressed itSnubber componentsVisual + resistanceAbsorb MOSFET switching energy; may be degradedTransformerMEAS-010 ring testMay have shorted turns from over-current eventGate drive resistorResistance measurementCan be damaged by gate-source overvoltage
Stress Test After Repair:

1. First power-on through 60W incandescent bulb in series with AC (limits current if fault remains)
2. Monitor DC bus rise — should reach correct voltage smoothly
3. Check output voltage — should stabilize at 12V
4. Remove current limiter bulb, apply full load
5. Monitor temperature of MOSFET and U5 for 10 minutes

Related Chunks: REP-001, MEAS-003, MEAS-005, MEAS-010, RM-001, RM-002

SECTION 11: DIAGNOSTIC YIELD NOTES (YD-*)

YD-001: Diagnostic Yield Note — DC Bus Voltage Test
Applies To: MEAS-001, SG-001, SG-002
Yield Analysis:
TOTAL MAJOR FAULT LOCATIONS IN THIS SMPS: ~12 key components

DC Bus PRESENT eliminates: F1, bridge rectifier, bulk cap, AC input, EMI filter = 5 components
DC Bus ABSENT eliminates: MOSFET, U5, transformer, Schottky, C12, feedback = 6 components

YIELD (bus absent): 6/12 = 50%
YIELD (bus present): 5/12 = 42%
MINIMUM YIELD: 42% regardless of result

Measurement Cost: 30–60 seconds, basic multimeter
Risk: High (lethal voltage) — mitigated by proper probe technique and isolation awareness
Why Ordered After Visual: Visual inspection (zero risk) comes first; DC bus test provides maximum yield for acceptable risk second
Related Chunks: MEAS-001, SG-001, DS-001, TE-001

YD-002: Diagnostic Yield Note — Output Voltage Test
Applies To: MEAS-006, SG-004
Yield Analysis:
Output voltage test is the safest "first electrical test" because it is on the secondary (low-voltage) side. Even before DC bus test, this can reveal whether the PSU has any output at all.
OUTPUT PRESENT (any voltage) → Eliminates: total primary failure, fuse blow, bridge failure
OUTPUT ABSENT              → Narrows to: severe fault (primary, switching, or secondary)

YIELD: Medium (~30%) but achieved at zero safety risk on secondary side
EFFICIENCY: Highest efficiency test due to very low risk/time cost

Why Important: Many technicians skip this "obvious" test. Output voltage measurement provides quick confirmation that the fault is upstream (no output) or downstream (low/high output). This directs the entire subsequent diagnostic path.
Related Chunks: MEAS-006, SG-004, DS-001

YD-003: Diagnostic Yield Note — MOSFET D-S Resistance Test
Applies To: MEAS-003, COMP-001
Yield Analysis:
When symptom is SIG-002 (fuse blown), MOSFET D-S test is the highest-yield powered-off test:
MOSFET SHORTED (D-S <10Ω): 
  → Confirms major failure; directs to cascade tracing (CAUS-001)
  → Yield: ~60% probability correct → high yield for the symptom context

MOSFET NORMAL (D-S >100kΩ):
  → Eliminates MOSFET; directs to bridge rectifier or bulk cap
  → Eliminates ~60% of fuse-blow candidates

Cost: 1–2 minutes, powered-off, requires discharge confirmation
Risk: Low (powered off, discharged circuit)
Skill: Basic — multimeter in resistance mode
Related Chunks: MEAS-003, SIG-002, COMP-001, DS-002

SECTION 12: TIME ESTIMATES (TE-*)

TE-001: Time Estimate — Fast Triage Path (Dead Unit, Bench)
Goal: Reach a dominant root-cause bucket quickly for "completely dead" symptom
Target Time: 3–7 minutes (cover open, tools ready)
StepActionTime1Visual inspection — fuse, MOSFET, capacitors, burn marks1–2 min2Output voltage test (MEAS-006) — confirm zero output20 sec3Fuse continuity (MEAS-002) — check fuse before DC bus15 sec4DC bus measurement (MEAS-001) — half-split the circuit30–60 sec5aIf DC bus absent: MOSFET D-S test (MEAS-003)1–2 min5bIf DC bus present: check Vcc (MEAS-009)1–2 min6Decision: root cause bucket identified—
Decision Outcome: By end of this sequence, fault is localized to one subsystem with specific component probability ranking.
Related Chunks: SYS-001, DS-001, MEAS-001, MEAS-002, MEAS-003, MEAS-006, YD-001

TE-002: Time Estimate — Full Diagnostic Sequence (Output Degraded)
Goal: Fully diagnose degraded output (low/high/ripple)
Target Time: 15–25 minutes (oscilloscope preferred)
StepActionTime1Output voltage measurement (MEAS-006)30 sec2Feedback reference measurement (MEAS-007)30 sec3Output capacitor ESR test (MEAS-008)2–3 min4Output Schottky test (MEAS-005)1–2 min5DC bus voltage + ripple check (MEAS-001 with oscilloscope)2–3 min6Controller Vcc check (MEAS-009)1–2 min7Transformer ring test if needed (MEAS-010)5–10 min
Related Chunks: SYS-002, SUB-003, MEAS-005, MEAS-006, MEAS-007, MEAS-008

SECTION 13: VISUAL INDICATORS (VI-*)

VI-001: Visual Indicators — Primary MOSFET Catastrophic Failure
Applies To: COMP-001, SIG-002
IMG: IMG_REF_MOSFET_COMPONENT
Clues (Ranked by Reliability):

1. Definitive: Cracked, holed, or exploded MOSFET plastic package — component clearly destroyed
2. High Confidence: Carbon/soot trail from MOSFET toward heatsink or surrounding PCB area
3. Supporting: Adjacent gate resistor (small resistor near MOSFET gate pin) shows burn discoloration
4. Supporting: PCB trace discoloration around drain pad or snubber network area
5. Possible: Melted solder joints at MOSFET leads (excessive heat from fault current)
6. Secondary sign: Thermal compound between MOSFET and heatsink appears cracked or absent (from thermal shock)

Interpretation Rule: Visual damage to MOSFET strongly correlates with hard primary short. Still run MEAS-003 to confirm, and MEAS-005 to check Schottky (often the root cause of MOSFET destruction).
Related Chunks: COMP-001, MEAS-003, MEAS-005, SIG-002, CAUS-001

VI-002: Blown Fuse — Visual Identification
Applies To: MEAS-002, SIG-002
IMG: IMG_REF_BLOWN_FUSE
Identification Clues:

1. Definitive: Visible break in the fuse wire element (inspect with magnification or bright light through glass)
2. Definitive: Fuse element vaporized — dark/black deposit inside glass envelope
3. High Confidence: Black carbonized deposit on one end of glass envelope
4. Supporting: Slight discoloration or yellowing of normally clear glass
5. Note: A fuse can appear intact visually but still be open — always confirm with continuity test (MEAS-002)

Fuse Rating Identification: Note the fuse body markings (current rating in A, voltage rating, type T=slow/F=fast) before replacement. Replace only with identical rated fuse after root cause resolved.
Critical Rule: Never replace with higher-rated fuse. The fuse rating is calculated to protect the circuit. A higher-rated fuse may allow damage to propagate further.
Related Chunks: MEAS-002, SIG-002, SUB-001, REP-004

VI-003: Electrolytic Capacitor Failure — Visual Identification
Applies To: COMP-003, COMP-006
IMG: IMG_REF_SMALL_CAPS (bulk), IMG_REF_SECONDARY_ZONE (C12)
Failure Clues (Ranked by Severity/Reliability):

1. Definitive: Top of capacitor bulging outward — pressure relief vent has expanded; immediate replacement required
2. Definitive: Electrolyte leak — brown, dry, crystalline or sticky residue at top seam or base of capacitor
3. High Confidence: Capacitor body visibly swollen compared to new component
4. Supporting: Capacitor leaning at an angle (internal pressure causing mechanical deformation)
5. Supporting: Corrosion at lead entry points (electrolyte migration causes oxidation)
6. Note: A failing capacitor (high ESR) may show NO visual symptoms — ESR testing (MEAS-008) is required for definitive evaluation

Observation: On this specific board, look closely at the upper-left cluster of electrolytics (primary side bulk caps) and the large lower-right capacitor (C12, output). Both locations are common failure sites.
Related Chunks: COMP-003, COMP-006, MEAS-008, SIG-006

VI-004: Transformer Overheating — Visual Identification
Applies To: COMP-008
IMG: IMG_REF_TRANSFORMER
Failure Clues:

1. Definitive: Windings visibly charred or melted — overheating damage
2. High Confidence: Brown discoloration of varnish/potting compound on bobbin (normally yellow/cream)
3. High Confidence: Crack or split in ferrite core (physical damage from thermal stress)
4. Supporting: Strong smell of burnt varnish during/after operation
5. Supporting: PCB discoloration around transformer footprint
6. Supporting: Delamination or bubbling of insulation tape between winding layers

Note on This Board: The transformer uses a yellow/gold wound bobbin. Discoloration from this original yellow toward brown or black indicates thermal damage.
Related Chunks: COMP-008, MEAS-010, SIG-004, CAUS-001

VI-005: Output Schottky Diode Failure — Visual Identification
Applies To: COMP-004, CAUS-001
IMG: IMG_REF_SECONDARY_ZONE
Failure Clues:

1. Definitive: Cracked or shattered diode package (usually TO-220 or axial)
2. High Confidence: Burn mark on PCB under or near diode
3. Supporting: PCB trace discoloration leading to/from diode
4. Supporting: Discolored thermal compound if diode is mounted to heatsink
5. Note: Schottky diodes often fail with no visible sign — electrical testing (MEAS-005) is required

Related Chunks: COMP-004, MEAS-005, CAUS-001, SIG-002

SECTION 14: RECURRENCE RISK MATRICES (RM-*)

RM-001: Recurrence Risk Matrix — Fuse Blows Symptom
Symptom: SIG-002 — Fuse Blows Immediately on Power-Up
If you replace only...Recurrence RiskWhy it comes backFuse only95%+Hard short remains; immediate re-blowFuse + MOSFET (without checking Schottky)40–70%If Schottky was root cause, it will destroy new MOSFETFuse + MOSFET + Schottky (without ESR check)10–20%Degraded bulk cap may stress new MOSFET over weeksFuse + MOSFET + Schottky + bulk cap ESR verified5–10%Possible unidentified cascade componentFull root cause analysis + all cascade components<5%Comprehensive repair
Key Insight: Every component in the CAUS-001 cascade must be evaluated. The fuse is always a symptom.
Related Chunks: SIG-002, CAUS-001, COMP-001, COMP-004, REP-001, REP-003, REP-004

RM-002: Recurrence Risk Matrix — Low Output Voltage
Symptom: SIG-004 — Output Below 10.8V
If you replace only...Recurrence RiskWhy it comes backOutput capacitor C12 only50%If root cause is Schottky or feedback, C12 will fail againOutput Schottky diode only40%If C12 ESR caused overheating of Schottky, C12 must also be replacedC12 + Schottky15%Possible feedback network contributionC12 + Schottky + feedback verified<5%Comprehensive repair
Related Chunks: SIG-004, COMP-004, COMP-006, COMP-007, CAUS-005

RM-003: Recurrence Risk Matrix — Thermal Shutdown
Symptom: SIG-007 — Unit Shuts Down from Heat
If you address only...Recurrence RiskWhy it comes backVentilation improvement only60%If U5 is degraded and drawing more power, will still overheatU5 replacement without ventilation fix70%Same thermal conditions will degrade new U5Thermal compound replacement only75%Underlying heat generation not addressedVentilation + U5 replacement + thermal compound10%May have installation factorFull root cause (ventilation + component + load check)<5%Comprehensive
Related Chunks: SIG-007, COMP-005, FIELD-003

SECTION 15: PROBABILITY JUSTIFICATIONS (PJ-*)

PJ-001: Probability Justification — MOSFET is 60% Probable When Fuse Blows
Question: Why is MOSFET failure assigned 60% probability when the presenting symptom is a blown fuse?
Mechanistic Reasoning:
The probability is based on three compounding factors:
First, the MOSFET sustains the highest electrical stress of any single component in this PSU. It must block the full DC bus voltage (310V) during the off-state, and it switches at full primary current. Voltage spikes from transformer leakage inductance can push drain voltage to 500–600V even in a 310V bus design. Each switching cycle creates a brief avalanche event in the MOSFET body.
Second, the MOSFET's primary failure mode (Drain-Source short at ~70% probability within MOSFET failures) directly creates a DC bus short circuit, which is precisely the condition that blows a fuse. A MOSFET that fails open, by contrast, would not blow a fuse.
Third, empirical field data from SMPS repairs consistently shows MOSFET D-S short as the leading cause of fuse blows. The combination of "highest-stress component" and "failure mode that directly causes fuse blow" creates strong Bayesian probability that the MOSFET is either the root cause or an intermediate victim.
Contrast With Other Candidates:

* Bridge rectifier (25%): Lower stress due to lower switching frequency; typically fails from surge; less common than MOSFET
* Bulk capacitor (10%): Primarily fails high-ESR or open, not short; short-circuit failure requires specific overvoltage event
* Transformer (5%): Winding-to-winding short is rare; usually fails open or high-ESR

Conclusion: The 60% probability reflects the intersection of highest component stress AND failure mode that produces the observed symptom.
Related Chunks: SIG-002, COMP-001, MEAS-003, CAUS-001

PJ-002: Probability Justification — Output Capacitor Causes Excessive Ripple
Question: Why is C12 (output capacitor) assigned 50% probability for excessive ripple symptom?
Mechanistic Reasoning:
The output capacitor serves as the primary ripple filter. Its ESR directly multiplies the ripple current to produce ripple voltage. As ESR increases (the dominant failure mode at 50% of capacitor failures), ripple voltage increases proportionally.
The ripple current through C12 is driven by the switching frequency and load current. In a 12V/2A output PSU operating at 50–100kHz, the capacitor sees substantial ripple current continuously. Over thousands of hours, this causes electrolyte to heat and slowly evaporate, increasing ESR.
The 50% probability reflects both the high failure rate of electrolytic capacitors under continuous ripple stress and the direct causal relationship between ESR and the observed symptom. No other single component has this direct a relationship to ripple voltage.
Related Chunks: SIG-006, COMP-006, MEAS-008, CAUS-005

PJ-003: Probability Justification — Optocoupler Causes Overvoltage
Question: Why does optocoupler degradation cause output to rise rather than fall?
Mechanistic Reasoning:
The feedback control loop works as follows: when output voltage rises, the secondary-side TL431 reference draws more current through the optocoupler LED, which turns on the phototransistor more strongly on the primary side, which reduces the PWM duty cycle, which reduces the output voltage — a negative feedback loop.
When the optocoupler LED ages and loses efficiency (CTR decreases), the same output voltage produces less photocurrent, which means less phototransistor conduction, which the controller interprets as the output voltage being too low, so it increases duty cycle to compensate, driving the output higher.
This is a loss-of-feedback effect: the controller can no longer "see" the correct output voltage, and its best-effort compensation drives the output in the wrong direction (upward). The output rises until OVP triggers, causing the cycling behavior of AMB-002.
Related Chunks: SIG-005, COMP-007, CAUS-003, MEAS-007

SECTION 16: REPAIR PROCEDURES (REP-*)

REP-001: MOSFET Replacement Procedure
Applies To: COMP-001, SIG-002
IMG: IMG_REF_MOSFET_COMPONENT
⚠️ SAFETY:

* Disconnect AC power and wait minimum 5 minutes
* Verify DC bus voltage is <5V (MEAS-001) before any physical contact
* Use ESD wrist strap when handling replacement MOSFET
* Work on non-conductive surface

Prerequisites: Complete cascade analysis — verify Schottky diode (MEAS-005), verify no other shorted components, identify root cause before replacing MOSFET.
Required Tools: Temperature-controlled soldering iron (350°C), desoldering braid or vacuum pump, thermal compound (non-conductive), multimeter, ESD strap, replacement MOSFET (match original part number or approved equivalent with ≥ voltage rating, ≥ current rating, same package).
Repair Procedure:
StepActionVerification1Confirm DC bus discharged (<5V)Meter reading2Photograph/note MOSFET orientation before removalPhoto taken3Remove MOSFET: desolder all three leadsAll leads free from PCB4Clean pads with desoldering braidClean, flat copper pads, no bridges5Inspect PCB for damage from fault currentNo burnt traces; repair if found6Apply thin even layer of thermal compound to back of new MOSFETEven coverage, no air gaps7Install new MOSFET in correct orientationGate, Drain, Source matches original8Solder all three leadsGood solder fillet, no bridges9Trim leads flushNo excessive lead protrusion
Pre-Power-On Verification:
TestExpectedPass/FailG-S resistance>1MΩPass if >1MΩD-S resistance>100kΩPass if >100kΩVisual solder inspectionNo bridgesPass if clean
Root Cause Checklist (BEFORE powering on):

*  Secondary Schottky diode tested normal (MEAS-005) — root cause of MOSFET damage confirmed/resolved
*  Snubber network components measured (visual + resistance) — pass
*  Bulk capacitor ESR measured — acceptable (<0.5Ω)
*  Gate drive resistor measured — within spec
*  Fuse replaced with correct-rated device (REP-004)

Power-On Test Procedure:

1. Connect AC through 60W incandescent bulb in series (current limiter)
2. Apply AC; observe bulb briefly illuminating then dimming (normal startup)
3. Monitor DC bus voltage — should stabilize at 155V or 310V
4. Measure output voltage (MEAS-006) — should reach 11.4–12.6V
5. If stable, remove current limiter bulb
6. Apply rated load for 10 minutes; monitor MOSFET temperature

Related Chunks: COMP-001, MEAS-003, MEAS-005, CAUS-001, RM-001, DS-003, REP-003, REP-004

REP-002: Output Capacitor C12 Replacement Procedure
Applies To: COMP-006, SIG-006, SIG-004
IMG: IMG_REF_SECONDARY_ZONE
⚠️ SAFETY: Secondary side — lower voltage risk, but discharge C12 before desoldering (stored charge at 12–16V; minimal shock risk but prevents arcing during desoldering).
Replacement Specification: Match or exceed original capacitor: same capacitance (µF), same or higher voltage rating (V), same or lower ESR, same physical dimensions to fit PCB. Use 105°C-rated capacitor for improved longevity.
Repair Procedure:
StepAction1Discharge C12 (short terminals briefly with insulated probe)2Note polarity markings (negative stripe = negative lead)3Desolder both leads; remove capacitor4Clean pads5Install new capacitor with correct polarity6Solder leads; trim
Polarity Warning: Electrolytic capacitors are polarized. Incorrect installation (reverse polarity) causes immediate failure and possible rupture. The negative lead is marked with a stripe on the capacitor body; the PCB silkscreen shows the positive (+) pad.
Verification After Repair:

1. ESR test on new capacitor (MEAS-008) — should be <0.1Ω
2. Power on, measure output ripple — should be <100mVpp
3. Load test at rated current for 5 minutes

Related Chunks: COMP-006, MEAS-008, SIG-006, CAUS-005

REP-003: Output Schottky Diode Replacement Procedure
Applies To: COMP-004, CAUS-001
IMG: IMG_REF_SECONDARY_ZONE
⚠️ SAFETY: Secondary-side component. Discharge all capacitors (C12 and primary bulk caps) before working.
Critical Context: This repair is often performed in combination with MOSFET replacement (REP-001). The Schottky diode is frequently the root cause of MOSFET failure (CAUS-001). Always determine which failed first.
Replacement Specification: Replace with identical part or equivalent Schottky diode with: same or higher PIV (Peak Inverse Voltage) rating, same or higher average forward current rating, same package type (TO-220, TO-263, or axial as original), Schottky type (not standard rectifier).
Repair Procedure:
StepAction1Note diode orientation (cathode marking — band or "K" designation)2Desolder diode leads; remove3Clean pads4Install new diode with correct orientation5Solder; trim leads6If diode mounts to heatsink: apply new thermal compound
Verification:

1. Diode test (MEAS-005): forward voltage 0.15–0.45V; reverse OL
2. Power on; measure output voltage (MEAS-006): 11.4–12.6V
3. Load test: output stable under rated current

Related Chunks: COMP-004, MEAS-005, CAUS-001, REP-001, RM-001

REP-004: Fuse Replacement — Post Root-Cause Confirmation
Applies To: SIG-002, MEAS-002
IMG: IMG_REF_BLOWN_FUSE
⚠️ CRITICAL: This procedure must ONLY be performed after root cause has been identified and resolved. Replacing the fuse before root cause analysis results in 95%+ immediate re-blow (RM-001).
Pre-Replacement Checklist:

*  MOSFET D-S resistance measured > 100kΩ (MEAS-003) — no short
*  Bridge rectifier tests normal (MEAS-004) — all diodes OK
*  Output Schottky tests normal (MEAS-005) — no short
*  Root cause identified and component replaced (COMP-001 or COMP-004)
*  Replacement fuse rating confirmed matches original (current, voltage, type)

Fuse Rating Verification:
Never substitute a higher-rated fuse. The fuse rating is a designed protection value. Use ONLY the same: current rating (A), voltage rating (V), time-current characteristic (T=slow-blow, F=fast-blow, M=medium).
Replacement Procedure:

1. Remove blown fuse from holder
2. Verify new fuse rating matches removed fuse markings
3. Install new fuse in holder
4. Perform current-limited power-on test (60W bulb in series)
5. Confirm fuse does not blow on power-up
6. Remove current limiter; verify normal operation

If Fuse Blows Again After Replacement: The root cause was not fully resolved. Do not replace again — return to diagnostic sequence. A second fuse blow with a new MOSFET and new Schottky suggests bridge rectifier or bulk capacitor short (COMP-002, COMP-003).
Related Chunks: MEAS-002, SIG-002, RM-001, REP-001, REP-003, DS-002

IMAGE REFERENCE INDEX
Image IDDescriptionLocation on PCBRelated ChunksIMG_REF_BOARD_OVERVIEWFull board top-down view; SP-80M visible (inverted); complete component layoutEntire PCBSYS-001, VI-001 through VI-005IMG_REF_PRIMARY_ZONELeft half of PCB; high-voltage primary side with transformer, bridge area, bulk caps, MOSFETLeft/center PCB areaSUB-001, SUB-002, COMP-001, COMP-002, COMP-003IMG_REF_SECONDARY_ZONERight half of PCB; low-voltage secondary side with C12, Schottky, feedback components, terminalRight PCB areaSUB-003, COMP-004, COMP-006, COMP-007IMG_REF_TRANSFORMERLarge wound transformer component with yellow/gold bobbin (center-left PCB)Center-left PCBCOMP-008, MEAS-010, VI-004IMG_REF_SMALL_CAPSCluster of small electrolytic capacitors (upper-left area, primary side)Upper-left PCBCOMP-003, VI-003, MEAS-001IMG_REF_DC_BUS_TESTPOINTTest point at bulk capacitor positive terminal for DC bus measurementPrimary side, bulk capMEAS-001, SG-001, YD-001IMG_REF_BLOWN_FUSEFuse component location and visual identification referencePrimary side inputMEAS-002, SIG-002, VI-002, REP-004IMG_REF_MOSFET_COMPONENTPrimary MOSFET location; right-side board area, 3-terminal deviceRight edge, primary sideCOMP-001, MEAS-003, VI-001, REP-001IMG_REF_PWM_ICU5 PWM controller IC (8-pin DIP, lower-center board)Lower-center PCBCOMP-005, MEAS-009IMG_REF_OUTPUT_TERMINALGreen terminal block at top of board; AC/DC connection pointsTop edge PCBMEAS-006, FIELD-001IMG_REF_DEAD_UNITReference view of non-powered unit for baseline visualEntire boardSIG-001IMG_REF_THERMALThermal imaging reference zones on PCBMultiple locationsSIG-007, FIELD-003IMG_REF_CABLE_DROPCable connection at output terminalsTerminal block areaFIELD-001IMG_REF_HICCUP_MODEOscilloscope capture reference for cycling outputOutput terminal / scopeSIG-003IMG_REF_LOW_OUTPUTMeter reading reference for low output voltage conditionTP2 outputSIG-004IMG_REF_HIGH_OUTPUTMeter reading reference for overvoltage conditionTP2 outputSIG-005IMG_REF_RIPPLEOscilloscope waveform reference showing excessive rippleTP2 with AC couplingSIG-006

Document Version: 1.0
Generated: 2026-02-24
Equipment: CCTV-PSU-24W-V1 (PCB: SP-80M)
Image Source: CCTV Power Supply Unit.jpeg — PCB visual analysis included
Target System: ChromaDB RAG Vector Store
Total Chunks: 82 (SIG×7, SYS×3, SUB×3, MEAS×10, COMP×8, SG×5, CAUS×5, FIELD×3, AMB×3, DS×3, YD×3, TE×2, VI×5, RM×3, PJ×3, REP×4)