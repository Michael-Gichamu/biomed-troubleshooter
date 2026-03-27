# Diagnostic Documentation: CCTV-PSU-24W-V1

**Equipment:** CCTV Multi-Camera Power Supply -- 12V DC
**PCB Marking:** SP-80W
**Document Version:** 3.0
**Purpose:** RAG retrieval for AI-powered troubleshooting agent
**Target:** ChromaDB Vector Store

---

## 1. Equipment Overview

The CCTV-PSU-24W-V1 (PCB: SP-80W) is a flyback switched-mode power supply providing 12V DC output to multiple CCTV cameras simultaneously. It accepts universal AC input (100–240V) and uses a flyback converter topology with a ferrite-core transformer (TR1) providing galvanic isolation between the primary mains side and the secondary 12V output side.

**Key Specifications:**
- Input: 100–240V AC, 50/60Hz
- Output: 12V DC, multi-channel distribution
- Topology: Flyback converter with PWM control
- Input Fuse: T5A/250V (time-delay, 5 Ampere, 250 Volt)
- Primary Bulk Capacitor C1: Dongbaohe 450V 68μF 105°C
- PWM Controller U3: M5579P (8-pin DIP)
- Inrush Thermistor RT1: NTC 5D-11 (5Ω at 25°C)
- Output Schottky Rectifier D3: White-body TO-220
- Output Filter Capacitors: C8, C10, C14 (all 105°C grade)
- Upper Feedback Resistor R2: 240kΩ ±5%
- Lower Feedback Resistor R2A: ~62kΩ
- Feedback Reference: TL431 shunt regulator (2.495V internal reference)

**PCB Layout Zones:**

| Zone | Key Components | Voltage Level |
|------|----------------|---------------|
| Input section | F1 (T5A/250V), RT1 (NTC 5D-11), MOV varistor, CX1, CX2, MY1 | AC mains |
| Primary side | C1 (450V 68μF), Bridge rectifier, Q1 (MOSFET), U3 (M5579P), TR1 | HIGH -- ~310V DC |
| Secondary side | D3 (TO-220), C8, C10, C14, TL431, Optocoupler, R2, R2A | LOW -- 12V DC |
| Output terminals | J1 test point, amber multi-way screw terminal block | LOW -- 12V DC |

---

## 2. Power Flow

```
AC Mains Input (100–240V AC)
    ↓
MOV -- Surge suppressor (red disc varistor, input section)
    ↓
RT1 -- NTC 5D-11 inrush thermistor (limits startup inrush current)
    ↓
F1 -- T5A/250V time-delay fuse (sacrificial protection)
    ↓
EMI Filter -- CX1, CX2 (X-capacitors) + MY1 (Y-capacitor)
    ↓
Bridge Rectifier -- Full-wave diode bridge
    ↓
C1 -- Dongbaohe 450V 68μF 105°C (primary DC bus filter capacitor)
     DC bus = ~310V DC at 230VAC input
     DC bus = ~155V DC at 115VAC input
    ↓
Startup resistor → U3 (M5579P) VCC supply
    ↓
U3 -- M5579P PWM controller → Q1 gate drive at 50–100kHz
    ↓
Q1 -- Primary switching MOSFET (switches 310V through TR1 primary winding)
    ↓
TR1 -- Flyback transformer (energy stored during Q1 ON, transferred to secondary during Q1 OFF)
    ↓
D3 -- Output Schottky rectifier, white-body TO-220 (fast-recovery type required)
    ↓
C8 + C10 + C14 -- Output filter capacitors (105°C grade, three capacitors)
    ↓
12V DC Output → J1 test point → Amber output terminal block → Cameras
    ↓
R2 (240kΩ) + R2A (~62kΩ) voltage divider → TL431 REF pin (2.495V reference)
    ↓
TL431 → Optocoupler LED → Crosses isolation barrier → U3 feedback input
    ↓
U3 adjusts Q1 duty cycle to maintain 12V regulation
```

**Signal chain for diagnosis:**
```
ac_input → F1 → bridge → C1 (DC bus) → Q1 → TR1 → D3 → output_12v
                                                             ↑
                                        TL431 ← R2/R2A ← output_12v
                                           ↓
                                      Optocoupler → U3 (M5579P)
```

---

## 3. Component Locations and Probe Placement

### C1 -- Primary Bulk Capacitor (DC Bus Measurement Point)

**Component:** Dongbaohe 450V 68μF 105°C
**Location:** Primary side of board adjacent to TR1 (flyback transformer). This is the largest capacitor on the primary half and is rated 450V -- this rating is printed on the capacitor body. The positive polarity is marked on the PCB.

**⚠ LETHAL -- C1 stores approximately 310V DC. This charge is retained after AC is disconnected. Discharge procedure: connect a 10kΩ 2W resistor across C1 terminals for 30 seconds, then verify less than 10V with a meter before touching any primary-side component. CAT III 600V rated probes required.**

**Probe placement (live -- AC powered on):**
Set meter to DC Voltage, 750V range. RED probe on "+" terminal of C1. BLACK probe on C1 negative terminal or primary ground. Expected reading ~310V DC for 230VAC supply.

