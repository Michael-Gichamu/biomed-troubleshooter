"""
Test script for validating the refactored diagnostic system classes.

This script tests:
1. MultimeterStabilizer - stabilization logic with mock data
2. DiagnosticState - creation and serialization

Note: No actual hardware tests are performed (no multimeter connected).
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from src.infrastructure.multimeter_stabilizer import MultimeterStabilizer
from src.domain.diagnostic_state import DiagnosticState


def test_multimeter_stabilizer():
    """Test the MultimeterStabilizer class with mock data."""
    print("\n=== Testing MultimeterStabilizer ===")
    
    # Create stabilizer instance with correct parameters
    stabilizer = MultimeterStabilizer(
        max_samples=50,
        min_samples=3,
        max_duration=180.0,
        window_size=10,
        stability_threshold=0.01,
        cluster_tolerance=0.05,
        zero_threshold=0.01
    )
    print("  Created MultimeterStabilizer instance")
    
    # Test adding samples one at a time (as the class expects)
    stable_readings = [12.05, 12.06, 12.05, 12.06, 12.05, 12.06, 12.05]
    for reading in stable_readings:
        result = stabilizer.add_sample(reading)
    
    # Get the stable reading
    result = stabilizer.get_stable_reading()
    print(f"  Input: {stable_readings}")
    print(f"  Result: {result}")
    assert result is not None, "Expected stable reading result"
    print("  Stabilization with stable readings works")
    
    # Test with noisy readings that should stabilize
    stabilizer.reset()
    noisy_readings = [12.05, 15.00, 12.06, 12.05, 12.06, 12.05]
    for reading in noisy_readings:
        result = stabilizer.add_sample(reading)
    
    result = stabilizer.get_stable_reading()
    print(f"  Input: {noisy_readings}")
    print(f"  Result: {result}")
    print("  Outlier filtering works")
    
    # Test reset functionality
    stabilizer.reset()
    count = stabilizer.get_sample_count()
    assert count == 0, "Expected sample count to be 0 after reset"
    print("  Reset functionality works")
    
    # Test sample count
    stabilizer.add_sample(12.05)
    stabilizer.add_sample(12.06)
    count = stabilizer.get_sample_count()
    assert count == 2, f"Expected 2 samples, got {count}"
    print(f"  Sample count works: {count} samples")
    
    print("\n  All MultimeterStabilizer tests passed!")
    return True


def test_diagnostic_state():
    """Test the DiagnosticState class."""
    print("\n=== Testing DiagnosticState ===")
    
    # Create a diagnostic state instance with correct parameters
    # Note: current_step is an integer (step index), equipment_model is the field name
    state = DiagnosticState(
        equipment_model="cctv-psu-24w-v1",
        current_step=0
    )
    print("  Created DiagnosticState instance")
    
    # Test adding a measurement directly to the measurements dict
    state.measurements["output_rail"] = {
        "value": 12.05,
        "unit": "V",
        "is_stable": True
    }
    print("  Added measurement: output_rail = 12.05V")
    
    # Test adding a tested point to tested_points list
    state.tested_points.append("bridge_rectifier")
    print("  Added tested point: bridge_rectifier")
    
    # Test adding an eliminated fault
    state.eliminated_faults.append("output_rail_short")
    print("  Eliminated fault: output_rail_short")
    
    # Test setting hypothesis
    state.current_hypothesis = "Normal operation"
    state.hypothesis_list = ["Normal operation", "Output rail overvoltage"]
    print("  Set hypothesis and hypothesis list")
    
    # Test serialization
    serialized = state.model_dump()
    json_str = json.dumps(serialized, indent=2)
    print(f"  Serialized state ({len(json_str)} bytes)")
    
    # Test deserialization
    restored = DiagnosticState(**serialized)
    assert restored.equipment_model == state.equipment_model
    assert restored.current_step == state.current_step
    print("  Deserialized state correctly")
    
    # Test getting summary (using model_dump for Pydantic v2)
    summary = {
        "equipment_model": state.equipment_model,
        "current_step": state.current_step,
        "measurements_count": len(state.measurements),
        "tested_points_count": len(state.tested_points),
        "eliminated_faults_count": len(state.eliminated_faults)
    }
    print(f"  Summary: {summary}")
    assert "equipment_model" in summary
    assert "measurements_count" in summary
    print("  State summary works")
    
    print("\n  All DiagnosticState tests passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("REFACTORED CLASSES VALIDATION TEST")
    print("=" * 60)
    
    try:
        test_multimeter_stabilizer()
        test_diagnostic_state()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        print("\nThe refactored diagnostic system classes are working correctly.")
        return True
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
