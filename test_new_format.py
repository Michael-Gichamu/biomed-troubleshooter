#!/usr/bin/env python3
"""
Test script for new data format
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.usb_multimeter import USBMultimeterClient
import binascii

print("=" * 60)
print("NEW FORMAT ANALYSIS")
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
            
            # Analyze patterns in the new data format
            print(f"  Byte frequencies:")
            freq = {}
            for byte in buffer:
                freq[byte] = freq.get(byte, 0) + 1
            
            for byte_val in sorted(freq.keys()):
                print(f"    0x{byte_val:02X}: {freq[byte_val]}")
            
            # Look for repeated sequences
            seq_counts = {}
            for i in range(len(buffer) - 10):
                seq = buffer[i:i+10]
                seq_hex = binascii.hexlify(seq).decode('ascii')
                seq_counts[seq_hex] = seq_counts.get(seq_hex, 0) + 1
            
            for seq, count in sorted(seq_counts.items(), key=lambda x: -x[1]):
                if count > 1:
                    print(f"  Sequence 0x{seq}: repeated {count} times")
                
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