**Important:** C8, C10, and C14 are the secondary-side output filter capacitors rated approximately 16–25V and located on the output half of the board. They are completely different components from C1. Probing C8/C10/C14 when attempting to measure the DC bus will yield the 12V secondary voltage, not the primary bus voltage.

---

### J1 -- 12V Output Test Point

**Location:** Secondary/output side of board, adjacent to D3 (white TO-220 Schottky rectifier). Alternatively measure at the positive terminal of C8, C10, or C14, or the positive rail of the amber output screw terminal block. All of these points are at 12V DC -- safe to probe.

**Probe placement (live):**
Set meter to DC Voltage, 20V range. RED probe on J1. BLACK probe on output ground.

---

### F1 -- Input Fuse

**Rating:** T5A/250V -- time-delay (slow-blow), 5 Ampere, 250 Volt. This specification is marked on the PCB silkscreen.
**Location:** Input section of board near RT1 (NTC 5D-11) and CX1.

**⚠ Disconnect AC power completely before measuring fuse resistance.**

**Probe placement (power off):**
Set meter to resistance (Ω), lowest range. Probe across both fuse end-caps. Less than 0.1Ω = intact. OL = blown.

**Rule:** F1 blows as a consequence of a downstream short -- primarily Q1 drain-to-source failure. Never replace F1 before testing Q1. A shorted Q1 will blow a new fuse immediately on power-up. If Q1 is shorted, also test D3 before replacing anything -- a shorted D3 is frequently the root cause of Q1 failure.

---

### Q1 -- Primary Switching MOSFET

**Location:** Primary side of board adjacent to U3 (M5579P PWM controller) and TR1. Labeled Q1 on PCB.

**⚠ Discharge C1 before testing: 10kΩ 2W resistor across C1 terminals for 30 seconds. Verify less than 10V at C1 before proceeding.**

**Probe placement (power off, C1 discharged):**
Set meter to resistance (Ω). Measure drain-to-source in both probe orientations. Greater than 100kΩ in both directions = healthy. Less than 10Ω in both directions = shorted (failed). Also test in diode mode: body diode should show 0.5–0.7V forward, OL reverse.

---

### D3 -- Output Schottky Rectifier

**Package:** White-body TO-220, 3 pins. Labeled D3 on PCB. Located on the secondary/output side of board adjacent to J1 test point. D3 carries the full combined output current for all camera channels and has a heatsink for this reason.

**⚠ Power off only for diode testing.**

**Probe placement (power off):**
Set meter to DIODE TEST mode. RED probe on anode, BLACK probe on cathode (verify pin orientation from D3 part number datasheet). Healthy Schottky: 0.15–0.45V forward, OL reverse. Shorted: approximately 0V in both orientations. Open: OL in both orientations.

**Specification note:** D3 must be replaced only with a fast-recovery Schottky diode of equivalent or higher Vrrm and current rating. Standard silicon rectifier diodes (1N400x series) cannot operate at flyback switching frequencies and must not be used.

---

### U3 -- PWM Controller IC

**Part number:** M5579P (8-pin DIP). Labeled U3 on PCB primary side.
**Function:** Generates PWM drive signal to Q1 gate. Controls duty cycle based on feedback from optocoupler. Receives supply voltage from startup resistor circuit connected to C1 DC bus.

---

### RT1 -- Inrush Current Limiter

**Part number:** NTC 5D-11 (nominal 5Ω at 25°C, 11mm disc NTC thermistor).
**Location:** Input section adjacent to F1 and CX1.
**Function:** Limits inrush current surge at startup as C1 charges. RT1 resistance decreases as it heats up during normal operation. A failed-open RT1 prevents any current reaching the primary stage.

---

### MOV -- Surge Suppressor

**Type:** Metal oxide varistor, red disc body. Located in input section.
**Function:** Clamps voltage spikes on the AC mains input. A shorted MOV pulls the mains to near-zero and may appear as total power loss.

**Probe placement (power off, isolated):**
Resistance mode. A healthy MOV reads several MΩ in both directions. A shorted MOV reads less than 10Ω.

---

### C8, C10, C14 -- Output Filter Capacitors

**Grade:** 105°C rated (-40°C to +105°C operating range). Three capacitors on secondary/output side. Capacitance values: read from the top of each capacitor body.

**⚠ Power off. Discharge each capacitor individually (brief 100Ω resistor across leads) before any measurement.**

**Assessment method -- MASTECH MS8250D -- two steps, both required:**

**STEP 1 -- Visual inspection first (most reliable indicator):**
Examine the top of each capacitor. A healthy electrolytic has a flat or very slightly concave top with undeformed vent score lines.

Confirmed failure indicators -- replace the capacitor if any of these are present:
- **Bulging top:** Top surface is domed or rounded upward -- internal pressure has pushed the vent outward
- **Blown top:** Vent has actually opened -- body is cracked or split at the top, sometimes with brown residue
- **Leaked electrolyte:** Brown, crusty, or sticky residue around the base of the capacitor on the PCB
- **Burnt or discoloured sleeve:** Plastic sleeve has darkened, blistered, or shows burn marks
- **Discoloured PCB:** PCB area around the capacitor has turned dark brown or black

