"""
CLI Interface

Command-line interface for the troubleshooting agent.
Supports interactive mode and scenario replay for testing.
"""

import json
import argparse
from pathlib import Path
from typing import Optional

from src.application.agent import run_diagnostic


def parse_measurement(arg: str) -> dict:
    """Parse measurement string like 'TP1:12.0:V'."""
    parts = arg.split(':')
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(f"Invalid measurement: {arg}")
    return {
        "test_point": parts[0],
        "value": float(parts[1]),
        "unit": parts[2]
    }


def load_scenario(scenario_file: str) -> dict:
    """Load a scenario from JSON file."""
    path = Path(scenario_file)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"Scenario file not found: {scenario_file}")

    with open(path, 'r') as f:
        data = json.load(f)

    return data


def interactive_mode():
    """Run the agent in interactive mode."""
    print("\n" + "=" * 60)
    print("BIOMEDICAL EQUIPMENT TROUBLESHOOTING AGENT")
    print("Interactive Mode")
    print("=" * 60)

    # Get equipment info
    equipment_model = input("Equipment Model: ").strip()
    equipment_serial = input("Equipment Serial (optional): ").strip()

    # Get trigger
    print("\nDescribe the symptom:")
    trigger_content = input("> ").strip()
    trigger_type = "symptom_report"

    # Collect measurements
    print("\nEnter measurements (format: TP:value:unit, empty to finish):")
    measurements = []
    while True:
        m = input("  Measurement: ").strip()
        if not m:
            break
        try:
            parsed = parse_measurement(m)
            measurements.append(parsed)
        except ValueError as e:
            print(f"  Error: {e}")

    # Run diagnostic
    result = run_diagnostic(
        trigger_type=trigger_type,
        trigger_content=trigger_content,
        equipment_model=equipment_model,
        equipment_serial=equipment_serial,
        measurements=measurements
    )

    # Output result
    print("\n" + "=" * 60)
    print("DIAGNOSIS RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))


def scenario_replay(scenario_file: str):
    """Replay a scenario from file (for testing without hardware)."""
    scenario = load_scenario(scenario_file)

    print("\n" + "=" * 60)
    print("SCENARIO REPLAY")
    print("=" * 60)
    print(f"Scenario: {scenario.get('name', 'Unknown')}")
    print(f"Category: {scenario.get('category', 'Unknown')}")
    print(f"Difficulty: {scenario.get('difficulty', 'Unknown')}")
    print(f"\nDescription: {scenario.get('description', 'N/A')}")

    # Extract measurements from scenario
    measurements = []
    for sig in scenario.get("signals", []):
        measurements.append({
            "test_point": sig.get("test_point", {}).get("id", "UNKNOWN"),
            "value": sig.get("value", 0.0),
            "unit": sig.get("unit", "V")
        })

    equipment_id = scenario.get("signals", [{}])[0].get("test_point", {}).get("id", "CCTV-PSU-24W-V1")
    if "-" in equipment_id and len(equipment_id) > 5:
        equipment_model = equipment_id
    else:
        equipment_model = "CCTV-PSU-24W-V1"

    # Run diagnostic
    result = run_diagnostic(
        trigger_type="signal_submission",
        trigger_content=f"Scenario replay: {scenario.get('name', 'Test')}",
        equipment_model=equipment_model,
        equipment_serial="TEST-001",
        measurements=measurements
    )

    # Compare with expected
    expected = scenario.get("expected_diagnosis", {})
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"Expected cause: {expected.get('primary_cause', 'N/A')}")
    print(f"Expected confidence: {expected.get('confidence', 'N/A')}")
    print(f"\nActual cause: {result.get('diagnosis', {}).get('primary_cause', 'N/A')}")
    print(f"Actual confidence: {result.get('diagnosis', {}).get('confidence_score', 'N/A')}")

    # Check if diagnosis matches
    actual = result.get("diagnosis", {}).get("primary_cause", "")
    expected_cause = expected.get("primary_cause", "")

    if expected_cause.lower() in actual.lower():
        print("\n[OK] Diagnosis matches expected!")
    else:
        print("\n[?] Diagnosis differs from expected (may be due to rule matching)")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Biomedical Equipment Troubleshooting Agent"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        help="Replay a scenario from JSON file"
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="Equipment model"
    )
    parser.add_argument(
        "--measurements", "-M",
        type=str,
        nargs="+",
        help="Measurements in format TP:value:unit"
    )
    parser.add_argument(
        "--trigger", "-t",
        type=str,
        default="",
        help="Trigger description"
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.scenario:
        scenario_replay(args.scenario)
    elif args.model and args.measurements:
        measurements = [parse_measurement(m) for m in args.measurements]
        result = run_diagnostic(
            trigger_type="signal_submission",
            trigger_content=args.trigger or "Quick diagnostic",
            equipment_model=args.model,
            equipment_serial="",
            measurements=measurements
        )
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
