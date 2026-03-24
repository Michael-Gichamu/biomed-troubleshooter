#!/usr/bin/env python3
"""
Refactored test script for usb_multimeter.py

Modes:
  --mock  → uses a fake serial port that feeds known‑good DTM0660 frames
  --live  → connects to a real meter (same behavior as before)

Examples:
  python test_mm.py --mock
  python test_mm.py --live --port COM3
  python test_mm.py --live --port /dev/ttyUSB0
"""
import sys
import argparse
import time
from typing import List

# Ensure local src is importable
sys.path.insert(0, '.')

from src.infrastructure import usb_multimeter as um  # import the module so we can monkey‑patch serial if needed
from src.infrastructure.usb_multimeter import USBMultimeterClient


UNIT_DISPLAY = {'Ω': 'ohm', 'µ': 'u'}


def fmt_reading(reading):
    value = reading.value
    prefix = ''
    if abs(value) >= 1_000_000:
        prefix = 'M'
        value /= 1_000_000
    elif abs(value) >= 1_000:
        prefix = 'k'
        value /= 1_000
    elif abs(value) < 0.001 and value != 0:
        prefix = 'u'
        value *= 1_000_000
    elif abs(value) < 1 and abs(value) >= 0.001:
        prefix = 'm'
        value *= 1_000

    unit = reading.unit
    unit = UNIT_DISPLAY.get(unit, unit)
    return f"{value:.4f} {prefix}{unit} [{reading.measurement_type}]"


# ----------------------------
# Mock serial and frame builder
# ----------------------------
# 7‑segment map used by the parser: tuple(A,B,C,D,E,F,G) → digit
_SEG_TO_DIGIT = {
    (1, 1, 1, 1, 1, 1, 0): "0",
    (0, 1, 1, 0, 0, 0, 0): "1",
    (1, 1, 0, 1, 1, 0, 1): "2",
    (1, 1, 1, 1, 0, 0, 1): "3",
    (0, 1, 1, 0, 0, 1, 1): "4",
    (1, 0, 1, 1, 0, 1, 1): "5",
    (1, 0, 1, 1, 1, 1, 1): "6",
    (1, 1, 1, 0, 0, 0, 0): "7",
    (1, 1, 1, 1, 1, 1, 1): "8",
    (1, 1, 1, 1, 0, 1, 1): "9",
}
# Build inverse mapping: digit → segments
_DIGIT_TO_SEGS = {}
for segs, ch in _SEG_TO_DIGIT.items():
    _DIGIT_TO_SEGS[ch] = segs


def _encode_four_digits_to_dtm0660_nibbles(d1, d2, d3, d4, dp_pos=None, negative=False):
    """
    Create the 15 payload nibbles n[0..14] (only some are used) for the DTM0660 mapping
    as expected by DTM0660Parser in usb_multimeter.py.

    dp_pos ∈ {None, 1, 2, 3} means a decimal point inserted after digit 1/2/3.
    """
    # Initialize all 15 payload nibbles to 0
    n = [0] * 15

    # Sign flags (in parser: is_dc/is_ac live in n[0]; minus lives in n[1] bit0)
    if negative:
        n[1] |= 0x1  # minus indicator at 0x2 group bit0

    # Helper to set a digit's A..G bits into the correct nibbles/bits
    def put_digit(pos, ch):
        # pos = 1..4
        A, B, C, D, E, F, G = _DIGIT_TO_SEGS.get(ch, (0, 0, 0, 0, 0, 0, 0))
        if pos == 1:
            # 0x2: 1A 1F 1E  -
            # 0x3: 1B 1G 1C  1D
            if A: n[1] |= 0x8
            if F: n[1] |= 0x4
            if E: n[1] |= 0x2
            if B: n[2] |= 0x8
            if G: n[2] |= 0x4
            if C: n[2] |= 0x2
            if D: n[2] |= 0x1
        elif pos == 2:
            # 0x4: 2A 2F 2E  DP1
            # 0x5: 2B 2G 2C  2D
            if A: n[3] |= 0x8
            if F: n[3] |= 0x4
            if E: n[3] |= 0x2
            if B: n[4] |= 0x8
            if G: n[4] |= 0x4
            if C: n[4] |= 0x2
            if D: n[4] |= 0x1
        elif pos == 3:
            # 0x6: 3A 3F 3E  DP2
            # 0x7: 3B 3G 3C  3D
            if A: n[5] |= 0x8
            if F: n[5] |= 0x4
            if E: n[5] |= 0x2
            if B: n[6] |= 0x8
            if G: n[6] |= 0x4
            if C: n[6] |= 0x2
            if D: n[6] |= 0x1
        elif pos == 4:
            # 0x8: 4A 4F 4E  DP3
            # 0x9: 4B 4G 4C  4D
            if A: n[7] |= 0x8
            if F: n[7] |= 0x4
            if E: n[7] |= 0x2
            if B: n[8] |= 0x8
            if G: n[8] |= 0x4
            if C: n[8] |= 0x2
            if D: n[8] |= 0x1

    put_digit(1, d1)
    put_digit(2, d2)
    put_digit(3, d3)
    put_digit(4, d4)

    # Decimal points: dp_pos is after digit 1/2/3
    if dp_pos == 1:
        n[3] |= 0x1  # DP1
    elif dp_pos == 2:
        n[5] |= 0x1  # DP2
    elif dp_pos == 3:
        n[7] |= 0x1  # DP3

    return n


