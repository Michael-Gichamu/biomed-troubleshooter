#!/usr/bin/env python3
"""
Test all common baud rates to find what the multimeter uses
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial
import time
import binascii

PORT = "COM8"
BAUD_RATES = [2400, 4800, 9600, 19200, 38400, 57600, 115200]

print("=" * 60)
print("TESTING ALL BAUD RATES")
print("=" * 60)

for baud_rate in BAUD_RATES:
    try:
        print(f"\nTesting baud rate: {baud_rate}")
        print("-" * 40)
        
        ser = serial.Serial(
            port=PORT,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )
        
        print(f"  Port open: {ser.is_open}")
        
        # Read for 3 seconds
        start_time = time.time()
        total_bytes = 0
        buffer = b""
        
        while time.time() - start_time < 3:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                buffer += data
                total_bytes += len(data)
                hex_str = binascii.hexlify(data).decode('ascii').upper()
                print(f"  Read {len(data)} bytes: {hex_str}")
            
            time.sleep(0.1)
        
        print(f"  Total bytes: {total_bytes}")
        
        if buffer:
            print(f"  Full buffer: {binascii.hexlify(buffer).decode('ascii').upper()}")
            
            # Look for patterns
            has_text = False
            for byte in buffer:
                if 0x20 <= byte <= 0x7E:
                    has_text = True
                    break
            
            if has_text:
                try:
                    text = buffer.decode('ascii', errors='ignore')
                    print(f"  ASCII: '{text.strip()}'")
                except:
                    pass
        
        ser.close()
        
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("BAUD RATE TEST COMPLETE")
print("=" * 60)