**STEP 2 -- Capacitance measurement (MS8250D, power off, one lead desoldered):**
Discharge the capacitor first. Desolder one lead to isolate from circuit -- in-circuit readings are unreliable. Set MS8250D to capacitance (F) position. Connect probes to capacitor leads. The MS8250D measures up to 66mF, which covers all capacitors on this board. Compare displayed reading to rated value on capacitor body.

| Reading vs Rated Value | Assessment | Action |
|------------------------|------------|--------|
| Within 20% of rated | Capacitance acceptable | Rely on visual inspection |
| 20–50% below rated | Capacitor degraded | Replace |
| More than 50% below rated | Capacitor severely failed | Replace immediately |
| Reads 0 or OL (open) | Capacitor dead -- open circuit | Replace immediately |
| Resistance mode reads <10Ω | Capacitor internally shorted | Replace immediately |

**Limitation to understand:** The MS8250D capacitance test measures at low frequency. It reliably detects a dead capacitor (open or severely reduced capacitance) and a shorted capacitor. However, a capacitor that has developed high internal resistance (high ESR) while retaining correct capacitance will pass this electrical test. In that case, a slightly bulging top is the primary physical sign -- if the symptom is output voltage droop under load or ripple and all electrical readings seem acceptable, replace the capacitors anyway. They are inexpensive and this is the most common failure mode on aged boards.

**Replacement specification:** Same capacitance (read from original body), same or higher voltage rating, low-ESR grade, 105°C minimum.

---

### R2 / R2A -- Output Voltage Setting Resistors

**R2:** 240kΩ ±5% (colour bands Red-Yellow-Yellow-Gold). Upper divider resistor. Labeled R2 on PCB.
**R2A:** Approximately 62kΩ (calculated). Lower divider resistor. Labeled R2A on PCB.
**Location:** Secondary side near TL431 shunt regulator.

**Regulation formula:** Vout = 2.495 × (1 + R2/R2A) = 12V → ratio R2/R2A ≈ 4.99
Verification: 2.495 × (1 + 240/62) = 2.495 × 4.87 ≈ 12.15V

**Probe placement (power off, one lead desoldered for accuracy):**
Resistance mode, appropriate range. R2 expected ~240kΩ. R2A expected ~62kΩ. Verify both values satisfy the formula above.

---

### TL431 -- Shunt Regulator (Feedback Reference)

**Location:** Secondary side, 3-pin TO-92 package near R2/R2A. Body marked "TL431" or "431".
**Internal reference voltage:** 2.495V (TI TL431 datasheet).

**Probe placement (live):**
Set meter to DC Voltage, 5V range. RED probe on TL431 REF pin. BLACK probe on output ground. Normal reading: 2.44–2.55V when feedback loop is actively regulating.

---

## 4. Test Points and Expected Values

| Signal ID | Component/Location | Parameter | Normal Value | Fault Threshold |
|-----------|-------------------|-----------|--------------|-----------------|
| bridge_output | C1 positive terminal (450V-rated) | DC Voltage | 280–340V (230V supply) | <250V or 0V = input fault |
| output_12v | J1 / C8/C10/C14 positive | DC Voltage | 11.4–12.6V no-load | <10.8V or >13.2V |
| feedback_ref | TL431 REF pin | DC Voltage | 2.44–2.55V | <2.2V or >2.6V |
| input_fuse | F1 across fuse body (power off) | Resistance | <0.1Ω | OL = blown |
| primary_mosfet | Q1 Drain–Source, both orientations (power off) | Resistance | >100kΩ | <10Ω = shorted |
| schottky_diode | D3 forward diode test (power off) | Diode voltage | 0.15–0.45V forward | <0.1V = shorted; OL = open |
| output_capacitor_esr | C8, C10, C14 -- visual inspection + MS8250D capacitance (one lead desoldered) | Visual + Capacitance | Flat top, capacitance within 20% of rated | Bulging/blown top; capacitance >20% below rated; reads shorted |
| feedback_resistor | R2 isolated (power off) | Resistance | ~240kΩ | OL = open, replace |

---

## 5. Signal Relationships and IF-THEN Logic

**Primary fault discrimination:**

```
IF output_12v = 0V AND ac_input = normal AND F1 = intact:

    MEASURE bridge_output (at C1 positive terminal, 750V DC range)

    IF bridge_output = 280–340V (230V supply):
        Primary input stage confirmed working.
        Fault is in Q1, U3 startup circuit, TR1, D3, or secondary.
        → Test Q1 D-S resistance (power off, C1 discharged)

    IF bridge_output = 0V:
        Primary input stage failure.
        → Test bridge rectifier diodes individually in diode test mode
        → Test MOV resistance (should be >1MΩ -- shorted MOV clamps mains)

    IF bridge_output = 140–175V:
        Normal reading for unit operating on 115VAC supply region.
        Not a fault.

    IF bridge_output = 50–200V (abnormally low for the supply voltage):
        C1 primary bulk capacitor (Dongbaohe 450V 68μF) degraded OR bridge partially failed.
        → Visually inspect C1 for bulging top. Test C1 capacitance with MS8250D (power off, FULLY discharge C1 first -- lethal stored voltage). Reading significantly below 68μF = degraded.
```

**Secondary fault discrimination when bridge_output = 280–340V, output_12v = 0V:**