def build_dtm0660_frame(
    value_str: str,
    dp_pos=None,
    *,
    ac=False,
    dc=False,
    unit="V",         # one of "V", "A", "Ω", "F", "Hz", "DIODE"
    prefix=None       # one of "M", "k", "m", "u", "n", or None
) -> bytes:
    """
    Construct a single 15‑byte DTM0660 frame that the parser can decode.

    value_str: exactly 4 digit characters 0‑9 (decimal point indicated by dp_pos)
    dp_pos: None, 1, 2, or 3 → position after digit to insert decimal point
    """
    assert len(value_str) == 4 and all(ch.isdigit() for ch in value_str), "value_str must be 4 digits"
    d1, d2, d3, d4 = list(value_str)
    n = _encode_four_digits_to_dtm0660_nibbles(d1, d2, d3, d4, dp_pos=dp_pos, negative=False)

    # AC/DC flags in n[0]
    if ac:
        n[0] |= 0x1
    if dc:
        n[0] |= 0x2

    # Unit/prefix bits per parser
    # bA = n[9]: Diode(0x8) k(0x4) n(0x2) u(0x1)
    # bB = n[10]: Beep(0x8) M(0x4) %(0x2) m(0x1)
    # bC = n[11]: Hold(?) Rel(?) Ohms(0x2) Farads(0x1)
    # bD = n[12]: LowBat(?) Hz(0x4) V(0x2) A(0x1)

    if unit == "V":
        n[12] |= 0x2
    elif unit == "A":
        n[12] |= 0x1
    elif unit == "Ω":
        n[11] |= 0x2
    elif unit == "F":
        n[11] |= 0x1
    elif unit == "Hz":
        n[12] |= 0x4
    elif unit == "DIODE":
        n[9] |= 0x8  # will be interpreted as DIODE and unit "V"

    if prefix == "M":
        n[10] |= 0x4
    elif prefix == "k":
        n[9] |= 0x4
    elif prefix == "m":
        n[10] |= 0x1
    elif prefix == "u":
        n[9] |= 0x1
    elif prefix == "n":
        n[9] |= 0x2

    # Compose 15 bytes where high nibble is index (1..F) and low nibble is payload nibble
    frame = bytearray()
    for i in range(15):
        idx = (i + 1) & 0xF
        frame.append((idx << 4) | (n[i] & 0xF))
    return bytes(frame)


