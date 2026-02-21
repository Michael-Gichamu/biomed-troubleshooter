"""
Mock Signal Generator

Generates simulated probe signals for testing and demonstration.
Provides realistic CCTV PSU fault scenarios for agent validation.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from src.domain.models import SignalBatch, Signal, TestPoint


class MockSignalGenerator:
    """Generates mock signals for demonstration and testing."""

    SCENARIO_PATH = Path("data/mock_signals")

    # Predefined scenarios with metadata
    SCENARIOS = {
        "cctv-psu-output-rail": {
            "name": "CCTV PSU Output Rail Collapse",
            "description": "24V output rail collapsed to 12V, indicating possible load short or regulation failure",
            "difficulty": "easy",
            "equipment_id": "CCTV-PSU-24W-V1"
        },
        "cctv-psu-overvoltage": {
            "name": "CCTV PSU Overvoltage Condition",
            "description": "Output voltage exceeded 24V spec, indicating regulation circuit failure",
            "difficulty": "medium",
            "equipment_id": "CCTV-PSU-24W-V1"
        },
        "cctv-psu-ripple": {
            "name": "CCTV PSU Ripple and Noise",
            "description": "Excessive ripple voltage on output, indicating filter capacitor failure",
            "difficulty": "medium",
            "equipment_id": "CCTV-PSU-24W-V1"
        },
        "cctv-psu-thermal": {
            "name": "CCTV PSU Thermal Shutdown",
            "description": "Device entering thermal protection due to inadequate cooling",
            "difficulty": "easy",
            "equipment_id": "CCTV-PSU-24W-V1"
        },
        "cctv-psu-normal": {
            "name": "CCTV PSU Normal Operation",
            "description": "All readings within specified tolerances",
            "difficulty": "easy",
            "equipment_id": "CCTV-PSU-24W-V1"
        }
    }

    def __init__(self, scenario: str = "cctv-psu-output-rail"):
        self.scenario = scenario

    def generate_signal_batch(
        self,
        equipment_id: Optional[str] = None
    ) -> SignalBatch:
        """Generate a signal batch from predefined scenarios."""

        scenario_info = self.SCENARIOS.get(
            self.scenario,
            self.SCENARIOS["cctv-psu-normal"]
        )

        equip_id = equipment_id or scenario_info["equipment_id"]
        timestamp = datetime.utcnow().isoformat()

        # Load from file if exists
        scenario_file = self.SCENARIO_PATH / f"{self.scenario}.json"

        if scenario_file.exists():
            with open(scenario_file, 'r') as f:
                data = json.load(f)
            return SignalBatch.from_dict(data)

        # Generate from built-in scenarios
        return self._generate_scenario(scenario_info, equip_id, timestamp)

    def _generate_scenario(
        self,
        scenario_info: Dict,
        equipment_id: str,
        timestamp: str
    ) -> SignalBatch:
        """Generate signals based on scenario type."""

        scenario_name = scenario_info["name"]

        if "output-rail" in self.scenario.lower() or "collapsed" in scenario_info["description"].lower():
            # Output rail collapse scenario
            signals = [
                Signal(
                    test_point=TestPoint(
                        id="TP1",
                        name="Primary Input",
                        location="AC mains input voltage"
                    ),
                    value=230.0,
                    unit="V",
                    accuracy=0.5,
                    measurement_type="voltage",
                    timestamp=timestamp
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP2",
                        name="Output Rail",
                        location="24V DC output - COLLAPSED"
                    ),
                    value=12.3,  # Collapsed from 24V
                    unit="V",
                    accuracy=0.1,
                    measurement_type="voltage",
                    timestamp=timestamp,
                    anomaly="collapsed_output"
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP3",
                        name="Output Current",
                        location="Load current draw"
                    ),
                    value=0.52,
                    unit="A",
                    accuracy=0.01,
                    measurement_type="current",
                    timestamp=timestamp
                )
            ]

        elif "overvoltage" in self.scenario.lower():
            # Overvoltage scenario
            signals = [
                Signal(
                    test_point=TestPoint(
                        id="TP1",
                        name="Primary Input",
                        location="AC mains input voltage"
                    ),
                    value=230.0,
                    unit="V",
                    accuracy=0.5,
                    measurement_type="voltage",
                    timestamp=timestamp
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP2",
                        name="Output Rail",
                        location="24V DC output - OVERVOLTAGE"
                    ),
                    value=28.5,  # Overvoltage
                    unit="V",
                    accuracy=0.1,
                    measurement_type="voltage",
                    timestamp=timestamp,
                    anomaly="overvoltage"
                )
            ]

        elif "ripple" in self.scenario.lower():
            # Ripple and noise scenario
            signals = [
                Signal(
                    test_point=TestPoint(
                        id="TP1",
                        name="Primary Input",
                        location="AC mains input voltage"
                    ),
                    value=230.0,
                    unit="V",
                    accuracy=0.5,
                    measurement_type="voltage",
                    timestamp=timestamp
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP2",
                        name="Output Rail",
                        location="24V DC output - HIGH RIPPLE"
                    ),
                    value=24.2,
                    unit="V",
                    accuracy=0.1,
                    measurement_type="voltage",
                    timestamp=timestamp,
                    anomaly="high_ripple"
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP4",
                        name="Ripple Voltage",
                        location="AC component on DC output"
                    ),
                    value=2.5,  # Should be < 100mV
                    unit="Vpp",
                    accuracy=0.01,
                    measurement_type="voltage_ac",
                    timestamp=timestamp,
                    anomaly="high_ripple"
                )
            ]

        elif "thermal" in self.scenario.lower():
            # Thermal shutdown scenario
            signals = [
                Signal(
                    test_point=TestPoint(
                        id="TP1",
                        name="Primary Input",
                        location="AC mains input voltage"
                    ),
                    value=230.0,
                    unit="V",
                    accuracy=0.5,
                    measurement_type="voltage",
                    timestamp=timestamp
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP2",
                        name="Output Rail",
                        location="24V DC output - INTERMITTENT"
                    ),
                    value=0.0,  # Shut down
                    unit="V",
                    accuracy=0.1,
                    measurement_type="voltage",
                    timestamp=timestamp,
                    anomaly="thermal_shutdown"
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP5",
                        name="Temperature",
                        location="Internal temperature sensor"
                    ),
                    value=85.0,  # Near thermal limit
                    unit="°C",
                    accuracy=1.0,
                    measurement_type="temperature",
                    timestamp=timestamp,
                    anomaly="over_temperature"
                )
            ]

        else:
            # Normal operation
            signals = [
                Signal(
                    test_point=TestPoint(
                        id="TP1",
                        name="Primary Input",
                        location="AC mains input voltage"
                    ),
                    value=230.0,
                    unit="V",
                    accuracy=0.5,
                    measurement_type="voltage",
                    timestamp=timestamp
                ),
                Signal(
                    test_point=TestPoint(
                        id="TP2",
                        name="Output Rail",
                        location="24V DC output - NORMAL"
                    ),
                    value=24.0,
                    unit="V",
                    accuracy=0.1,
                    measurement_type="voltage",
                    timestamp=timestamp
                )
            ]

        return SignalBatch(
            timestamp=timestamp,
            equipment_id=equipment_id,
            signals=signals
        )

    def list_scenarios(self) -> List[Dict]:
        """List available scenarios with metadata."""
        return [
            {
                "id": key,
                "name": info["name"],
                "description": info["description"],
                "difficulty": info["difficulty"]
            }
            for key, info in self.SCENARIOS.items()
        ]

    def get_scenario_info(self, scenario: Optional[str] = None) -> Dict:
        """Get detailed info for a scenario."""
        key = scenario or self.scenario
        return self.SCENARIOS.get(key, {})

    def save_scenario(self, filepath: Optional[Path] = None) -> Path:
        """Save current scenario to JSON file."""
        save_path = filepath or self.SCENARIO_PATH / f"{self.scenario}.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        signal_batch = self.generate_signal_batch()
        data = signal_batch.to_dict()

        with open(save_path, 'w') as f:
            json.dump(data, f, indent=2)

        return save_path


# =============================================================================
# Convenience Functions
# =============================================================================

def generate_mock_signals(
    scenario: str = "cctv-psu-output-rail",
    equipment_id: Optional[str] = None
) -> SignalBatch:
    """Generate mock signals for a given scenario."""
    generator = MockSignalGenerator(scenario)
    return generator.generate_signal_batch(equipment_id)


def list_available_scenarios() -> List[Dict]:
    """List all available mock scenarios."""
    generator = MockSignalGenerator()
    return generator.list_scenarios()
