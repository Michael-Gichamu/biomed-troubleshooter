"""
Log Raw Binary Data from Multimeter

This script logs raw binary data to help reverse-engineer the communication protocol.
"""

import sys
import os
import serial
import time
import binascii

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log_raw_data():
    """Log raw binary data from the multimeter."""
    PORT = "COM8"
    BAUD_RATE = 2400
    
    print("=" * 60)
    print("LOGGING RAW BINARY DATA")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Baud rate: {BAUD_RATE}")
    print()
    print("Press Ctrl+C to stop...")
    print("-" * 40)
    print()
    
    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        
        time.sleep(0.5)
        print("Connected. Waiting for data...")
        
        start_time = time.time()
        
        while time.time() - start_time < 10.0:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                
                # Print hex view
                hex_str = binascii.hexlify(data).decode('ascii').upper()
                
                # Group into bytes
                hex_pairs = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
                
                # Print with offsets
                print(f"{len(data)} bytes received:")
                print(" ".join(hex_pairs))
                
                # Try to find patterns
                print("Pattern analysis:")
                
                # Look for repeating sequences
                if len(data) > 4:
                    # Check for repeated bytes
                    unique_bytes = len(set(data))
                    if unique_bytes < len(data) * 0.5:
                        print(f"  High repetition: {unique_bytes} unique bytes out of {len(data)}")
                
                # Look for possible voltage/current values
                for i in range(len(data) - 1):
                    byte1 = data[i]
                    byte2 = data[i+1]
                    
                    # Check for possible BCD or binary coded values
                    if 0x30 <= byte1 <= 0x39 or 0x30 <= byte2 <= 0x39:
                        print(f"  Digit-like bytes at positions {i}-{i+1}: {byte1:02X} {byte2:02X}")
                
                # Check for start/end markers
                if data[0] == 0x44 or data[-1] == 0x11:
                    print(f"  Possible frame markers detected")
                
                print()
                time.sleep(0.5)
            
            else:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("\nDisconnected")

def test_protocol_sniffing():
    """Test various decoding methods."""
    print("Testing different decoding methods...")
    
    # Sample data from previous test
    sample_data = b'\x00\x00\x00\x00\x00\x00\x00\x00D"\x03\x00\x003u\x02\x11\x00\x00\x00\x00\x00\x00\x00\x00D"\x03\x00\x003u\x02\x11\x00\x00\x00\x00\x00\x00\x00\x00D"\x03\x00\x003t\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00@"\x02\x00\x002u\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00\x88"\x02\x00!\x132\x14\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00\x88"\x02\x00!\x132\x14\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00\x88"\x02\x00!\x030t\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00H"\x02\x00r\x017%\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00@"\x02\x00\x001w\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00@"\x02\x00\x002%\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00@"\x02\x00\x00\x10%\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00@"\x02\x00\x007\x04\x03\x11\x00\x00\x00\x00\x00\x00\x00\x00@"\x02\x00\x0005v\x01\x11\x00\x00\x00\x00\x00\x00\x00\x00'
    
    print(f"\nSample data length: {len(sample_data)} bytes")
    print(f"Hex: {binascii.hexlify(sample_data).decode('ascii').upper()}")
    
    # Look for patterns
    frames = []
    i = 0
    
    while i < len(sample_data):
        # Look for start marker (0x44 = 'D')
        if sample_data[i] == 0x44 and (i + 10) < len(sample_data):
            # Try to find end marker (0x11)
            end = sample_data.find(b'\x11', i)
            if end != -1 and (end - i) < 20:
                frame = sample_data[i:end+1]
                frames.append(frame)
                print(f"\nFrame found at {i}: {binascii.hexlify(frame).decode('ascii').upper()}")
                i = end + 1
            else:
                i += 1
        else:
            i += 1
            
    if frames:
        print(f"\nTotal frames found: {len(frames)}")
        
        # Analyze frame structure
        first_frame = frames[0]
        print(f"\nFirst frame structure ({len(first_frame)} bytes):")
        
        for j, byte in enumerate(first_frame):
            print(f"  Offset {j:02X}: {byte:02X} ('{chr(byte)}' if printable)")

if __name__ == "__main__":
    # First, test protocol sniffing on sample data
    test_protocol_sniffing()
    
    # Then log real data
    print("\n" + "="*60)
    print("Capturing real data from device...")
    print("="*60)
    log_raw_data()
