# Current Project Status

> Last updated: 2026-03-19
> This document reflects the actual current state of the codebase.

---

## Current Milestone

**Phase: Core Diagnostic Workflow Complete + Self-Healing Infrastructure**

The main LangGraph-based diagnostic workflow is functional with:
- Signal interpretation using equipment-specific thresholds
- RAG-powered evidence retrieval from ChromaDB (embedded mode)
- Fault analysis with LLM reasoning
- Recovery recommendation generation
- **NEW**: Self-healing LLM infrastructure with automatic key/model rotation

---

## Working Features

### ✅ Core Functionality
| Feature | Status | Notes |
|---------|--------|-------|
| LangGraph workflow | Working | 6-node pipeline in [`src/application/agent.py`](src/application/agent.py) |
| Mock signal mode | Working | JSON scenarios in [`data/mock_signals/`](data/mock_signals/) |
| USB multimeter | Working | Mastech MS8250D support in [`src/infrastructure/usb_multimeter.py`](src/infrastructure/usb_multimeter.py) |
| Signal interpretation | Working | Domain service in [`src/domain/models.py`](src/domain/models.py) |
| RAG evidence retrieval | Working | ChromaDB embedded mode in [`src/infrastructure/chromadb_client.py`](src/infrastructure/chromadb_client.py) |
| Equipment configuration | Working | YAML-driven thresholds/faults in [`data/equipment/`](data/equipment/) |
| CLI interface | Working | [`src/interfaces/cli.py`](src/interfaces/cli.py) |
| LangSmith tracing | Working | Full observability enabled |

### ✅ Self-Healing LLM Infrastructure (NEW!)
| Feature | Status | Notes |
|---------|--------|-------|
| Multiple API keys | Working | [`src/infrastructure/llm_manager.py`](src/infrastructure/llm_manager.py) |
| Multiple fallback models | Working | Auto-rotation on failure |
| Exponential backoff | Working | 1s → 2s → 4s → 8s → 16s |
| Error pattern detection | Working | LogParser detects 503, rate limits, timeouts |
| Automatic key rotation | Working | Rotates through GROQ_API_KEYS |
| Automatic model rotation | Working | Falls back to next model if all keys fail |

### ✅ Data & Configuration
| Feature | Status | Notes |
|---------|--------|-------|
| Equipment YAML schema | Working | [`data/equipment/cctv-psu-24w-v1.yaml`](data/equipment/cctv-psu-24w-v1.yaml) |
| Mock signal scenarios | Working | 4 scenarios: output_rail, overvoltage, ripple, thermal |
| Knowledge base | Working | RAG documents in [`data/knowledge/`](data/knowledge/) |
| ChromaDB (embedded) | Working | No Docker required - runs out of the box |

---

## Known Blockers & Issues

### 🔴 High Priority

| Issue | Location | Description |
|-------|----------|-------------|
| Empty function | [`src/application/conversational_agent.py:191`](src/application/conversational_agent.py:191) | `route_from_analysis()` is `pass` - routing logic not implemented |
| Incomplete image handling | [`src/studio/conversational_agent.py:395`](src/studio/conversational_agent.py:395) | Image data stripping logic is `pass` - needs implementation |

### 🟡 Medium Priority

| Issue | Location | Description |
|-------|----------|-------------|
| Limited equipment support | [`data/equipment/`](data/equipment/) | Only CCTV-PSU-24W-V1 configured |

### 🟢 Low Priority

| Issue | Location | Description |
|-------|----------|-------------|
| No tests for core workflow | [`tests/`](tests/) | Only parser tests exist |
| No CI/CD | N/A | Project not yet integrated with CI |

---

## Next Actionable Steps

### Immediate (Fix Blockers)

1. **Implement `route_from_analysis()` function**
   - File: [`src/application/conversational_agent.py`](src/application/conversational_agent.py:191)
   - Should route based on analysis results in state keys
   - Priority: High

2. **Implement image data stripping**
   - File: [`src/studio/conversational_agent.py`](src/studio/conversational_agent.py:395)
   - Optimize UI by stripping large image data after agent step
   - Priority: Medium

### Short-term (Enhancements)

3. **Add more test scenarios**
   - File: [`data/mock_signals/`](data/mock_signals/)
   - Add undervoltage, short circuit scenarios

4. **Add equipment support**
   - File: [`data/equipment/`](data/equipment/)
   - Create YAML for another equipment type

---

## Environment Setup Notes

### Required Environment Variables

Create `.env` from `.env.example`:

```
# Required
GROQ_API_KEYS=key1,key2,key3   # Multiple keys (auto-rotates)
LLM_MODELS=model1,model2       # Multiple models (fallback chain)
LANCHAIN_API_KEY=your_langchain_api_key
LANGSMITH_TRACING=true

# Optional (with defaults)
MAX_RETRIES_PER_KEY=2
MAX_RETRIES_PER_MODEL=2
BACKOFF_BASE_SECONDS=1.0
BACKOFF_MAX_SECONDS=16.0
```

### Running the Project

```bash
# No Docker needed - ChromaDB runs in embedded mode
pip install -r requirements.txt

# Mock mode (no hardware)
python -m src.interfaces.cli --mock

# USB mode (requires Mastech MS8250D multimeter)
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1

# LangGraph Studio (debugging)
langgraph dev --port 2024
```

---

## Technical Debt

| Item | Description | Impact |
|------|-------------|--------|
| Empty conversational routing | `route_from_analysis()` not implemented | Conversational agent can't route properly |
| Incomplete image handling | Large image data not stripped | Memory/UI performance issues |
| Single equipment type | Only CCTV-PSU configured | Limited use case |
| No integration tests | Only unit tests for parser | Risk of regressions |

---

## What Works on a New Machine

If you clone this project on a new machine:

1. ✅ Python 3.10+ environment
2. ✅ `pip install -r requirements.txt`
3. ✅ Configure `.env` with API keys (use GROQ_API_KEYS for multiple keys)
4. ✅ Run `python -m src.interfaces.cli --mock` - works out of the box
5. ✅ ChromaDB embedded mode works automatically (no Docker)
6. ✅ Self-healing LLM with automatic key/model rotation
7. ⚠️ USB mode requires Mastech MS8250D multimeter with CP210x adapter
8. ⚠️ LangGraph Studio requires `langgraph` CLI installed