```
TEST 1: Q1 drain-to-source resistance (power off, C1 discharged)
    IF Q1 D-S < 10Ω → Q1 shorted.
        Also test D3 -- shorted D3 frequently causes Q1 overstress and failure.
        Replace all shorted devices before replacing F1 or powering on.
    IF Q1 D-S > 100kΩ → Q1 healthy. Proceed to TEST 2.

TEST 2: D3 diode test (power off)
    IF D3 = OL in forward direction → D3 open. No secondary output path. Replace D3.
    IF D3 = ~0V in both orientations → D3 shorted. Root cause of Q1 damage.
        Replace both D3 and Q1.
    IF D3 = 0.15–0.45V forward, OL reverse → D3 healthy. Proceed to TEST 3.

TEST 3: Startup resistor continuity (power off)
    IF startup resistor = OL → U3 (M5579P) never receives VCC. No switching begins.
        Replace open startup resistor.

TEST 4: U3 VCC pin voltage (live measurement -- exercise full safety precautions)
    IF U3 VCC = 0V → Startup circuit failed or C1 not charged.
    IF U3 VCC = 10–25V → U3 has supply. Check gate drive signal to Q1.
    IF U3 VCC present and Q1 healthy → suspect TR1 winding fault or feedback startup loop.
```

**Output voltage fault discrimination:**

```
IF output_12v = low (8–11V) under rated load:
    INSPECT C8, C10, C14 visually first
        IF any cap has bulging top, blown top, or leaked electrolyte → Replace that capacitor.
    MEASURE capacitance of C8, C10, C14 with MS8250D (one lead desoldered, cap discharged)
        IF any capacitor reads more than 20% below its rated value → Replace that capacitor.
        IF any capacitor reads shorted in resistance mode (<10Ω) → Replace that capacitor.
    IF all caps pass visual and capacitance checks:
        MEASURE D3 forward voltage in diode mode
            IF Vf > 0.6V → D3 degraded, increased forward drop, replace D3.
        MEASURE feedback_ref at TL431 REF pin
            IF feedback_ref < 2.2V → R2/R2A divider values have changed.
        NOTE: If output droops under load but caps pass all tests, degraded cap ESR
        is still the most likely cause -- replace C8, C10, C14 as a set regardless.

IF output_12v > 13.2V:
    DISCONNECT ALL CAMERA LOADS IMMEDIATELY.
    MEASURE feedback_ref at TL431 REF pin
        IF feedback_ref ≈ 2.495V AND output still high
            → Optocoupler CTR has degraded.
              Less feedback signal crosses to U3.
              U3 increases duty cycle. Output climbs above setpoint.
              Replace optocoupler.
        IF feedback_ref > 2.6V
            → R2 (240kΩ) has failed open or drifted high.
              Measure R2 out-of-circuit.
              Replace with 240kΩ ±1% metal film resistor.

IF output_12v = cycling at 0.5–2Hz (hiccup mode):
    Disconnect all cameras and output loads.
        IF cycling stops → Connected load is drawing overcurrent.
          Inspect camera cables for short circuit. Disconnect cameras one at a time to identify fault.
        IF cycling continues → Internal PSU fault.
          Visually inspect and test capacitance of C8, C10, C14 with MS8250D.
          Test feedback network stability.
```

**Optocoupler CTR degradation mechanism:**
The optocoupler LED ages over time, causing the current transfer ratio (CTR) to decrease. Reduced CTR means less photocurrent reaches the primary side. U3 (M5579P) interprets this as the output being too low and increases Q1 duty cycle. Output voltage rises above the 12V regulation point. This is the most common cause of output overvoltage in aged units.

**D3-Q1-F1 cascade failure mechanism:**
D3 fails shorted → transformer TR1 secondary winding is effectively short-circuited → primary winding current spikes massively → Q1 experiences severe thermal stress → Q1 drain-to-source fails shorted → DC bus (310V from C1) is directly connected through shorted Q1 to transformer primary → very high current flows through bridge rectifier → F1 (T5A/250V) blows. In this sequence, D3 is the root cause, Q1 is a victim, and F1 is the sacrificial final protection.

---

## 6. Normal Operation

**Power-on sequence:**
1. RT1 (NTC 5D-11) limits inrush current as C1 charges from the bridge rectifier
2. C1 charges to ~310V DC (230V supply)
3. Startup resistor circuit provides initial VCC to U3 (M5579P)
4. U3 begins generating PWM drive signal -- Q1 starts switching at 50–100kHz
5. TR1 transfers energy to secondary on each Q1 off-cycle
6. D3 rectifies pulsed secondary output to DC
7. C8, C10, C14 filter the rectified output to clean DC
8. TL431 and optocoupler feedback loop closes -- output stabilises at 12V

**Steady-state indicators:**
- Output voltage stable at 11.4–12.6V under rated load
- No audible noise from TR1 -- squealing or whining indicates feedback instability or overload
- D3 (TO-220) and Q1 warm but not hot -- D3 case temperature less than 70°C at rated load
- Output ripple less than 50mV peak-to-peak

---

## 7. Fault Signatures

### SIG-001: Unit Completely Dead -- No Output, No Indicators

