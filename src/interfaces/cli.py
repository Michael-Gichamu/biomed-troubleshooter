"""
CLI Interface

Command-line interface for the troubleshooting agent.
Supports interactive mode, mock mode, USB multimeter mode, and scenario replay.
"""

import os
# Load environment variables FIRST, before any LangChain imports
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

# Verify LangChain project is set
langchain_project = os.getenv("LANGCHAIN_PROJECT", "biomed-troubleshooter")
print(f"LangChain Project: {langchain_project}")

import json
import argparse
from pathlib import Path
from typing import Optional

from src.application.agent import run_diagnostic
from src.interfaces.mode_router import ModeRouter, MockSignalSource
from src.infrastructure.mock_generator import MockSignalGenerator, list_available_scenarios
from src.domain.models import SignalBatch


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


def print_header(title: str) -> None:
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str) -> None:
    """Print formatted section header."""
    print(f"\n--- {title} ---")


def run_mock_mode(scenario: str = "cctv-psu-output-rail") -> dict:
    """
    Run agent in mock mode with predefined scenario.

    Args:
        scenario: Name of the scenario to run

    Returns:
        Diagnostic result dictionary
    """
    print_header("MOCK MODE - Biomedical Troubleshooting Agent")

    # Get mode info
    router = ModeRouter()
    mode = router.get_mode()
    mode_info = router.get_mode_info()

    print(f"Mode: {mode}")
    print(f"Scenario: {scenario}")
    print()

    # Show available scenarios
    print("Available scenarios:")
    scenarios = list_available_scenarios()
    for s in scenarios:
        marker = "*" if s["id"] == scenario else " "
        print(f"  {marker} {s['id']}: {s['name']} ({s['difficulty']})")
    print()

    # Generate mock signals
    generator = MockSignalGenerator(scenario)
    signal_batch = generator.generate_signal_batch()

    print_section("Generated Signals")
    for sig in signal_batch.signals:
        anomaly_mark = "[!]" if sig.anomaly else ""
        print(f"  {sig.test_point.id}: {sig.value} {sig.unit} ({sig.measurement_type}){anomaly_mark}")

    print()

    # Run diagnostic
    result = run_diagnostic(
        trigger_type="mock_signal",
        trigger_content=f"Mock scenario: {scenario}",
        equipment_model=signal_batch.equipment_id,
        equipment_serial="MOCK-001",
        measurements=[
            {
                "test_point": s.test_point.id,
                "value": s.value,
                "unit": s.unit
            }
            for s in signal_batch.signals
        ]
    )

    # Display results
    print_section("Diagnosis Result")

    if "diagnosis" in result:
        diag = result["diagnosis"]
        print(f"  Primary Cause: {diag.get('primary_cause', 'Unknown')}")
        print(f"  Confidence: {diag.get('confidence_score', 'Unknown')}")
        print(f"  Severity: {diag.get('severity', 'Unknown')}")

        if "recommended_actions" in diag:
            print("\n  Recommended Actions:")
            for i, action in enumerate(diag["recommended_actions"], 1):
                print(f"    {i}. {action}")

    print("\n" + "=" * 60)
    print(f"Full result saved. Traces available in LangSmith.")
    print("=" * 60)

    return result


def run_usb_mode(equipment_id: str, timeout: int = 60) -> None:
    """
    Run agent in USB multimeter mode.

    Args:
        equipment_id: Equipment ID being tested
        timeout: Seconds to wait for measurements
    """
    print_header("USB MULTIMETER MODE - Biomedical Troubleshooting Agent")
    print(f"Equipment: {equipment_id}")
    print(f"Timeout: {timeout} seconds")
    print("\nPress Ctrl+C to exit\n")

    # Import USB multimeter
    try:
        from src.infrastructure.usb_multimeter import USBMultimeterClient
    except ImportError:
        print("[ERROR] pyserial not installed. Install with: pip install pyserial")
        return

    router = ModeRouter()
    config = router.config

    print("Detecting USB multimeter...")
    
    client = USBMultimeterClient(port=config.get("usb_port"))
    
    if not client.connect():
        print("[ERROR] Failed to connect to USB multimeter")
        print("\nTroubleshooting:")
        print("  1. Ensure multimeter is connected via USB")
        print("  2. Check if drivers are installed")
        print("  3. Try specifying port: --usb COM3")
        return

    print(f"Connected to multimeter!")
    print("\nTaking measurements...")
    print("Connect probes to test points and press Enter after each measurement.")
    print()

    try:
        measurements = []
        test_point_id = 1
        
        while True:
            input(f"Press Enter to take measurement {test_point_id} (or 'q' to finish): ")
            
            reading = client.read_measurement(timeout=5.0)
            if reading:
                measurements.append({
                    "test_point": f"TP{test_point_id}",
                    "value": reading.value,
                    "unit": reading.unit
                })
                print(f"  Recorded: {reading.value} {reading.unit} ({reading.measurement_type})")
                test_point_id += 1
            else:
                print("  No reading received. Try again.")
            
            if len(measurements) >= 10:
                print("\nMaximum measurements reached (10)")
                break

    except KeyboardInterrupt:
        print("\n\n[EXIT] Interrupted by user")
    
    finally:
        client.disconnect()

    if measurements:
        print_section("RUNNING DIAGNOSIS")
        result = run_diagnostic(
            trigger_type="usb_measurement",
            trigger_content="Live USB multimeter measurements",
            equipment_model=equipment_id,
            equipment_serial="USB-001",
            measurements=measurements
        )

        print_section("Diagnosis Result")
        if "diagnosis" in result:
            diag = result["diagnosis"]
            print(f"  Primary Cause: {diag.get('primary_cause', 'Unknown')}")
            print(f"  Confidence: {diag.get('confidence_score', 'Unknown')}")

    print("\nDisconnected from multimeter.")


