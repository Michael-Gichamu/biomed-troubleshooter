#!/usr/bin/env python3
"""
Test raw serial communication without parsing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial
import time
import binascii

PORT = "COM8"
BAUD = 2400

print("=" * 60)
print("RAW SERIAL TEST")
print("=" * 60)

try:
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0
    )
    
    print(f"Port open: {ser.is_open}")
    print(f"Port: {PORT}")
    print(f"Baud: {BAUD}")
    print()
    
    print("Reading raw data for 10 seconds...")
    print("-" * 40)
    
    total_bytes = 0
    start_time = time.time()
    
    while time.time() - start_time < 10:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            hex_str = binascii.hexlify(data).decode('ascii').upper()
            print(f"{len(data)} bytes: {hex_str}")
            total_bytes += len(data)
        
        time.sleep(0.1)
        
    print("-" * 40)
    print(f"Total bytes read: {total_bytes}")
    
    ser.close()
    print("Port closed")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
