# Mock Signals File Structure

## Individual Scenario Files (`cctv-psu-*.json`)

These are **standalone, self-contained test cases** used by the CLI `--mock` mode:

```python
# Example: Running a specific scenario
python -m src.interfaces.cli --mock cctv-psu-output-rail
```

**Characteristics:**
- Each file contains ONE complete fault scenario
- Includes detailed `troubleshooting_notes` with step-by-step procedures
- Human-readable descriptions for manual testing
- Used for demo/development testing via CLI

## `scenarios.json`

This is the **canonical test suite** used by the **test suite** and **evaluation framework**:

```python
# Example: Running all scenarios for automated testing
pytest src/evaluation/ -v
```

**Characteristics:**
- Contains 5 pre-defined FAULT scenarios (FAULT-001 to FAULT-005)
- Standardized signal format matching the `SignalBatch` model
- Each scenario includes `expected_diagnosis` for automated verification
- Used for regression testing and agent performance evaluation

## Comparison Table

| Aspect | Individual Files | scenarios.json |
|--------|-----------------|----------------|
| **Purpose** | CLI demos, manual testing | Automated testing, CI/CD |
| **Format** | Extended with troubleshooting notes | Standardized signal format |
| **Validation** | Visual inspection | Automated pass/fail |
| **Count** | 4 scenarios | 5 scenarios |
| **Structure** | One file per scenario | All scenarios in one file |

## Scenario Coverage

| Scenario ID | Name | Difficulty | Category |
|-------------|------|------------|----------|
| FAULT-001 | Output Rail Collapse | easy | power |
| FAULT-002 | Overvoltage Output | medium | power |
| FAULT-003 | Primary Side Input Fault | medium | power |
| FAULT-004 | Ripple and Noise on Output | hard | signal_quality |
| FAULT-005 | Thermal Shutdown Condition | easy | control |

## When to Use Each

| Use Case | Use This |
|----------|----------|
| Demoing the agent to stakeholders | Individual files via `--mock` |
| Testing a specific fault manually | Individual files |
| Running automated test suite | `scenarios.json` |
| Verifying agent performance | `scenarios.json` |
| CI/CD pipeline | `scenarios.json` |
