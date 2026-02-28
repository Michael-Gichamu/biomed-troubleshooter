#!/usr/bin/env python3
"""
Test script with detailed debugging info
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.usb_multimeter import USBMultimeterClient
import binascii

print("=" * 60)
print("VERBOSE TEST")
print("=" * 60)

try:
    # Create client instance
    client = USBMultimeterClient(port="COM8")
    
    if not client.connect():
        print("ERROR: Could not connect")
        sys.exit(1)
    
    print(f"Connected at {client.baud_rate} baud")
    print()
    
    print("Reading for 10 seconds...")
    
    import time
    start_time = time.time()
    
    while time.time() - start_time < 10:
        buffer = b""
        # Read for 0.5 seconds
        read_start = time.time()
        while time.time() - read_start < 0.5 and client.is_connected():
            if client._serial.in_waiting > 0:
                data = client._serial.read(client._serial.in_waiting)
                buffer += data
        
        if buffer:
            hex_str = binascii.hexlify(buffer).decode('ascii').upper()
            print(f"Read {len(buffer)} bytes: {hex_str}")
            
            # Try to parse directly
            reading = client._parse_binary_frame(buffer)
            if reading:
                print(f"  Parsed: {reading.value} {reading.unit} ({reading.measurement_type})")
            else:
                print("  Not parsed as binary frame")
                
        time.sleep(0.1)
        
    print()
    print("Test complete")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    if 'client' in locals():
        client.disconnect()
