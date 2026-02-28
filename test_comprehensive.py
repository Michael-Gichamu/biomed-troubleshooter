#!/usr/bin/env python3
"""
Comprehensive test of all possible communication settings
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial
import time
import binascii

PORT = "COM8"
BAUD_RATES = [2400, 4800, 9600, 19200]
BYTESIZES = [serial.EIGHTBITS, serial.SEVENBITS]
PARITIES = [serial.PARITY_NONE, serial.PARITY_EVEN, serial.PARITY_ODD]
STOPBITS = [serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE, serial.STOPBITS_TWO]

print("=" * 60)
print("COMPREHENSIVE COMMUNICATION TEST")
print("=" * 60)

# Test all possible combinations
results = []

for baud in BAUD_RATES:
    for bytesize in BYTESIZES:
        for parity in PARITIES:
            for stopbits in STOPBITS:
                try:
                    key = f"{baud} {bytesize}-{parity}-{stopbits}"
                    
                    ser = serial.Serial(
                        port=PORT,
                        baudrate=baud,
                        bytesize=bytesize,
                        parity=parity,
                        stopbits=stopbits,
                        timeout=1.0
                    )
                    
                    # Try to read for 1 second
                    start_time = time.time()
                    buffer = b""
                    while time.time() - start_time < 1:
                        if ser.in_waiting > 0:
                            buffer += ser.read(ser.in_waiting)
                        time.sleep(0.1)
                    
                    ser.close()
                    
                    if buffer:
                        print(f"[OK] {key} - {len(buffer)} bytes")
                        hex_str = binascii.hexlify(buffer).decode('ascii').upper()
                        print(f"  {hex_str}")
                        
                        try:
                            text = buffer.decode('ascii', errors='ignore')
                            if text.strip():
                                print(f"  '{text.strip()}'")
                        except:
                            pass
                        
                        results.append({
                            'config': key,
                            'bytes_received': len(buffer),
                            'data': buffer
                        })
                    else:
                        print(f"[NO DATA] {key}")
                        
                except Exception as e:
                    print(f"[ERROR] {key}: {e}")
                    pass

print("\n" + "=" * 60)
print(f"RESULTS: {len(results)} working configurations")
print("=" * 60)

for result in sorted(results, key=lambda x: -x['bytes_received']):
    print(f"{result['config']}: {result['bytes_received']} bytes")
