#!/usr/bin/env python3
"""
Test script to read from USB multimeter.
Continuously reads and displays any data received.
"""
import serial
import time
import sys

def test_multimeter(port='COM8', baud_rates=[2400, 9600, 115200, 19200]):
    """Test connection to multimeter at various baud rates."""
    
    print(f"Testing multimeter on {port}")
    print(f"Trying baud rates: {baud_rates}")
    print("-" * 50)
    
    for baud in baud_rates:
        print(f"\nTrying baud rate {baud}...")
        try:
            ser = serial.Serial(port, baud, timeout=2)
            print(f"  Port opened at {baud} baud")
            
            # Wait and read
            start_time = time.time()
            received_data = []
            
            while time.time() - start_time < 3:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    received_data.append(data)
                    print(f"  Received: {data}")
                
                # Check for quit
                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                    line = sys.stdin.readline()
                    if line.strip().lower() == 'q':
                        ser.close()
                        return
                
                time.sleep(0.1)
            
            if received_data:
                print(f"  SUCCESS! Data received at {baud} baud")
                ser.close()
                return baud
            
            ser.close()
            print(f"  No data at {baud} baud")
            
        except serial.SerialException as e:
            print(f"  Error at {baud} baud: {e}")
    
    print("\n" + "=" * 50)
    print("No data received at any baud rate.")
    print("Possible causes:")
    print("  1. Multimeter is not transmitting data")
    print("  2. Data output is disabled on the multimeter")
    print("  3. Multimeter needs to be in measurement mode")
    print("\nTry pressing the DATA button on your multimeter")
    print("and then take a measurement.")
    
    return None

if __name__ == "__main__":
    import select
    
    port = sys.argv[1] if len(sys.argv) > 1 else 'COM8'
    print("Press 'q' and Enter to quit")
    print("")
    
    test_multimeter(port)
