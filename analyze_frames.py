#!/usr/bin/env python3
"""
Analyze the captured multimeter frames
"""

import binascii

# Real data from debug
raw_data = b'4022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004022020000303557031000000000000000004422030000303504031000000000000000004422030000303504031000000000000000004422030000303504031000000000000000004422030000303504031000000000000000004422030000303504031000000000000000004422030000303576011000000000000000004422030000303576'

# Decode hex string to bytes
data_bytes = binascii.unhexlify(raw_data)

print("=" * 60)
print("FRAME ANALYSIS")
print("=" * 60)
print(f"Total bytes: {len(data_bytes)}")
print()

# Look for frames starting with 0x40 or 0x44 and ending with 0x10 or 0x11
frames = []
i = 0

while i < len(data_bytes):
    # Look for start markers
    if data_bytes[i] == 0x40 or data_bytes[i] == 0x44:
        # Look for end markers in next 10-20 bytes
        end_marker = None
        end_pos = -1
        
        # Try to find end markers
        for j in range(i + 5, min(i + 20, len(data_bytes))):
            if data_bytes[j] in [0x10, 0x11]:
                end_marker = data_bytes[j]
                end_pos = j
                break
        
        if end_pos != -1:
            frame = data_bytes[i:end_pos+1]
            frames.append(frame)
            i = end_pos + 1
            continue
            
    i += 1

print(f"Found {len(frames)} complete frames:")
print()

for i, frame in enumerate(frames[:20]):
    hex_str = binascii.hexlify(frame).decode('ascii').upper()
    print(f"Frame {i}: {hex_str}")
    
    # Detailed analysis
    print(f"  Length: {len(frame)} bytes")
    print(f"  Start: {frame[0]:02X}")
    print(f"  End: {frame[-1]:02X}")
    
    if len(frame) >= 9:
        print(f"  Bytes 5-6 (value): {frame[5]:02X} {frame[6]:02X}")
        print(f"  Byte 7 (decimal): {frame[7]:02X}")
    
    print()