**Observable:** Zero output at J1, no LED illumination, silence on power-up.

**IF-THEN Reasoning:**
```
IF output_12v = 0V AND ac_input = 0V
    THEN check power cord and wall outlet -- fault is upstream of PSU

IF output_12v = 0V AND ac_input = normal AND F1 = blown
    THEN test Q1 D-S resistance before replacing F1
    THEN test D3 -- shorted D3 is common cascade root cause
    THEN replace all shorted semiconductors, then replace F1

IF output_12v = 0V AND ac_input = normal AND F1 = intact AND bridge_output = 0V
    THEN bridge rectifier has failed open
    THEN OR MOV has shorted -- test MOV resistance

IF output_12v = 0V AND ac_input = normal AND F1 = intact AND bridge_output = 280–340V
    THEN fault in Q1, startup circuit, D3, or U3
    THEN test Q1 D-S → test D3 → test startup resistor continuity
```

**Root cause candidates:**
| Cause | Estimated Probability | Mechanism |
|-------|-----------------------|-----------|
| Q1 D-S shorted | 30% | Cascade from D3 short, or independent thermal failure |
| D3 open | 25% | No secondary rectification path |
| Startup resistor open | 20% | U3 never receives VCC, no switching begins |
| Bridge rectifier open | 15% | No DC bus at C1 |
| U3 (M5579P) failed | 10% | No gate drive to Q1 |

---

### SIG-002: F1 (T5A/250V) Blows on Power-Up

**Observable:** F1 ruptures within seconds of AC connection.

**Root cause cascade:**
```
D3 shorted → TR1 secondary short → primary current spike
→ Q1 thermal overstress → Q1 D-S shorted → F1 (T5A/250V) blows
```

**Critical rule:** Never replace F1 without first testing Q1. If Q1 is shorted, a new T5A/250V fuse blows immediately. Always test D3 after finding a shorted Q1 -- D3 failure is the most common root cause.

**Required test sequence before replacing F1:**
1. Q1 D-S resistance -- less than 10Ω = shorted
2. D3 diode test -- approximately 0V both orientations = shorted
3. Bridge rectifier diodes -- any reading OL in forward direction = open diode
4. Replace all shorted semiconductors
5. Verify no shorts remain before installing new F1 (T5A/250V)

---

### SIG-003: Output Cycling / Hiccup Mode

**Observable:** Output pulses on and off at 0.5–2Hz rhythm.

**IF-THEN Reasoning:**
```
IF output cycles AND all loads disconnected → output becomes stable
    THEN connected load is causing overcurrent
    THEN disconnect cameras one by one to identify fault camera or cable

IF output cycles AND all loads disconnected → still cycles
    THEN internal PSU fault
    THEN visually inspect C8, C10, C14 for bulging tops and test capacitance with MS8250D
    THEN test feedback network for instability
```

**Root cause candidates:**
| Cause | Estimated Probability | Mechanism |
|-------|-----------------------|-----------|
| Load short or overload | 40% | OCP repeatedly triggering |
| C8/C10/C14 high ESR | 30% | Ripple triggers false overcurrent protection |
| Feedback instability | 20% | Loop oscillation |
| D3 partially degraded | 10% | Regulation instability |

---

### SIG-004: Low Output Voltage -- Below 10.8V Under Load

**Observable:** Output reads 8–11V under rated load; acceptable at no-load.

**IF-THEN Reasoning:**
```
IF output_12v = low under load AND output_12v = normal at no-load
    THEN load regulation failure
    THEN visually inspect C8, C10, C14 for bulging tops, then test capacitance with MS8250D (one lead desoldered) → replace any reading >20% below rated or showing bulging

IF output_12v = low at no-load as well AND feedback_ref = 2.44–2.55V
    THEN D3 forward voltage has increased (Schottky degradation)
    THEN measure D3 Vf -- if >0.6V, replace D3

IF output_12v = low AND feedback_ref < 2.2V
    THEN feedback divider R2/R2A has changed value
    THEN measure R2 and R2A out-of-circuit
```

**Root cause candidates:**
| Cause | Estimated Probability | Mechanism |
|-------|-----------------------|-----------|
| C8/C10/C14 high ESR | 45% | Voltage droop under load current |
| D3 degraded | 25% | Increased Vf reduces output |
| R2/R2A drifted | 20% | Altered regulation setpoint |
| TR1 degraded | 10% | Reduced energy transfer |

---

### SIG-005: High Output Voltage -- Above 13.2V

**Observable:** Output exceeds 13.2V. Risk of permanent damage to connected camera electronics.

**⚠ Disconnect all cameras and loads immediately before proceeding with diagnosis.**

**IF-THEN Reasoning:**
```
IF output_12v > 13.2V AND feedback_ref ≈ 2.495V
    THEN optocoupler CTR has degraded
    THEN replace optocoupler with same or equivalent part number

IF output_12v > 13.2V AND feedback_ref > 2.6V
    THEN R2 (240kΩ) has failed open or drifted significantly high
    THEN measure R2 resistance out-of-circuit
    THEN replace with 240kΩ ±1% metal film resistor
```

---

### SIG-006: Excessive Output Ripple or Noise

