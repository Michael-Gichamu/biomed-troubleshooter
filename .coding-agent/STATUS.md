# Current Project Status

> Last updated: 2026-03-20
> This document reflects the actual current state of the codebase.

---

## Current Milestone

**Phase: Autonomous Stabilization Flow Complete**

The multimeter measurement flow has been refactored to:
- Eliminate manual "ready/next" confirmation after test-point guidance
- Implement MAD-based robust stabilization algorithm
- Enable autonomous sampling with dwell-time enforcement
- Return only stable readings to the agent
- Faster, less frustrating UX for engineers

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

### ✅ Autonomous Measurement (NEW!)
| Feature | Status | Notes |
|---------|--------|-------|
| MAD-based stabilization | Working | Uses Median Absolute Deviation for outlier rejection |
| Dwell-time enforcement | Working | Requires 3 consecutive stable samples |
| Integrated guidance + sampling | Working | Single tool call shows guidance then samples |
| No manual confirmation | Working | Removed "Reply next" prompts |
| Robust cluster detection | Working | Prefers newest stable readings |

### ✅ Image Handling
| Feature | Status | Notes |
|---------|--------|-------|
| URL-based images | Working | No base64 in LLM messages |
| Inline image rendering | Working | Markdown format: `![alt](url)` |
| GitHub RAW hosting | Working | Images served via github.com raw URLs |
| No local server needed | Working | Eliminated port 8000 dependency |

### ✅ Self-Healing LLM Infrastructure
| Feature | Status | Notes |
|---------|--------|-------|
| Multiple API keys | Working | [`src/infrastructure/llm_manager.py`](src/infrastructure/llm_manager.py) |
| Multiple fallback models | Working | Auto-rotation on failure |
| Exponential backoff | Working | 1s → 2s → 4s → 8s → 16s |
| Automatic key rotation | Working | Rotates through GROQ_API_KEYS |
| Automatic model rotation | Working | Falls back to next model if all keys fail |

---

## Known Blockers & Issues

### 🔴 High Priority

| Issue | Location | Description |
|-------|----------|-------------|
| None | - | All high priority issues resolved |

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

### Immediate

1. **Run the startup script**
   - Windows: `start.bat`
   - Unix/Mac: `./start.sh`
   - Starts LangGraph Studio (port 2024) - no local image server needed

### Short-term (Enhancements)

2. **Add more test scenarios**
   - File: [`data/mock_signals/`](data/mock_signals/)
   - Add undervoltage, short circuit scenarios

3. **Add equipment support**
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
# IMAGE_BASE_URL is now optional - images use GitHub RAW URLs
```

### Running the Project

```bash
# No Docker needed - ChromaDB runs in embedded mode
pip install -r requirements.txt

# Start LangGraph Studio
# Windows
start.bat

# Unix/Mac
./start.sh

# LangGraph Studio (port 2024)
langgraph dev --port 2024

# Mock mode (no hardware)
python -m src.interfaces.cli --mock

# USB mode (requires Mastech MS8250D multimeter)
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1
```

---

## Technical Debt

| Item | Description | Status |
|------|-------------|--------|
| Empty conversational routing | `route_from_analysis()` not implemented | Pending |
| Image handling via URLs | Refactored from base64 | ✅ Complete |
| Single equipment type | Only CCTV-PSU configured | Pending |
| No integration tests | Only unit tests for parser | Pending |

---

## What Works on a New Machine

If you clone this project on a new machine:

1. ✅ Python 3.10+ environment
2. ✅ `pip install -r requirements.txt`
3. ✅ Configure `.env` with API keys (use GROQ_API_KEYS for multiple keys)
4. ✅ Run `python -m src.interfaces.cli --mock` - works out of the box
5. ✅ ChromaDB embedded mode works automatically (no Docker)
6. ✅ Self-healing LLM with automatic key/model rotation
7. ✅ GitHub RAW URLs for images - no local server needed
8. ⚠️ USB mode requires Mastech MS8250D multimeter with CP210x adapter
9. ⚠️ LangGraph Studio requires `langgraph` CLI installed