def build_mock_stream() -> List[bytes]:
    """
    Build a sequence of DTM0660 frames that cover all measurement types expected by the test.
    Each frame encodes 4 digits plus an optional decimal per the parser's mapping.
    """
    frames = []

    # DC Voltage: 3.300 V  (digits "3300", decimal after d1)
    frames.append(build_dtm0660_frame("3300", dp_pos=1, dc=True, unit="V"))

    # AC Voltage: 120.0 V  (digits "1200", decimal after d3)
    frames.append(build_dtm0660_frame("1200", dp_pos=3, ac=True, unit="V"))

    # DC Current: 12.00 mA → 0.012 A (digits "1200", dp2 + 'm' prefix, unit A, DC)
    frames.append(build_dtm0660_frame("1200", dp_pos=2, dc=True, unit="A", prefix="m"))

    # AC Current: 25.00 mA → 0.025 A
    frames.append(build_dtm0660_frame("2500", dp_pos=2, ac=True, unit="A", prefix="m"))

    # Resistance: 2.200 kΩ
    frames.append(build_dtm0660_frame("2200", dp_pos=1, unit="Ω", prefix="k"))

    # Continuity (beep mode): same as resistance but with beep bit → in parser we trigger via bB(0x8)
    # We'll reuse resistance digits and set the beep bit by adjusting payload nibble n[10].
    base = bytearray(build_dtm0660_frame("0000", dp_pos=None, unit="Ω"))
    # Set bB beep bit (index 0xB → byte with high nibble 0xB is at position 10 (0‑based))
    for i in range(len(base)):
        if (base[i] >> 4) == 0xB:
            base[i] |= 0x8  # set beep bit
            break
    frames.append(bytes(base))

    # Frequency: 1000 Hz
    frames.append(build_dtm0660_frame("1000", dp_pos=None, unit="Hz"))

    # Capacitance: 10.00 µF
    frames.append(build_dtm0660_frame("1000", dp_pos=2, unit="F", prefix="u"))

    # Diode: 0.625 V
    frames.append(build_dtm0660_frame("0625", dp_pos=1, unit="DIODE"))

    # Repeat the set twice to simulate multiple samples
    return frames * 2


class FakeSerial:
    """
    Minimal serial‑like object that feeds bytes from a prepared buffer.
    Compatible with attributes/methods used by USBMultimeterClient.
    """
    def __init__(self, port=None, baudrate=2400, bytesize=8, parity='N', stopbits=1,
                 timeout=1.0, xonxoff=False, rtscts=False, dsrdtr=False):
        self.port = port or "MOCK"
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        # Prepare a concatenated byte stream of all frames
        frames = build_mock_stream()
        self._buffer = bytearray().join(frames)
        self._read_offset = 0

    @property
    def in_waiting(self):
        return len(self._buffer) - self._read_offset

    def read(self, n=1):
        if not self.is_open:
            return b""
        n = max(0, min(n, self.in_waiting))
        start = self._read_offset
        end = start + n
        self._read_offset = end
        return bytes(self._buffer[start:end])

    def close(self):
        self.is_open = False


def run_live(args):
    client = USBMultimeterClient(port=args.port)
    if client.connect():
        print(f'Connected on {client.port}')
        print('Reading 20 measurements (change modes during the test):')
        print('-' * 60)
        for _ in range(20):
            reading = client.read_measurement(timeout=2.0)
            if reading:
                print(f'>>> {fmt_reading(reading)}  raw={reading.raw_value[:28]}')
            else:
                print('>>> (no reading — check USB cable and baud rate)')
            time.sleep(1)
        client.disconnect()
        print('Done.')
    else:
        print('Failed to connect — check multimeter is connected via USB')
        sys.exit(1)


def run_mock(args):
    # Monkey‑patch the serial.Serial constructor used inside usb_multimeter.py
    # so the USBMultimeterClient will read from our FakeSerial.
    original_serial_cls = um.serial.Serial
    try:
        um.serial.Serial = FakeSerial  # replace
        client = USBMultimeterClient(port="MOCK")
        if client.connect():
            print('Connected to mock multimeter.')
            print('Reading 20 mock measurements (covering all modes):')
            print('-' * 60)
            for _ in range(20):
                reading = client.read_measurement(timeout=2.0)
                if reading:
                    print(f'>>> {fmt_reading(reading)}  raw={reading.raw_value[:28]}')
                else:
                    print('>>> (no mock reading — this should not happen)')
                time.sleep(0.2)
            client.disconnect()
            print('Done (mock).')
        else:
            print('Failed to connect to mock serial — check monkey‑patch.')
            sys.exit(1)
    finally:
        # Restore the original serial.Serial in case other tests run later
        um.serial.Serial = original_serial_cls


def main():
    parser = argparse.ArgumentParser(description="Multimeter test (live or mock)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--mock', action='store_true', help='Run against a fake serial device with generated frames')
    mode.add_argument('--live', action='store_true', help='Run against a real multimeter')
    parser.add_argument('--port', default=None, help='Serial port for live mode (e.g., COM3 or /dev/ttyUSB0)')
    args = parser.parse_args()

    print('=== Multimeter Test (refactored) ===')
    if args.mock:
        run_mock(args)
    else:
        run_live(args)


if __name__ == "__main__":
    main()