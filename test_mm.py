"""Test script to read from multimeter and display measurements."""
import sys
sys.path.insert(0, '.')
from src.infrastructure.usb_multimeter import USBMultimeterClient
import time

print('=== Multimeter Test ===')
print('Connecting to multimeter...')

client = USBMultimeterClient()

if client.connect():
    print(f'Connected on {client.port}')
    print('Reading 10 measurements:')
    print('-' * 50)
    
    for i in range(10):
        reading = client.read_measurement()
        if reading:
            value = reading.value
            multiplier = ''
            if reading.value >= 1000000:
                multiplier = 'M'
                value = reading.value / 1000000
            elif reading.value >= 1000:
                multiplier = 'k'
                value = reading.value / 1000
            
            unit = reading.unit
            # Replace omega with ohm for ASCII compatibility
            if unit == '\u03a9': unit = 'ohm'
            
            print(f'>>> {value:.4f} {multiplier}{unit} [{reading.measurement_type}]')
        else:
            print('>>> (waiting for reading...)')
        time.sleep(1)
    
    client.disconnect()
else:
    print('Failed to connect - check multimeter is connected via USB')
    sys.exit(1)
