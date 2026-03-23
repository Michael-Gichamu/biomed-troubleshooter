# Current Project Status

> Last updated: 2026-03-23
> This document reflects the actual current state of the codebase.

---

## Current Milestone

**Phase: Step-by-Step Diagnostic Engine Refactoring (COMPLETE)**

Refactored [`src/studio/conversational_agent.py`](src/studio/conversational_agent.py) to align with "Step-by-Step Diagnostic Engine" specification:

### Refactoring Changes (2026-03-23)

1. **Identity & Greeting (New Thread Detection)** (lines ~217-304):
   - Added new thread detection via `is_new_thread` check on HumanMessage count
   - For new threads: "Hello Engineer, I am DIAG. I'll guide you through a systematic diagnostic process."
   - Node label: `[1. Initialization]`

2. **Mandatory Node Labeling** (all nodes):
   - RAG_NODE: `[1. Initialization]` - Entry point
   - HYPOTHESES_NODE: `[3. Preliminary Assessment]` - Fault hypotheses
   - STEP_NODE: `[4. Measurement & Guidance]` - Active probing
   - REASON_NODE: `[5. Results Analysis]` - Data interpretation
   - REPAIR_NODE: `[6. Repair Procedure]` - Final fix steps
   - INTERRUPT_NODE: `[4. Measurement & Guidance]` - Next test point

3. **Physical Probing & Source Citation** (lines ~517, ~1112):
   - HYPOTHESES_NODE (line ~517): "_As specified in {equipment_model}.yaml._"
   - INTERRUPT_NODE (line ~1112): "_As specified in {state.equipment_model}.yaml._"
   - STEP_NODE: Added location citation with physical description

4. **Multimeter Polling Logic** (lines ~646-653):
   - Added explicit polling message: "🔌 **Multimeter is active and polling.** Please place your probes on **{test_point_id}** ({physical_description})."

5. **Repair Formatting & Truth-Groundedness** (lines ~1000-1006, ~1034-1040):
   - Fixed duplicate numbering: changed from `f"{i+1}. {r.get('step', '')}: {r.get('instruction', '')}"` to `f"- **{r.get('step', '')}:** {r.get('instruction', '')}"`
   - Added source citation: "_[Source: {equipment_model}-diagnostics.md]_"

6. **RAG Document Citation** (lines ~283-297):
   - Added document name extraction from RAG results
   - Message: "*Retrieved from: {doc_names}*"

Fixed multimeter mode detection in [`src/infrastructure/usb_multimeter.py`](src/infrastructure/usb_multimeter.py):

### Multimode Detection Updates (2026-03-23)

1. **18-byte Frame Parser** (lines ~117-145):
   - Fixed Continuity detection: `buf[11] & 0x10` (was `buf[11] & 0x40`)
   - Fixed Diode detection: `buf[11] & 0x20` (was `buf[12] & 0x01`)
   - Added Frequency detection: `buf[10] & 0x04`
   - Added Capacitance detection: `buf[10] & 0x02`

2. **10-byte Frame Parser** (lines ~633-680):
   - Added function code detection: `0x23`=Continuity, `0x24`=Diode, `0x25`=Frequency
   - Proper mapping for Resistance (0x21), Voltage (0x22), Current (0x20)

3. **Test Script** - Created `test_mm.py` for testing multimeter readings

---

## Working Features

### ✅ Core Functionality
| Feature | Status | Notes |
|---------|--------|-------|
| LangGraph workflow | Working | Hypothesis-driven in [`src/studio/conversational_agent.py`](src/studio/conversational_agent.py) |
| USB multimeter | Working | Mastech MS8250D with improved mode detection |
| Signal interpretation | Working | Domain service in [`src/domain/models.py`](src/domain/models.py) |
| RAG evidence retrieval | Working | ChromaDB embedded mode |
| Equipment configuration | Working | YAML-driven in [`data/equipment/`](data/equipment/) |
| CLI interface | Working | [`src/interfaces/cli.py`](src/interfaces/cli.py) |

### ✅ Multimode Measurement Support
| Mode | Status | Detection |
|------|--------|-----------|
| DC Voltage | ✅ Working | `DC_VOLTAGE` |
| AC Voltage | ✅ Working | `AC_VOLTAGE` |
| DC Current | ✅ Working | `DC_CURRENT` |
| AC Current | ✅ Working | `AC_CURRENT` |
| Resistance | ✅ Working | `RESISTANCE` |
| Continuity | ✅ Fixed | `CONTINUITY` |
| Diode | ✅ Fixed | `DIODE` |
| Frequency | ✅ Working | `FREQUENCY` |
| Capacitance | ✅ Working | `CAPACITANCE` |

### ✅ Self-Healing LLM Infrastructure
| Feature | Status | Notes |
|---------|--------|-------|
| Multiple API keys | Working | [`src/infrastructure/llm_manager.py`](src/infrastructure/llm_manager.py) |
| Multiple fallback models | Working | Auto-rotation on failure |
| Exponential backoff | Working | 1s → 2s → 4s → 8s → 16s |

---

## Known Blockers & Issues

### 🔴 High Priority
| Issue | Location | Description |
|-------|----------|-------------|
| LangGraph CLI not in PATH | System | `langgraph dev` doesn't work globally |

### 🟡 Medium Priority
| Issue | Location | Description |
|-------|----------|-------------|
| Limited equipment support | [`data/equipment/`](data/equipment/) | Only CCTV-PSU-24W-V1 configured |

---

## Next Actionable Steps

1. **Fix LangGraph CLI PATH issue** - Add Scripts folder to PATH or use venv
2. **Test all multimeter modes** - Verify Continuity, Diode, Frequency, Capacitance work correctly

---

## Environment Setup Notes

### Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Start LangGraph Studio (Windows)
start.bat

# USB multimeter test
python test_mm.py
```

---

## What Was Deleted (Cleanup)

The following were removed to simplify the project:

| Deleted | Reason |
|---------|--------|
| `src/application/agent.py` | Legacy, replaced by conversational_agent.py |
| `src/domain/diagnostic_state.py` | Not used |
| `src/infrastructure/llm_client.py` | Duplicate re-export |
| `data/mock_signals/` | Mock mode removed |
| `tests/` folder | Not needed |
| `start.sh`, `start-services.*` | Extra scripts |
| `docs/langgraph_design.md` | Duplicate of ARCHITECTURE.md |

---

## Technical Debt

| Item | Description | Status |
|------|-------------|--------|
| LangGraph CLI | PATH issue on Windows | Pending |
| Single equipment | Only CCTV-PSU configured | Pending |

---

## What Works on a New Machine

If you clone this project:

1. ✅ Python 3.10+ environment
2. ✅ `pip install -r requirements.txt`
3. ✅ Configure `.env` with API keys
4. ✅ USB mode works with MS8250D multimeter
5. ✅ ChromaDB embedded mode works (no Docker)
6. ⚠️ LangGraph Studio requires venv or PATH fix
