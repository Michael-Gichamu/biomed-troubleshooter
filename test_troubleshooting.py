#!/usr/bin/env python3
"""
Comprehensive troubleshooting test for USB multimeter
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial
import serial.tools.list_ports
import time

print("=" * 60)
print("USB MULTIMETER TROUBLESHOOTING")
print("=" * 60)
print()

# Step 1: Check available COM ports
print("Step 1: Checking available COM ports...")
print("-" * 40)

try:
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("  ❌ No COM ports found on the system")
        print()
        print("Troubleshooting:")
        print("  1. Check if the USB cable is properly connected")
        print("  2. Verify the multimeter is turned on and set to USB mode")
        print("  3. Check if USB drivers are installed")
        print("  4. Try a different USB port or cable")
        sys.exit(1)
    
    print(f"  ✔️ Found {len(ports)} COM port(s):")
    for port in ports:
        print(f"    - {port.device}: {port.description}")
        
    print()
        
except Exception as e:
    print(f"  ❌ Error listing COM ports: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Check for CP210x device (our detected device)
print("Step 2: Finding multimeter device...")
print("-" * 40)

multimeter_port = None

for port in ports:
    if "CP210" in port.description or "10C4:EA60" in f"{port.vid:04X}:{port.pid:04X}" if port.vid and port.pid else "":
        multimeter_port = port.device
        print(f"  ✔️ Multimeter detected on {multimeter_port}")
        print(f"    Description: {port.description}")
        if port.vid and port.pid:
            print(f"    Hardware ID: VID:{port.vid:04X}:PID:{port.pid:04X}")
        print()
        break

if not multimeter_port:
    print("  ❌ No multimeter detected")
    print()
    print("Troubleshooting:")
    print("  1. Make sure the multimeter is connected and powered on")
    print("  2. Check if the USB cable is a data cable (not charge-only)")
    print("  3. Verify the multimeter is in USB communication mode")
    print("  4. Check Device Manager for yellow exclamation marks")
    sys.exit(1)

# Step 3: Test basic port communication
print("Step 3: Testing port communication...")
print("-" * 40)

try:
    ser = serial.Serial(
        port=multimeter_port,
        baudrate=2400,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0
    )
    
    print(f"  ✔️ Port {multimeter_port} opened successfully")
    print(f"  Baud rate: {ser.baudrate}")
    print(f"  Timeout: {ser.timeout}")
    
    # Check if we can read anything
    print("  Reading for 10 seconds...")
    start_time = time.time()
    buffer = b""
    
    while time.time() - start_time < 10:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer += data
            print(f"  Read {len(data)} bytes: {data.hex().upper()}")
        time.sleep(0.1)
        
    if buffer:
        print()
        print("  ✔️ Data received!")
        print(f"  Total bytes: {len(buffer)}")
        
        # Check if data looks valid
        has_valid_data = False
        
        # Look for common patterns
        if any(0x30 <= b <= 0x39 for b in buffer):  # Digits
            has_valid_data = True
        
        if b'\x44' in buffer or b'\xc8' in buffer:  # Common start markers
            has_valid_data = True
            
        if has_valid_data:
            print("  ✔️ Data appears to be valid multimeter output")
        else:
            print("  ⚠️ Data may be corrupt or in unexpected format")
            
    else:
        print()
        print("  ❌ No data received from multimeter")
        print()
        print("Troubleshooting:")
        print("  1. Check if the multimeter is turned on")
        print("  2. Verify the multimeter is in USB communication mode (check manual)")
        print("  3. Make sure the multimeter is measuring something (connect probes)")
        print("  4. Try a different USB port on your computer")
        print("  5. Test with a different USB cable")
        print("  6. Check if the multimeter is sending data at a different baud rate")
        print()
        print("Common baud rates for multimeters: 2400, 4800, 9600, 19200")
        
    ser.close()
        
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("Troubleshooting:")
    print("  1. Make sure the port is not already in use")
    print("  2. Check if you have permission to access the port")
    print("  3. Try restarting your computer")

print()
print("=" * 60)
print("TROUBLESHOOTING COMPLETE")
print("=" * 60)
