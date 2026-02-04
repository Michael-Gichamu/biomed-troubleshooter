"""
Biomedical Equipment Troubleshooting Agent

A LangGraph-based AI agent for troubleshooting biomedical power electronics.
Uses RAG + signal interpretation for decision-support.

Architecture:
    - src/domain: Pure business entities and domain logic
    - src/infrastructure: External services (RAG, data access)
    - src/application: Use cases and LangGraph workflows
    - src/interfaces: CLI, API, and adapters

Usage:
    from src.application.agent import run_diagnostic
    from src.interfaces.cli import main

    result = run_diagnostic(
        trigger_type="signal_submission",
        trigger_content="Power supply not working",
        equipment_model="CCTV-PSU-24W-V1",
        equipment_serial="",
        measurements=[{"test_point": "TP1", "value": 12.0, "unit": "V"}]
    )
"""

__version__ = "1.0.0"
