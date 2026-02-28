"""
Test Different Baud Rates

This script tests different baud rates to find the correct one for your multimeter.
The raw data was garbled, which suggests a baud rate mismatch.
"""

import sys
import os
import serial
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_baud_rates():
    """Test different baud rates."""
    PORT = "COM8"
    BAUD_RATES = [2400, 4800, 9600, 19200, 38400, 57600, 115200]
    
    print("=" * 60)
    print("BAUD RATE TEST - COM8")
    print("=" * 60)
    print()
    
    for baud in BAUD_RATES:
        print(f"Testing baud rate: {baud}")
        print("-" * 40)
        
        try:
            ser = serial.Serial(
                port=PORT,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            
            time.sleep(0.5)
            
            # Read some data
            buffer = b""
            start_time = time.time()
            
            while time.time() - start_time < 2.0:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    buffer += data
            
            ser.close()
            
            # Try to decode
            if buffer:
                print(f"  Raw bytes ({len(buffer)}): {buffer.hex()}")
                
                # Try different encodings
                for encoding in ['utf-8', 'ascii', 'latin-1']:
                    try:
                        text = buffer.decode(encoding, errors='replace')
                        text_clean = ''.join([c if c.isprintable() or c in '\r\n' else '.' for c in text])
                        print(f"  Decoded ({encoding}): '{text_clean}'")
                        
                        # Look for voltage/current patterns
                        if any(keyword in text_clean.lower() for keyword in ['dc', 'ac', 'v', 'a', 'ohm', 'hz']):
                            print(f"  [MATCH] Contains measurement keywords")
                        
                    except Exception as e:
                        print(f"  Failed to decode {encoding}: {e}")
            
            print()
            
        except Exception as e:
            print(f"  Error: {e}")
            print()

def test_quick_connect():
    """Test with most common baud rates quickly."""
    from src.infrastructure.usb_multimeter import USBMultimeterClient
    
    print("Testing USBMultimeterClient with different baud rates...")
    
    for baud in [2400, 9600, 19200]:
        print()
        print(f"  Baud rate: {baud}")
        
        client = USBMultimeterClient(port="COM8", baud_rate=baud)
        if client.connect():
            reading = client.read_measurement(timeout=2.0)
            
            if reading:
                print(f"    Success! {reading}")
            else:
                print(f"    No valid reading received")
                
            client.disconnect()
        else:
            print(f"    Failed to connect")

if __name__ == "__main__":
    # First test all possible baud rates
    test_baud_rates()
    
    # Then test with USBMultimeterClient
    test_quick_connect()
