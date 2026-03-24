"""
Test script for MS8250D Multimeter - Raw frames + Parsed values.

Shows detailed frame analysis to verify correct operation.
"""

import sys
sys.path.insert(0, '.')
from src.infrastructure.usb_multimeter import USBMultimeterClient, MS8250DParser
import time

print('=== MS8250D Multimeter Test ===')
print('Connecting to multimeter...')

client = USBMultimeterClient()

if client.connect():
    print(f'Connected on {client.port}')

    # Phase 1: Raw frame dump for diagnostics
    print('\n--- Raw Frame Dump (5 frames) ---')
    for i in range(5):
        frame = client.read_raw_frame(timeout=3.0)
        if frame:
            hex_str = ' '.join(f'{b:02X}' for b in frame)
            valid = MS8250DParser.validate_frame(frame)
            phase = MS8250DParser.classify_phase(frame)
            print(f'  Frame {i}: [{hex_str}]  phase={phase}  valid={valid}')
        else:
            print(f'  Frame {i}: (timeout)')

    # Phase 2: Parsed measurements
    print(f'\n--- Parsed Measurements (10 readings) ---')
    print('-' * 60)

    for i in range(10):
        reading = client.read_measurement(timeout=3.0)
        if reading:
            unit = reading.unit
            if unit == '\u03a9':
                unit = 'ohm'

            value = reading.value
            multiplier = ''
            if abs(value) >= 1000000:
                multiplier = 'M'
                value = value / 1000000
            elif abs(value) >= 1000:
                multiplier = 'k'
                value = value / 1000

            print(f'  [{i+1:2d}] >>> {value:.4f} {multiplier}{unit} [{reading.measurement_type}]')
        else:
            print(f'  [{i+1:2d}] >>> (waiting for reading...)')

    client.disconnect()
else:
    print('Failed to connect - check multimeter is connected via USB')
    sys.exit(1)