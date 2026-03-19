# AI Agent Entry Point - Project Memory System

> **IMPORTANT**: This is the primary entry point for ANY AI agent working on this project. Start here before making any changes.

---

## Quick Status Snapshot

| Item | Status |
|------|--------|
| **Project Type** | LangGraph-powered AI troubleshooting agent |
| **Core Functionality** | Automated equipment diagnostics for CCTV Power Supply Units |
| **Working Modes** | Mock (simulation) and USB (real hardware via Mastech MS8250D) |
| **Primary LLM** | Groq (Llama 3.3 70B) |
| **Vector DB** | ChromaDB (embedded mode - no Docker required) |
| **Current State** | Core diagnostic workflow functional; some conversational agent routing incomplete |

---

## Documentation Structure

```
.coding-agent/
├── AGENTS.md         ← YOU ARE HERE (entry point)
├── STATUS.md         ← Current state, blockers, next steps
├── SPEC.md           ← Product-level understanding
├── ARCHITECTURE.md   ← Technical implementation details
└── sessions/         ← Session history (for future use)
```

---

## For Any New AI Agent

### First Steps

1. **Read this file** (AGENTS.md) - You're here ✓
2. **Check [STATUS.md](.coding-agent/STATUS.md)** - Understand current state and blockers
3. **Review [SPEC.md](.coding-agent/SPEC.md)** - Understand what this project is trying to achieve
4. **Study [ARCHITECTURE.md](.coding-agent/ARCHITECTURE.md)** - Understand how the system works

### Starting Development

Before making any code changes:

```bash
# Ensure working directory is up to date
git pull

# Review environment setup
cp .env.example .env
# Edit .env with your API keys (GROQ_API_KEY, LANGCHAIN_API_KEY, etc.)

# Install dependencies
pip install -r requirements.txt

# Run in mock mode (no hardware needed)
python -m src.interfaces.cli --mock

# Or run in USB mode (requires Mastech MS8250D multimeter)
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1

# Or use LangGraph Studio for debugging
langgraph dev --port 2024
```

### Key Files Reference

| Purpose | File |
|---------|------|
| Main diagnostic workflow | [`src/studio/conversational_agent.py`](src/studio/conversational_agent.py) |
| Domain models & services | [`src/domain/models.py`](src/domain/models.py) |
| Equipment configuration | [`data/equipment/cctv-psu-24w-v1.yaml`](data/equipment/cctv-psu-24w-v1.yaml) |
| CLI interface | [`src/interfaces/cli.py`](src/interfaces/cli.py) |
| Infrastructure config | [`src/infrastructure/config.py`](src/infrastructure/config.py) |
| ChromaDB client | [`src/infrastructure/chromadb_client.py`](src/infrastructure/chromadb_client.py) |

---

## Mode-Specific Guidance

### For Debugging Issues
1. Check [STATUS.md](.coding-agent/STATUS.md) for known issues
2. Enable LangSmith tracing in `.env` for full observability
3. Use mock mode to reproduce issues without hardware

### For Adding New Features
1. Review [SPEC.md](.coding-agent/SPEC.md) to ensure alignment with project goals
2. Study [ARCHITECTURE.md](.coding-agent/ARCHITECTURE.md) to understand where the feature fits
3. Add equipment-specific logic in YAML config (not hardcoded)

### For Fixing Bugs
1. Run tests: `pytest tests/`
2. Use mock scenarios: `python -m src.interfaces.cli --mock --scenario cctv-psu-overvoltage`
3. Check LangSmith traces for decision debugging

---

## Design Philosophy

This project follows **data-driven architecture**:

- **No equipment-specific code**: All thresholds, faults, and recovery steps come from YAML files in [`data/equipment/`](data/equipment/)
- **Hybrid intelligence**: Combines deterministic rule-matching with LLM reasoning
- **Explicit contracts**: Each LangGraph node has clear input/output contracts
- **Observability first**: Every decision traced via LangSmith
- **Embedded dependencies**: ChromaDB runs in embedded mode (no Docker needed)

---

## Need Help?

- **Project overview**: See [SPEC.md](.coding-agent/SPEC.md)
- **Current state**: See [STATUS.md](.coding-agent/STATUS.md)
- **Technical details**: See [ARCHITECTURE.md](.coding-agent/ARCHITECTURE.md)
- **Existing docs**: See [`docs/`](docs/) directory
