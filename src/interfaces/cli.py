"""
CLI Interface

Command-line interface for the troubleshooting agent.
Supports interactive mode and USB multimeter mode.
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
import time
from pathlib import Path
from typing import Optional

from src.application.agent import run_diagnostic
from src.interfaces.mode_router import ModeRouter
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


def run_usb_mode(equipment_id: str, timeout: int = 60) -> None:
    """
    Run agent in USB multimeter mode with INTERACTIVE agent guidance after each measurement.

    Args:
        equipment_id: Equipment ID being tested
        timeout: Seconds to wait for measurements
    """
    print_header("USB MULTIMETER MODE - Interactive Troubleshooting Agent")
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
    print("\nTaking measurements with agent guidance...")
    print("After each measurement, the agent will analyze it and guide your next step.")
    print()

    # Skip initial analysis - we'll analyze after each measurement
    print("="*60)
    print("Ready to take measurements...")
    print("The agent will guide you after each measurement you take.")
    print("="*60 + "\n")
    
    # Store initial recommendations for display
    initial_recommendations = []
    
    # Initialize measurement tracking
    measurements = []
    test_point_id = 1
    start_time = time.time()
    last_reading = None
    
    try:
        while time.time() - start_time < timeout:
            print(f"\n[Step {test_point_id}] Waiting for measurement...")
            print("(IMPORTANT: Change multimeter mode/rotary switch to trigger a reading)")
            print("(e.g., switch from DC Voltage to Continuity, or to a different range)")
            
            # Wait longer for MS8250D which only sends on mode change
            reading = client.read_measurement(timeout=30.0)
            
            if reading:
                # Only record if we get a new distinct reading
                if last_reading is None or reading.value != last_reading.value or reading.unit != last_reading.unit:
                    
                    # Collect multiple readings to get stable average
                    print("\n  Collecting readings for stability...")
                    readings_for_avg = [reading]
                    stable_timeout = time.time() + 5  # Collect for 5 seconds
                    
                    while time.time() < stable_timeout:
                        extra_reading = client.read_measurement(timeout=1.0)
                        if extra_reading and extra_reading.unit == reading.unit:
                            readings_for_avg.append(extra_reading)
                            print(f"    Sample: {extra_reading.value} {extra_reading.unit}")
                        else:
                            break
                    
                    # Smart filtering: only average stable values (within threshold)
                    if len(readings_for_avg) > 1:
                        values = [r.value for r in readings_for_avg]
                        mean_val = sum(values) / len(values)
                        
                        # Filter: keep only values within 5% of mean (stable readings)
                        threshold = abs(mean_val) * 0.05  # 5% tolerance
                        if threshold < 0.5:  # Minimum threshold of 0.5 for small values
                            threshold = 0.5
                        
                        stable_values = [v for v in values if abs(v - mean_val) <= threshold]
                        
                        if len(stable_values) >= 2:
                            avg_value = sum(stable_values) / len(stable_values)
                            print(f"\n  [Filtered] {len(stable_values)} stable values (within +/-{threshold:.2f})")
                            print(f"  [Averaged] {avg_value:.2f} {reading.unit} (from {len(stable_values)}/{len(values)} samples)")
                            final_value = avg_value
                        else:
                            print(f"\n  [WARN] Readings too unstable - using first value")
                            final_value = reading.value
                            stable_values = [reading.value]
                    else:
                        final_value = reading.value
                    
                    measurement = {
                        "test_point": f"TP{test_point_id}",
                        "value": final_value,
                        "unit": reading.unit
                    }
                    measurements.append(measurement)
                    print(f"\n[OK] Recorded: {final_value:.2f} {reading.unit} ({reading.measurement_type})")
                    
                    # INTERACTIVE: Run agent after EACH measurement
                    print_section("AGENT ANALYSIS")
                    result = run_diagnostic(
                        trigger_type="usb_measurement",
                        trigger_content=f"Live measurement: {final_value:.2f} {reading.unit} ({reading.measurement_type})",
                        equipment_model=equipment_id,
                        equipment_serial="USB-001",
                        measurements=measurements
                    )
                    
                    # Display agent guidance
                    if "recommended_actions" in result and result["recommended_actions"]:
                        print("Agent Guidance:")
                        for action in result["recommended_actions"][:3]:
                            print(f"  → {action}")
                    
                    if "diagnosis" in result and result["diagnosis"]:
                        diag = result["diagnosis"]
                        current_diag = diag.get('primary_cause', 'Unknown')
                        confidence = diag.get('confidence_score', 'Unknown')
                        print(f"\nCurrent Assessment: {current_diag} (Confidence: {confidence})")
                    
                    # Check if we should continue
                    if "should_continue" in result:
                        if not result["should_continue"]:
                            print("\n[Agent] Diagnostic complete! No more measurements needed.")
                            break
                    
                    test_point_id += 1
                    last_reading = reading
                else:
                    print(f"  (Duplicate reading: {reading.value} {reading.unit}, ignoring)")
            else:
                print("  (No reading detected - check multimeter connection)")
                
            if len(measurements) >= 15:
                print("\nMaximum measurements reached (15)")
                break

    except KeyboardInterrupt:
        print("\n\n[EXIT] Interrupted by user")
    
    finally:
        client.disconnect()

    if measurements:
        print_section("FINAL DIAGNOSIS")
        result = run_diagnostic(
            trigger_type="usb_measurement",
            trigger_content="Final diagnosis from all measurements",
            equipment_model=equipment_id,
            equipment_serial="USB-001",
            measurements=measurements
        )

        print_section("Final Diagnosis Result")
        if "diagnosis" in result:
            diag = result["diagnosis"]
            print(f"  Primary Cause: {diag.get('primary_cause', 'Unknown')}")
            print(f"  Confidence: {diag.get('confidence_score', 'Unknown')}")
            if "severity" in diag:
                print(f"  Severity: {diag.get('severity', 'Unknown')}")
        
        if "recommended_actions" in result:
            print("\nFinal Recommended Actions:")
            for action in result["recommended_actions"]:
                print(f"  → {action}")

    print("\nDisconnected from multimeter.")


def show_mode_status() -> None:
    """Display current mode configuration."""
    print_header("MODE STATUS")

    router = ModeRouter()
    mode_info = router.get_mode_info()

    print(f"Current Mode: {mode_info['mode'].upper()}")
    print()

    if mode_info['mode'] == 'usb':
        print("USB Configuration:")
        print(f"  Port: {mode_info['usb_port']}")
    else:
        print("Mode: USB (multimeter)")
    
    print()
    print("To change mode, set APP_MODE in .env file:")
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
  # Run in USB multimeter mode
  python -m src.interfaces.cli --usb CCTV-PSU-24W-V1

  # Show current mode configuration
  python -m src.interfaces.cli --status

  # Interactive mode with manual input
  python -m src.interfaces.cli --interactive
        """
    )

    # Mode commands
    mode_group = parser.add_mutually_exclusive_group()

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
    if args.usb:
        run_usb_mode(args.usb)
    elif args.status:
        show_mode_status()
    elif args.interactive:
        interactive_mode()
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
        print("  python -m src.interfaces.cli --usb <model>    # Use USB multimeter")
        print("  python -m src.interfaces.cli --status         # Check configuration")
        print()
        print("Run with --help for full command list")
        print()
        parser.print_help()


if __name__ == "__main__":
    main()