**Observable:** AC ripple on DC output causes camera interference or visible noise in image.

**IF-THEN Reasoning:**
```
IF ripple > 200mV peak-to-peak AND output_12v average = normal
    THEN C8/C10/C14 are degraded -- internal resistance increased
    THEN visually inspect C8, C10, C14 for bulging tops. Test capacitance with MS8250D (one lead desoldered). Replace any cap showing physical failure signs or reading >20% below rated value.

IF ripple present at 100Hz (twice mains frequency)
    THEN C1 (primary bulk capacitor 450V 68μF) degraded
    THEN visually inspect C1. Test capacitance with MS8250D (power off, fully discharge C1 first -- lethal stored voltage). Reading significantly below 68μF = degraded.
```

---

### SIG-007: Thermal Shutdown -- Works Cold, Fails After Warm-Up

**Observable:** Unit operates correctly from a cold start, shuts down after 5–30 minutes, recovers when cooled.

**IF-THEN Reasoning:**
```
IF fails when hot AND output current > rated maximum
    THEN overload condition -- reduce camera count or find short

IF fails when hot AND current within rating AND improves with added ventilation
    THEN inadequate airflow -- improve installation environment

IF fails when hot AND current within rating AND no improvement with ventilation
    THEN Q1 partially degraded -- higher RDS(on) causing excess heat generation
    THEN OR D3 thermal interface degraded -- poor contact to heatsink
```

---

## 8. Diagnostic Strategy

### Primary Strategy: Half-Split at DC Bus (C1)

Measuring the DC bus voltage at C1 is the single highest-information-value first test. One measurement eliminates approximately 50% of all possible fault locations by determining whether the fault is in the primary input section or the switching/secondary section.

```
DC bus at C1 = 280–340V?
    │
    ├─► YES → Primary input stage is working
    │         Fault is in: Q1, startup circuit, U3, TR1, D3, or secondary
    │         Eliminates: AC input, F1, MOV, RT1, bridge rectifier, C1
    │
    └─► NO → Primary input stage has failed
              Fault is in: bridge rectifier, MOV, C1, or F1
              Eliminates: Q1, U3, TR1, D3, secondary stage
```

### Strategy by Symptom

| Symptom | First Test | Recommended Strategy |
|---------|------------|----------------------|
| Dead unit (SIG-001) | C1 DC bus voltage | Half-split at DC bus |
| F1 blown (SIG-002) | Q1 D-S resistance | Cascade trace: Q1 → D3 → F1 |
| Low output (SIG-004) | C8/C10/C14 visual + capacitance | Feedback trace: visual → capacitance test → D3 Vf → divider |
| High output (SIG-005) | TL431 REF pin | Feedback trace: REF → optocoupler → R2 |
| Hiccup (SIG-003) | Load disconnect test | Load isolation first |
| Ripple (SIG-006) | C8/C10/C14 visual + capacitance | Visually inspect then test capacitance with MS8250D |
| Thermal (SIG-007) | Output current measurement | Thermal profiling |

---

## 9. Step-by-Step Troubleshooting Paths

### PATH A: Dead Unit (No Output at J1)

```
STEP 1: Visual inspection
    → Check for burnt components, bulging capacitors, discoloured PCB
    → F1 may be visually blown (blackened or broken wire visible)

STEP 2: Confirm AC input (200–250V AC at input connector)
    → 0V = upstream fault (cord, outlet, breaker) -- not a PSU fault

STEP 3: Test F1 continuity (power off)
    → <0.1Ω = intact → go to STEP 4
    → OL = blown → go to STEP 3A before replacing

    STEP 3A -- F1 blown, before replacing:
        Test Q1 D-S resistance (power off, C1 discharged)
        Test D3 diode test (power off)
        Replace all shorted semiconductors found
        Then replace F1 (T5A/250V only)

STEP 4: Measure DC bus at C1 (live -- 310V lethal, full precautions)
    → 280–340V = primary working → go to STEP 5
    → 0V = primary failure → test bridge diodes, test MOV resistance

STEP 5: Test Q1 D-S resistance (power off, C1 discharged)
    → <10Ω = Q1 shorted → also test D3 → replace all shorted parts → retest
    → >100kΩ = Q1 healthy → go to STEP 6

STEP 6: Test D3 diode test (power off)
    → OL forward = D3 open → replace D3 (fast-recovery Schottky, same ratings)
    → Normal → go to STEP 7

STEP 7: Test startup resistor continuity (power off, C1 discharged)
    → OL = open startup resistor → U3 never starts → replace startup resistor
    → Intact → test U3 VCC pin voltage (live, advanced)
```

### PATH B: Degraded Output

