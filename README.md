# Biomedical Equipment Troubleshooting Agent

A LangGraph-based AI agent for troubleshooting biomedical power electronics.

## Architecture

The project follows **Clean Architecture** principles with strict separation of concerns:

```
src/
├── domain/           # Pure business entities (no framework dependencies)
│   └── models.py      # SignalCollection, FaultHypothesis, DiagnosticRule, etc.
├── infrastructure/   # External services and adapters
│   └── rag_repository.py  # ChromaDB integration, static rules
├── application/       # Use cases and LangGraph workflows
│   └── agent.py       # LangGraph StateGraph implementation
└── interfaces/        # CLI and adapters
    └── cli.py         # Command-line interface
```

## Design Principles

1. **Determinism**: Agent behavior is predictable and reproducible
2. **Debuggability**: Every state transition is logged and traceable
3. **Explainability**: Reasoning chain is always included in output
4. **Testability**: No hardware required for testing (scenario replay)

## Installation

```bash
pip install -e .
```

## Usage

### Interactive Mode

```bash
python -m src.interfaces.cli --interactive
```

### Quick Diagnostic

```bash
python -m src.interfaces.cli -m CCTV-PSU-24W-V1 -M "TP1:12.0:V" "TP2:5.0:V" -t "Power supply issue"
```

### Scenario Replay (Testing)

```bash
python -m src.interfaces.cli -s data/mock_signals/scenarios.json
```

### Programmatic Usage

```python
from src.application.agent import run_diagnostic

result = run_diagnostic(
    trigger_type="signal_submission",
    trigger_content="CCTV power supply not working",
    equipment_model="CCTV-PSU-24W-V1",
    equipment_serial="",
    measurements=[
        {"test_point": "TP1", "value": 232.0, "unit": "V"},
        {"test_point": "TP2", "value": 0.05, "unit": "V"}
    ]
)
```

## Output Format

```json
{
  "version": "1.0",
  "timestamp": "2026-02-03T10:00:00Z",
  "session_id": "uuid",
  "diagnosis": {
    "primary_cause": "Output rail collapse",
    "confidence_score": 0.85,
    "signal_evidence": {...}
  },
  "recommendations": [...],
  "reasoning_chain": [...],
  "limitations": {...}
}
```

## Testing

Run tests with:

```bash
pytest tests/
```

## Project Structure

- `data/mock_signals/`: Test scenarios for validation
- `docs/`: Architecture documentation
- `tests/`: Unit and integration tests

## License

MIT