def show_mode_status() -> None:
    """Display current mode configuration."""
    print_header("MODE STATUS")

    router = ModeRouter()
    mode_info = router.get_mode_info()

    print(f"Current Mode: {mode_info['mode'].upper()}")
    print()

    if mode_info['mode'] == 'mock':
        print("Mock Configuration:")
        print(f"  Scenario: {mode_info['mock_scenario']}")
        print()
        print("Available Scenarios:")
        scenarios = list_available_scenarios()
        for s in scenarios:
            print(f"  - {s['id']}: {s['name']} ({s['difficulty']})")
    else:
        print("USB Configuration:")
        print(f"  Port: {mode_info['usb_port']}")

    print()
    print("To change mode, set APP_MODE in .env file:")
    print("  APP_MODE=mock   # For simulation")
    print("  APP_MODE=usb    # For USB multimeter")


def interactive_mode():
    """Run the agent in interactive mode."""
    print_header("INTERACTIVE MODE")

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
    print_section("DIAGNOSIS RESULT")
    print(json.dumps(result, indent=2))


def scenario_replay(scenario_file: str):
    """Replay a scenario from file (for testing without hardware)."""
    scenario = load_scenario(scenario_file)

    print_header("SCENARIO REPLAY")
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
    print_section("VERIFICATION")
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
        description="Biomedical Equipment Troubleshooting Agent - LangGraph-powered diagnostic system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in mock mode with default scenario
  python -m src.interfaces.cli --mock

  # Run in mock mode with specific scenario
  python -m src.interfaces.cli --mock cctv-psu-overvoltage

  # Run in USB multimeter mode
  python -m src.interfaces.cli --usb CCTV-PSU-24W-V1

  # Show current mode configuration
  python -m src.interfaces.cli --status

  # Interactive mode with manual input
  python -m src.interfaces.cli --interactive

  # Replay scenario from file
  python -m src.interfaces.cli -s data/mock_signals/scenario.json
        """
    )

    # Mode commands
    mode_group = parser.add_mutually_exclusive_group()

    mode_group.add_argument(
        "--mock", "-M",
        const="cctv-psu-output-rail",
        nargs="?",
        metavar="SCENARIO",
        help="Run in mock mode with predefined scenario (default: cctv-psu-output-rail)"
    )
    mode_group.add_argument(
        "--usb", "-U",
        metavar="EQUIPMENT_ID",
        help="Run in USB multimeter mode with Mastech MS8250D"
    )
    mode_group.add_argument(
        "--status", "-S",
        action="store_true",
        help="Show current mode configuration"
    )

    # Interactive and replay (keep for backward compatibility)
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode with manual input"
    )
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        help="Replay a scenario from JSON file"
    )

    # Standard diagnostic arguments
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="Equipment model"
    )
    parser.add_argument(
        "--measurements", "-V",
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

    # Handle mode commands
    if args.mock is not None:
        run_mock_mode(args.mock)
    elif args.usb:
        run_usb_mode(args.usb)
    elif args.status:
        show_mode_status()
    elif args.interactive:
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
        # Default: show help
        print_header("BIOMEDICAL TROUBLESHOOTING AGENT")
        print()
        print("LangGraph-powered AI agent for biomedical equipment troubleshooting")
        print()
        print("Quick Start:")
        print("  python -m src.interfaces.cli --mock           # Run demo scenario")
        print("  python -m src.interfaces.cli --usb <model>    # Use USB multimeter")
        print("  python -m src.interfaces.cli --status         # Check configuration")
        print()
        print("Run with --help for full command list")
        print()
        parser.print_help()


if __name__ == "__main__":
    main()
