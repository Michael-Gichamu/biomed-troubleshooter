# Biomedical Equipment Troubleshooting Agent - Scope Definition

> **Document Version:** 1.0  
> **Last Updated:** 2026-02-03  
> **Purpose:** Define the strict boundaries, responsibilities, and contracts for the LangGraph-based troubleshooting agent

---

## 1. Agent Responsibilities

The agent is responsible for:

### 1.1 Decision-Support Only
- Provide **recommendations** and **diagnostic guidance** to human technicians
- Explain the reasoning behind each recommendation in human-readable terms
- Present evidence (signal data, knowledge base citations) supporting each conclusion
- Suggest specific test points and expected measurements for verification

### 1.2 Structured Diagnostic Workflow
- Accept structured symptom descriptions from users
- Query the RAG knowledge base (ChromaDB) for relevant troubleshooting procedures
- Compare user-provided probe signals against known-good thresholds from the knowledge base
- Generate a ranked list of potential root causes with confidence scores
- Output a structured diagnosis with recommended next steps

### 1.3 Knowledge Base Interaction
- Retrieve relevant technical documentation based on symptom queries
- Extract failure mode patterns matching observed signals
- Return citations/references to source documents for human1.4 Scal verification

### ability Contract
- Operate identically regardless of the specific equipment in the knowledge base
- Never hardcode equipment-specific logic; all troubleshooting knowledge must flow through RAG
- Accept any equipment schema defined in the knowledge base without code changes

---

## 2. Agent Boundaries - What the Agent MUST NEVER Do

### 2.1 Autonomous Action Restrictions
- **NEVER** send control signals to any equipment
- **NEVER** modify equipment configuration or firmware
- **NEVER** execute repairs or component replacements
- **NEVER** bypass safety interlocks or overrides
- **NEVER** make clinical decisions affecting patient care

### 2.2 Scope Limitations
- **NEVER** diagnose equipment outside the defined knowledge base without explicit warning
- **NEVER** provide diagnosis with 100% confidence; always express uncertainty
- **NEVER** hallucinate technical specifications or signal thresholds
- **NEVER** ignore conflicting evidence between RAG knowledge and user-provided signals
- **NEVER** provide pricing, sourcing, or vendor recommendations

### 2.3 Communication Boundaries
- **NEVER** claim to replace human technician judgment
- **NEVER** provide diagnosis without at least one signal measurement or symptom report
- **NEVER** refuse to explain reasoning when asked by the user
- **NEVER** output unstructured or inconsistent response formats

### 2.4 Safety Requirements
- **NEVER** recommend procedures that violate equipment safety guidelines
- **NEVER** suggest measurements that could damage equipment or harm personnel
- **NEVER** proceed with diagnosis if user signals are outside defined safe ranges without warning

---

## 3. Inputs the Agent Consumes

### 3.1 User-Provided Information

| Input Type | Required | Format | Description |
|------------|----------|--------|-------------|
| **Equipment Identifier** | Yes | String | Model/serial number to select correct knowledge base |
| **Symptom Description** | Yes | Free text or structured | Observable problem reported by user |
| **Probe Signals** | Yes (for signal-based diagnosis) | Array of signal objects | Measured values from test points |
| **User Role** | No | Enum | `technician`, `engineer`, `student` (affects explanation detail) |

### 3.2 Probe Signal Schema

```typescript
interface ProbeSignal {
  test_point: string;      // e.g., "TP12 - Output Voltage"
  measurement_type: "voltage" | "current" | "resistance" | "power" | "frequency";
  measured_value: number;  // The actual measurement
  unit: string;            // e.g., "V", "A", "Ω", "W", "Hz"
  expected_range?: {       // Optional: user's expected range for comparison
    min: number;
    max: number;
  };
  timestamp: string;       // ISO 8601 when measurement was taken
  instrument?: string;     // e.g., "Fluke 87V", "Oscilloscope"
}
```

### 3.3 Knowledge Base Data (via RAG/ChromaDB)

The agent queries the RAG system for:
- Equipment technical manuals and service procedures
- Known failure modes and their signatures
- Signal threshold specifications (acceptable vs. failing ranges)
- Troubleshooting flowcharts and decision trees
- Component replacement procedures

---

## 4. Outputs the Agent Must Always Produce

### 4.1 Fixed Output Structure

Every agent response MUST conform to this JSON schema:

