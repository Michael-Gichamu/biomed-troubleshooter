#!/usr/bin/env python3
"""
Debug script to troubleshoot multimeter communication
"""

import sys
import os
import time
import serial
import binascii

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_multimeter():
    PORT = "COM8"
    BAUD_RATES = [2400, 9600, 19200, 4800]
    
    print("=" * 60)
    print("MULTIMETER DEBUG")
    print("=" * 60)
    print()
    
    for baud_rate in BAUD_RATES:
        print(f"Testing baud rate: {baud_rate}")
        print("-" * 40)
        
        try:
            ser = serial.Serial(
                port=PORT,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            
            print(f"  [OK] Port open")
            print(f"  Timeout: {ser.timeout}")
            print(f"  in_waiting: {ser.in_waiting}")
            
            # Try to read data
            print("  Reading for 3 seconds...")
            start_time = time.time()
            total_bytes = 0
            buffer = b""
            
            while time.time() - start_time < 3.0:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    total_bytes += len(data)
                    buffer += data
                    print(f"  Read {len(data)} bytes: {binascii.hexlify(data).decode('ascii').upper()}")
                else:
                    time.sleep(0.1)
            
            print(f"  Total bytes read: {total_bytes}")
            if buffer:
                print(f"  Buffer: {binascii.hexlify(buffer).decode('ascii').upper()}")
                
                # Look for patterns
                if b'\x44' in buffer and b'\x11' in buffer:
                    print("  [*] Found possible frame markers")
                
                # Try to decode as text
                try:
                    text = buffer.decode('ascii', errors='ignore')
                    print(f"  ASCII decode: '{text.strip()}'")
                except:
                    pass
                
                try:
                    text = buffer.decode('utf-8', errors='ignore')
                    print(f"  UTF-8 decode: '{text.strip()}'")
                except:
                    pass
                
            ser.close()
            
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        print()
    
    print("=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    debug_multimeter()