```
STEP 1: Measure output_12v at J1 under rated load
    → <10.8V → PATH B1 (low output)
    → >13.2V → PATH B2 (high output) -- DISCONNECT ALL LOADS FIRST
    → 11.4–12.6V but high ripple → PATH B3 (ripple)

PATH B1 -- Low Output:
    STEP 1a: Visually inspect C8, C10, C14 (power off). Look for bulging or blown top, leaked electrolyte.
        → Any physical failure sign → replace that capacitor with low-ESR 105°C grade
    STEP 1b: Test capacitance with MS8250D (one lead desoldered, discharged)
        → Reading >20% below rated value → replace
        → Reads shorted in resistance mode (<10Ω) → replace
    STEP 1b: If all caps pass visual inspection and capacitance test -- measure TL431 REF pin (live)
        → REF = 2.44–2.55V → test D3 forward voltage (power off)
          D3 Vf > 0.6V → D3 degraded → replace D3
        → REF < 2.2V → R2 or R2A value has changed → measure both out-of-circuit

PATH B2 -- High Output (loads disconnected):
    STEP 2a: Measure TL431 REF pin (live)
        → REF ≈ 2.495V → optocoupler CTR degraded → replace optocoupler
        → REF > 2.6V → R2 (240kΩ) open or drifted → measure R2 out-of-circuit
                        Replace with 240kΩ ±1% metal film

PATH B3 -- Excessive Ripple:
    STEP 3a: Visually inspect C8, C10, C14 (power off). Look for bulging top, leaked electrolyte.
        → Physical failure sign → replace that capacitor
    STEP 3b: Test capacitance of C8, C10, C14 with MS8250D (one lead desoldered, discharged)
        → Reading >20% below rated → replace
    STEP 3c: If all output caps pass -- visually inspect C1 (450V 68μF, power off, DISCHARGE FIRST)
        → Bulging top or capacitance significantly below 68μF → replace with 450V 68μF 105°C
```

---

## 10. Repair Procedures

### REP-001: Primary MOSFET Q1 Replacement

**Prerequisites:** Identify and replace D3 if also shorted -- do not replace Q1 alone if D3 caused the failure, or Q1 will fail again.

**Procedure:**
1. Disconnect AC. Discharge C1 (10kΩ 2W resistor for 30 seconds). Verify less than 10V at C1.
2. Note Q1 pin orientation (Gate, Drain, Source) from PCB silkscreen or part datasheet.
3. Desolder all three Q1 leads.
4. Clean pads with desoldering braid.
5. Install replacement Q1 in correct orientation.
6. Solder all leads. Confirm no solder bridges.
7. Before power-on verify: Q1 G-S > 1MΩ, Q1 D-S > 100kΩ.

**Safe first power-on:** Connect a 60W incandescent bulb in series with the AC supply as a current limiter. Bulb flashes briefly then dims = correct startup and regulation. Bulb stays continuously bright = short still present, disconnect immediately.

---

### REP-002: Output Schottky D3 Replacement

**Prerequisites:** Confirm D3 failure by diode test. If D3 was shorted, also inspect and test Q1.

**Procedure:**
1. Disconnect AC. Discharge C8, C10, C14 (100Ω resistor briefly across each).
2. Note D3 anode/cathode orientation from PCB or datasheet.
3. Desolder D3. Clean pads.
4. Install replacement -- fast-recovery Schottky type, same or higher Vrrm and rated current. Do not use 1N400x or any standard silicon rectifier.
5. Test replacement with diode meter before powering on: 0.15–0.45V forward, OL reverse.

---

### REP-003: Output Capacitor Replacement (C8, C10, or C14)

**Procedure:**
1. Disconnect AC. Discharge the capacitor to be replaced (100Ω resistor briefly).
2. Note polarity (negative stripe on capacitor sleeve, marked – on PCB).
3. Desolder both leads. Clean pads.
4. Install replacement with correct polarity.
5. Specification: Same capacitance (read from original body), same or higher voltage rating, low-ESR, 105°C grade.

---

### REP-004: Feedback Resistor R2 Replacement

**Symptom addressed:** Output overvoltage (>13.2V) with TL431 REF pin above 2.6V.

**Procedure:**
1. Disconnect AC.
2. Desolder one end of R2 for accurate isolated measurement.
3. Measure R2. Expected ~240kΩ. OL = open (failed).
4. Replace with 240kΩ ±1% metal film resistor.
5. After repair, verify output = 11.4–12.6V with cameras reconnected.

---

## 11. Safety

⚠️ **DANGER: Lethal voltages are present on the primary side of this board at all times when AC is connected, and for a period after disconnection due to stored charge in C1.**

| Location | Voltage | Hazard |
|----------|---------|--------|
| AC input terminals, F1, MOV | 100–240V AC | Lethal AC shock |
| C1 positive terminal (450V 68μF) | ~310V DC stored | Lethal even after AC disconnect |
| Q1 drain pin | ~310V DC switched | Lethal |
| TR1 primary winding | Switched 310V DC | Lethal |

**Safety rules:**
1. Disconnect AC power before performing any resistance or component measurements
2. Discharge C1 (450V 68μF) via 10kΩ 2W resistor across C1 terminals for 30 seconds after AC disconnect
3. Verify less than 10V at C1 with a meter before touching any primary-side component
4. During live high-voltage measurements, keep one hand away from the board
5. Use probes rated CAT III 600V minimum for all primary-side measurements
6. Replace F1 only with T5A/250V time-delay fuse -- no substitution
7. Never replace F1 without first confirming Q1 D-S resistance is greater than 100kΩ
8. Disconnect all camera loads before investigating any overvoltage condition (output >13.2V)

---

## 12. Common Failure Modes

