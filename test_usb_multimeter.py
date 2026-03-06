"""
Test USB Multimeter Connection

This script tests the USB multimeter connection and lists available COM ports.
Run this to verify your multimeter is properly connected before using live mode.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_usb_connection():
    """Test USB multimeter detection and connection."""
    print("=" * 60)
    print("USB MULTIMETER CONNECTION TEST")
    print("=" * 60)
    print()
    
    # Step 1: List available COM ports
    print("Step 1: Listing available COM ports...")
    print("-" * 40)
    
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("  [!] No COM ports found!")
            print("  Possible causes:")
            print("    - Multimeter not connected")
            print("    - Drivers not installed")
            print("    - Device not powered on")
            return False
        
        print(f"  Found {len(ports)} COM port(s):")
        print()
        
        cp210x_found = False
        for port in ports:
            vid_str = f"VID:{port.vid:04X}" if port.vid else "VID:????"
            pid_str = f"PID:{port.pid:04X}" if port.pid else "PID:????"
            
            # Check if this is a CP210x device (Silicon Labs)
            is_cp210x = port.vid == 0x10C4 or 'CP210' in port.description.upper()
            if is_cp210x:
                cp210x_found = True
                print(f"  [*] {port.device}")
                print(f"      Description: {port.description}")
                print(f"      Hardware ID: {vid_str}:{pid_str}")
                print(f"      [CP210x DETECTED - This is your multimeter!]")
            else:
                print(f"  [ ] {port.device}")
                print(f"      Description: {port.description}")
                print(f"      Hardware ID: {vid_str}:{pid_str}")
            print()
        
        if not cp210x_found:
            print("  [!] No CP210x device detected.")
            print("  Your multimeter uses the Silicon Labs CP210x USB to UART Bridge.")
            print("  Check if the device is connected and drivers are installed.")
        
    except ImportError:
        print("  [ERROR] pyserial not installed!")
        print("  Install with: pip install pyserial")
        return False
    
    # Step 2: Test multimeter client
    print()
    print("Step 2: Testing USBMultimeterClient...")
    print("-" * 40)
    
    try:
        from src.infrastructure.usb_multimeter import USBMultimeterClient
        
        # Auto-detect
        detected_port = USBMultimeterClient.detect_multimeter()
        if detected_port:
            print(f"  [OK] Auto-detected multimeter on: {detected_port}")
        else:
            print("  [!] Could not auto-detect multimeter")
            print("  You may need to specify the port manually.")
            return False
        
        # Try to connect
        print()
        print("Step 3: Attempting connection...")
        print("-" * 40)
        
        client = USBMultimeterClient(port=detected_port)
        if client.connect():
            print(f"  [OK] Connected to multimeter!")
            print(f"  Port: {client.port}")
            print(f"  Baud Rate: {client.baud_rate}")
            
            # Try to read a measurement
            print()
            print("Step 4: Reading measurement (5 second timeout)...")
            print("-" * 40)
            print("  Connect probes to a voltage source and watch for readings...")
            print()
            
            reading = client.read_measurement(timeout=5.0)
            if reading:
                print(f"  [OK] Measurement received:")
                print(f"      Type: {reading.measurement_type}")
                print(f"      Value: {reading.value} {reading.unit}")
                print(f"      Raw: {reading.raw_value}")
            else:
                print("  [!] No measurement received within timeout.")
                print("  This is normal if the multimeter isn't measuring anything.")
                print("  Try connecting probes to a voltage source and run again.")
            
            client.disconnect()
            print()
            print("=" * 60)
            print("CONNECTION TEST COMPLETE")
            print("=" * 60)
            print()
            print("Your multimeter is ready for live mode!")
            print("Run: python -m src.interfaces.cli --usb CCTV-PSU-24W-V1")
            return True
        else:
            print("  [ERROR] Failed to connect to multimeter")
            print()
            print("Troubleshooting:")
            print("  1. Ensure the multimeter is connected via USB")
            print("  2. Check if CP210x drivers are installed")
            print("  3. Try a different USB port")
            print("  4. Check Device Manager for COM port assignment")
            return False
            
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def list_ports_simple():
    """Simple port listing without full test."""
    print("Available COM Ports:")
    print("-" * 40)
    
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            print(f"  {port.device}: {port.description}")
            
        if not ports:
            print("  No COM ports found")
            
    except ImportError:
        print("pyserial not installed. Run: pip install pyserial")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test USB multimeter connection")
    parser.add_argument("--list", "-l", action="store_true", help="Just list ports")
    args = parser.parse_args()
    
    if args.list:
        list_ports_simple()
    else:
        success = test_usb_connection()
        sys.exit(0 if success else 1)
