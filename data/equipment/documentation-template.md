# RAG-Optimized Diagnostic Documentation Template

**Purpose:** Template for creating equipment-specific diagnostic documentation for AI-powered troubleshooting agents (RAG retrieval).

**Instructions:** Replace all placeholders in brackets [] with equipment-specific values. Follow the section structure exactly for consistent RAG chunking.

---

## 1. Equipment Overview

Brief description of the equipment, its function, and key specifications.

**Key Specifications:**
- Input: [voltage range, frequency]
- Output: [voltage, current, power]
- Topology: [e.g., flyback, buck, linear, etc.]

**PCB Layout Zones:**
| Zone | Components | Voltage Level |
|------|------------|---------------|
| [Zone 1] | [Components] | [HIGH/LOW] |
| [Zone 2] | [Components] | [HIGH/LOW] |
| [Zone 3] | [Components] | [HIGH/LOW] |

---

## 2. Block Diagram Description

[Describe the high-level architecture - how the equipment processes signals/power from input to output]

**Example for SMPS:**
- Input conditioning → Conversion stage → Output filtering → Regulation loop

**Example for Biomedical Device:**
- Power input → Internal power supply → Signal acquisition → Signal processing → Display/Output

---

## 3. Power Flow

Describe the path energy/signals flow through the system.

```
[Input Stage] → [Stage 1] → [Stage 2] → [Stage 3] → [Output]
```

**Stage-by-Stage Description:**

1. **[Stage Name]:** [What happens here, key components]
2. **[Stage Name]:** [What happens here, key components]
3. **[Stage Name]:** [What happens here, key components]

---

## 4. Signals / Test Points Table

| Test Point | Location | Signal Type | Normal Value | Fault Threshold |
|------------|----------|-------------|--------------|-----------------|
| [TP1] | [Description] | [DC/AC/Resistance] | [Value] | [<min or >max] |
| [TP2] | [Description] | [DC/AC/Resistance] | [Value] | [<min or >max] |
| [TP3] | [Description] | [DC/AC/Resistance] | [Value] | [<min or >max] |
| [TP4] | [Description] | [DC/AC/Resistance] | [Value] | [<min or >max] |
| [TP5] | [Description] | [DC/AC/Resistance] | [Value] | [<min or >max] |

---

## 5. Expected Values

### Voltage Measurements
| Condition | TP1 | TP2 | TP3 | TP4 |
|-----------|-----|-----|-----|-----|
| Normal | [V] | [V] | [V] | [V] |
| No-load | [V] | [V] | [V] | [V] |
| Full-load | [V] | [V] | [V] | [V] |

### Resistance Measurements
| Component | Normal | Failed |
|-----------|--------|--------|
| [Component 1] | [Ω] | [<Ω or >Ω] |
| [Component 2] | [Ω] | [<Ω or >Ω] |

---

## 6. Threshold States

| Signal | Normal | Degraded | Fault | Missing |
|--------|--------|----------|-------|---------|
| [Signal 1] | [min-max] | [min-max] | [< or >] | [value] |
| [Signal 2] | [min-max] | [min-max] | [< or >] | [value] |

---

## 7. Fault Signatures

### SIG-001: [Fault Name]

**Observable:** [What the technician sees/hears]

**IF-THEN Reasoning:**
```
IF [condition 1] AND [condition 2]
    THEN [likely cause]

IF [condition 3] AND [condition 4]
    THEN [alternative cause]
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| [Component] | [%] | [Why it fails] |
| [Component] | [%] | [Why it fails] |

---

### SIG-002: [Fault Name]

**Observable:** [What the technician sees/hears]

**IF-THEN Reasoning:**
```
IF [condition] AND [condition]
    THEN [likely cause]
```

**Root Cause Candidates:**
| Cause | Probability | Mechanism |
|-------|-------------|-----------|
| [Component] | [%] | [Why it fails] |

---

### SIG-003: [Fault Name]

**Observable:** [What the technician sees/hears]

**IF-THEN Reasoning:**
```
IF [condition] AND [condition]
    THEN [likely cause]
```

---

## 8. Root Cause Table

| Fault Signature | Root Cause | Cascade Effect |
|-----------------|------------|----------------|
| [SIG-001] | [Component failed] | [What happens downstream] |
| [SIG-002] | [Component failed] | [What happens downstream] |
| [SIG-003] | [Component failed] | [What happens downstream] |

---

## 9. Diagnostic Strategy

### Primary Strategy: [Half-Split / Energy Flow / Binary Partition]

**Highest-Yield First Test:**
- Test: [test point or component]
- Why: [what it eliminates]
- Yield: [% of fault space eliminated]

**Strategy Selection Table:**
| If Symptom | Use Strategy |
|------------|--------------|
| [Symptom 1] | [Strategy name] |
| [Symptom 2] | [Strategy name] |

---

## 10. Troubleshooting Steps

### PATH A: [Primary Symptom Category]

```
STEP 1: [Test/Action]
    → IF [result] → proceed to STEP 2
    → IF [result] → proceed to STEP [X]

STEP 2: [Test/Action]
    → IF [result] → [conclusion]
    → IF [result] → [conclusion]

STEP 3: [Test/Action]
    → IF [result] → [conclusion]
```

### PATH B: [Secondary Symptom Category]

```
STEP 1: [Test/Action]
    → IF [result] → proceed to STEP 2
```

---

## 11. Repair Procedures

### REP-001: [Component] Replacement

**When to use:** [Specific fault signature]

**Procedure:**
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Verification:**
- [Test to confirm repair]
- [Expected result]

---

### REP-002: [Component] Replacement

**When to use:** [Specific fault signature]

**Procedure:**
1. [Step 1]
2. [Step 2]

---

## 12. Safety Warnings

⚠️ **DANGER: [Primary hazard]**

| Zone | Hazard | Mitigation |
|------|--------|------------|
| [Area 1] | [Voltage/risk] | [Safety measure] |
| [Area 2] | [Voltage/risk] | [Safety measure] |

**General Safety Rules:**
1. [Rule 1]
2. [Rule 2]
3. [Rule 3]

---

## 13. Images / Test Point Locations

**Image Reference Table:**
| Image | Description | Location | Test Points |
|-------|-------------|----------|-------------|
| [IMG-001] | [Description] | [PCB area] | [TP list] |
| [IMG-002] | [Description] | [PCB area] | [TP list] |

---

## 14. Notes for RAG Reasoning

**Key Diagnostic Relationships:**

```
IF [signal A] = [value] AND [signal B] = [value]
    THEN [fault conclusion]

IF [measurement] = [value]
    THEN [component] is [likely state]
```

**Common Diagnostic Patterns:**
- Pattern 1: [description with IF-THEN]
- Pattern 2: [description with IF-THEN]

**Questions This Documentation Helps Answer:**
- "If [TP] is [value] but [TP] is normal, what does that mean?"
- "If [output] is [value] but [input] exists, what failed?"
- "What component failure causes this signature?"
- "What repair should be performed?"
- "What should be checked next?"

---

## Quick Reference Decision Tree

```
[Primary Question]
├─► Yes → [Next Question/Answer]
│       ├─► [Condition] → [Result]
│       └─► [Condition] → [Result]
│
└─► No → [Next Question/Answer]
        ├─► [Condition] → [Result]
        └─► [Condition] → [Result]
```

---

**Template Version:** 1.0  
**Created:** [Date]  
**For Equipment:** [Equipment model/ID]