| Rank | Component | Label | Failure Mode | Fault Signature | Frequency |
|------|-----------|-------|--------------|-----------------|-----------|
| 1 | Primary MOSFET | Q1 | D-S short | Dead unit, F1 blown | 30% |
| 2 | Output Schottky | D3 | Short or open | Dead unit or Q1 cascade | 25% |
| 3 | Output capacitors | C8/C10/C14 | High ESR | Low voltage under load, ripple | 20% |
| 4 | Startup circuit | R25 area | Open | Dead unit, F1 and Q1 intact | 10% |
| 5 | Bridge rectifier | -- | Diode open | Dead unit, F1 intact | 5% |
| 6 | PWM controller | U3 (M5579P) | Failed | Dead unit | 5% |
| 7 | Optocoupler | -- | CTR degraded | Output overvoltage | 3% |
| 8 | Feedback resistor | R2 | Open | Output overvoltage | 2% |

---

## 13. Measurement Interpretation Guide

### DC Bus Voltage (C1 Positive Terminal)

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| 280–340V | Normal, 230V supply | Fault is in switching or secondary section |
| 140–175V | Normal, 115V supply | Fault is in switching or secondary section |
| 0V | Primary input failure | Test bridge diodes, test MOV, test F1 |
| 50–250V (abnormally low) | C1 degraded or bridge partial failure | Visually inspect C1; test C1 capacitance with MS8250D (fully discharge first); test bridge diodes |

### 12V Output Voltage (J1 Test Point)

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| 11.4–12.6V | Normal | Check load and cables |
| 10.8–11.4V | Marginally low | Visually inspect C8/C10/C14, test capacitance with MS8250D |
| <10.8V | Under-voltage | Visually inspect C8/C10/C14, test capacitance, test D3, check feedback |
| 12.6–13.2V | Marginally high | Test TL431 REF pin, check optocoupler |
| >13.2V | Overvoltage -- disconnect loads immediately | Test TL431 REF, measure R2 |
| 0V | No output | Measure DC bus at C1 first |

### TL431 REF Pin (Feedback Reference)

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| 2.44–2.55V | Normal | Optocoupler if output is high; D3 Vf if output is low |
| <2.2V | Low reference | Measure R2/R2A values out-of-circuit |
| >2.6V | High reference | R2 (240kΩ) open or drifted -- measure R2 |
| 0V | No reference | Secondary dead -- check D3, output capacitors |

### Q1 Drain-to-Source Resistance

| Reading | Interpretation | Next Action |
|---------|----------------|-------------|
| >100kΩ both orientations | Healthy | Check startup circuit, D3, U3 |
| <10Ω both orientations | Shorted -- Q1 failed | Replace Q1, also test D3 |
| 0.5–0.7V one direction (diode mode) | Normal body diode | Q1 is healthy |

### Output Capacitor Assessment (C8, C10, C14) -- MASTECH MS8250D

**Visual inspection first:**
| Physical Sign | Assessment | Action |
|---------------|------------|--------|
| Flat top, clean base | Healthy | Proceed to capacitance test |
| Top slightly domed or rounded | Degraded -- internal pressure building | Replace |
| Top visibly bulging or cracked open | Failed | Replace immediately |
| Brown residue at base | Leaked electrolyte -- failed | Replace immediately |
| Darkened or blistered sleeve | Thermal damage | Replace immediately |

**Capacitance measurement (MS8250D, one lead desoldered, cap discharged):**
| Reading vs Rated Value | Assessment | Action |
|------------------------|------------|--------|
| Within 20% of rated | Capacitance acceptable | Rely on visual inspection |
| 20–50% below rated | Capacitor degraded | Replace |
| >50% below rated | Capacitor severely failed | Replace immediately |
| Reads 0 or OL | Dead -- open circuit | Replace immediately |
| Resistance mode <10Ω | Internally shorted | Replace immediately |

---

## Quick Reference Decision Tree

```
Output = 0V?
├─► Yes
│   ├─► F1 blown?
│   │   ├─► Yes → Test Q1 D-S and D3 → replace shorted parts → replace F1 (T5A/250V)
│   │   └─► No → Measure C1 DC bus (LETHAL -- full precautions)
│   │           ├─► 280–340V → Test Q1, D3, startup circuit, U3 (M5579P)
│   │           └─► 0V → Test bridge rectifier diodes, test MOV resistance
│
├─► Output low (<10.8V under load)
│   └─► Visually inspect + capacitance test C8/C10/C14 (MS8250D) → Test D3 Vf → Test R2/R2A
│
├─► Output high (>13.2V) → DISCONNECT ALL CAMERAS FIRST
│   └─► Test TL431 REF pin
│       ├─► ≈2.495V → Replace optocoupler
│       └─► >2.6V → Measure R2 (240kΩ expected) → replace if open/drifted
│
├─► Output cycling (hiccup)
│   └─► Disconnect all cameras → still cycles: visually inspect + capacitance test C8/C10/C14
│
└─► Excessive ripple
    └─► Visually inspect + capacitance test C8/C10/C14 → visually inspect + capacitance test C1 (fully discharge first)
```

---

**Document Version:** 3.0
**Equipment:** CCTV-PSU-24W-V1 (PCB: SP-80W)
**Target System:** ChromaDB RAG Vector Store