```typescript
interface AgentOutput {
  // Metadata
  version: "1.0";
  timestamp: string;                    // ISO 8601 UTC
  equipment_context: {
    model: string;
    serial?: string;
  };

  // Diagnosis results
  diagnosis: {
    primary_cause: string;              // Most likely root cause
    confidence_score: number;           // 0.0 - 1.0
    contributing_factors: string[];     // Secondary issues
    signal_evidence: {
      matching_signals: Array<{
        test_point: string;
        measured: number;
        expected: string;               // e.g., "12V ± 5%"
        deviation_percent: number;
      }>;
      conflicting_signals: Array<{      // Signals that don't match the diagnosis
        test_point: string;
        measured: number;
        expected: string;
        note: string;
      }>;
    };
  };

  // Recommendations
  recommendations: Array<{
    action: string;                     // e.g., "Replace C4 capacitor"
    priority: "critical" | "high" | "medium" | "low";
    verification_step: string;          // How to verify the fix worked
    warnings?: string[];
    estimated_difficulty: "easy" | "moderate" | "expert";
  }>;

  // Knowledge base citations
  citations: Array<{
    document_id: string;
    title: string;
    relevant_section: string;
    relevance_score: number;            // 0.0 - 1.0
  }>;

  // Reasoning explanation
  reasoning_chain: Array<{
    step: number;
    observation: string;
    inference: string;
    confidence_impact: "positive" | "negative" | "neutral";
  }>;

  // Confidence and limitations
  limitations: {
    missing_information: string[];      // What would improve diagnosis
    uncertainty_factors: string[];      // Why confidence is limited
    recommended_expert_review: boolean;
  };
}
```

### 4.2 Response Format Requirements

- **Consistency**: Every output MUST include all fields defined above
- **Confidence Expression**: Confidence scores MUST reflect genuine uncertainty; never output 1.0
- **Evidence-Based**: Every diagnosis MUST reference at least one signal measurement
- **Citation Requirement**: Every recommendation MUST have at least one RAG citation
- **Human Readability**: The `reasoning_chain` field MUST be understandable by a technician without AI expertise

---

## 5. Scalability Guidelines

The agent is designed to support **any equipment type** defined in the RAG knowledge base:

| Component | Scalable? | Mechanism |
|-----------|-----------|-----------|
| Equipment models | Yes | Add documents to ChromaDB; agent auto-detects |
| Signal types | Yes | Schema extensible via configuration |
| Troubleshooting procedures | Yes | RAG retrieval; no code changes |
| Component databases | Yes | Document-based; no schema migration |
| Agent logic | No | Core LangGraph workflow is fixed |

### 5.1 Adding New Equipment

To add a new equipment type:
1. Add technical documentation to `data/docs_raw/`
2. Process into structured format in `data/docs_structured/`
3. Ingest into ChromaDB (embeddings auto-generated)
4. Agent immediately supports the new equipment without code changes

### 5.2 Unsupported Equipment

If queried equipment is not in the knowledge base, the agent MUST:
1. Return `diagnosis.primary_cause` = "EQUIPMENT_NOT_IN_KNOWLEDGE_BASE"
2. Set `confidence_score` = 0.0
3. Populate `limitations.recommended_expert_review` = true
4. Provide generic troubleshooting guidance from a fallback knowledge base

---

## 6. Decision-Support Guarantee

This agent is explicitly **NOT** an autonomous system:

- All diagnosis outputs are recommendations, not instructions
- All repair actions require human technician execution
- All safety-critical decisions remain with qualified personnel
- The agent exists to augment human expertise, not replace it

The `recommendations` field in every output is advisory. Technicians MUST:
- Verify all signal measurements independently
- Apply their professional judgment to all recommendations
- Follow institutional safety protocols
- Escalate to human experts when confidence is low

---

## 7. Error Handling

| Condition | Agent Response |
|-----------|----------------|
| Invalid input schema | Return error with specific field violation |
| Equipment not found | Structured "not in knowledge base" output |
| Conflicting evidence | Explicitly report conflicts in `diagnosis.signal_evidence.conflicting_signals` |
| Low confidence (< 0.3) | Set `limitations.recommended_expert_review` = true |
| RAG query fails | Fallback to generic troubleshooting; warn user |

---

## 8. Compliance Notes

- All timestamps MUST use ISO 8601 UTC format
- All numerical values MUST include explicit units
- All diagnostic confidence MUST be expressed as 0.0 - 1.0 floats
- All citations MUST reference retrievable documents in the knowledge base
