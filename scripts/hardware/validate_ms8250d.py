"""
Validator and live mode test script for MS8250D multimeter.

Two-phase behavior:
1) Offline parser tests using synthetically built 18-byte frames.
2) Live manual mode sweep and capture with USBMultimeterClient.
"""

import math
import sys
import time

sys.path.insert(0, '.')
from src.infrastructure.usb_multimeter import (
    MultimeterReading,
    MastechMS8250DParser,
    USBMultimeterClient,
)


# =============================================================================
# Frame builder — reverse-engineers byte encoding from desired digit values
# =============================================================================

# Reverse lookup: digit value → 11-bit word for main display
_DIGIT_TO_WORD = {v: k for k, v in MastechMS8250DParser.DIGITS_MAIN.items()}


def build_frame(
    digits=(0, 0, 0, 0),
    decimal_pos=0,       # 0=none, 1=X.XXX, 2=XX.XX, 3=XXX.X
    dc=False, ac=False,
    volt=False, ohm=False, ampere=False, hz=False, farad=False,
    diode=False, beep=False,
    negative=False,
    milli=False, kilo=False, mega=False, micro=False, nano=False,
) -> bytes:
    """
    Build a valid 18-byte MS8250D frame from human-readable parameters.

    ``digits`` is a 4-tuple of main-display digit values (0-9, or 0xF for OL).
    The builder encodes them into the correct byte positions, sets the RS232
    flag (required by flags_valid), and applies all requested mode/multiplier
    flags.
    """
    buf = bytearray(18)

    # RS232 flag — mandatory for a valid frame
    buf[1] |= (1 << 1)

    # --- Encode the four main-display digits ---
    d1, d2, d3, d4 = digits
    w1, w2, w3, w4 = (_DIGIT_TO_WORD[d] for d in (d1, d2, d3, d4))

    # d1 → buf[2] bits 4-5, buf[3] bits 0-2 and 4-5
    buf[3] |= (w1 >> 8) & 0x07
    buf[2] |= w1 & 0x30
    buf[3] |= (w1 & 0x03) << 4

    # d2 → buf[4] bits matching 0x73 mask, buf[5] bits 0-1
    buf[4] |= (w2 >> 4) & 0x73
    buf[5] |= w2 & 0x03

    # d3 → buf[5] bits 4-5, buf[6] bits 0-2 and 4-5
    buf[6] |= (w3 >> 8) & 0x07
    buf[5] |= w3 & 0x30
    buf[6] |= (w3 & 0x03) << 4

    # d4 → buf[7] bits matching 0x73 mask, buf[8] bits 0-1
    buf[7] |= (w4 >> 4) & 0x73
    buf[8] |= w4 & 0x03

    # --- Decimal point position ---
    if decimal_pos == 1:    # X.XXX
        buf[3] |= (1 << 6)
    elif decimal_pos == 2:  # XX.XX
        buf[5] |= (1 << 6)
    elif decimal_pos == 3:  # XXX.X
        buf[7] |= (1 << 2)

    # --- AC / DC ---
    if ac:
        buf[1] |= (1 << 4)
    if dc:
        buf[2] |= (1 << 1)

    # --- Measurement type ---
    if volt:
        buf[9] |= (1 << 4)
    if ohm:
        buf[9] |= (1 << 6)
    if ampere:
        buf[10] |= (1 << 0)
    if hz:
        buf[10] |= (1 << 2)
    if farad:
        buf[10] |= (1 << 1)
    if diode:
        buf[11] |= (1 << 0)
    if beep:
        buf[11] |= (1 << 1)

    # --- Multipliers ---
    if milli:
        buf[9] |= (1 << 0)
    if kilo:
        buf[9] |= (1 << 2)
    if mega:
        buf[8] |= (1 << 6)
    if micro:
        if farad:
            buf[9] |= (1 << 1)
        else:
            buf[8] |= (1 << 4)
    if nano:
        buf[8] |= (1 << 5)

    # --- Sign ---
    if negative:
        buf[0] |= (1 << 2)

    return bytes(buf)


# =============================================================================
# Offline parser unit tests
# =============================================================================

def run_unit_tests() -> bool:
    print("=== Unit Tests: MastechMS8250DParser ===\n")
    passed = 0
    failed = 0

    def check(label, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {label}")
            passed += 1
        else:
            print(f"  [FAIL] {label}  {detail}")
            failed += 1

    # ------------------------------------------------------------------
    # 1. DC Voltage 310.0 V  (C1 bus capacitor reading)
    # ------------------------------------------------------------------
    frame = build_frame(digits=(3, 1, 0, 0), decimal_pos=3, dc=True, volt=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("DC 310.0V parses", r is not None)
    if r:
        check("DC 310.0V value",  abs(r.value - 310.0) < 0.01, f"got {r.value}")
        check("DC 310.0V unit",   r.unit == "V", f"got {r.unit}")
        check("DC 310.0V type",   r.measurement_type == "DC_VOLTAGE", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 2. DC Voltage 3.100 V  (low voltage)
    # ------------------------------------------------------------------
    frame = build_frame(digits=(3, 1, 0, 0), decimal_pos=1, dc=True, volt=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("DC 3.100V parses", r is not None)
    if r:
        check("DC 3.100V value", abs(r.value - 3.100) < 0.001, f"got {r.value}")
        check("DC 3.100V type",  r.measurement_type == "DC_VOLTAGE", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 3. AC Voltage 12.05 V
    # ------------------------------------------------------------------
    frame = build_frame(digits=(1, 2, 0, 5), decimal_pos=2, ac=True, volt=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("AC 12.05V parses", r is not None)
    if r:
        check("AC 12.05V value", abs(r.value - 12.05) < 0.01, f"got {r.value}")
        check("AC 12.05V type",  r.measurement_type == "AC_VOLTAGE", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 4. Resistance 4.700 kΩ → stored as 4700 Ω
    # ------------------------------------------------------------------
    frame = build_frame(digits=(4, 7, 0, 0), decimal_pos=1, ohm=True, kilo=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("4.700kΩ parses", r is not None)
    if r:
        check("4.700kΩ value", abs(r.value - 4700.0) < 0.1, f"got {r.value}")
        check("4.700kΩ unit",  r.unit == "Ω", f"got {r.unit}")
        check("4.700kΩ type",  r.measurement_type == "RESISTANCE", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 5. Continuity 0.32 Ω (short circuit reading)
    # ------------------------------------------------------------------
    frame = build_frame(digits=(0, 0, 3, 2), decimal_pos=2, beep=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("Continuity 0.32Ω parses", r is not None)
    if r:
        check("Continuity value", abs(r.value - 0.32) < 0.01, f"got {r.value}")
        check("Continuity type",  r.measurement_type == "CONTINUITY", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 6. Diode forward drop 0.650 V
    # ------------------------------------------------------------------
    frame = build_frame(digits=(0, 6, 5, 0), decimal_pos=1, diode=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("Diode 0.650V parses", r is not None)
    if r:
        check("Diode value", abs(r.value - 0.650) < 0.001, f"got {r.value}")
        check("Diode type",  r.measurement_type == "DIODE", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 7. Negative DC voltage -5.23 V
    # ------------------------------------------------------------------
    frame = build_frame(digits=(0, 5, 2, 3), decimal_pos=2, dc=True, volt=True, negative=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("Negative -5.23V parses", r is not None)
    if r:
        check("Negative value", abs(r.value - (-5.23)) < 0.01, f"got {r.value}")
        check("Negative sign",  r.value < 0, f"got {r.value}")

    # ------------------------------------------------------------------
    # 8. Overflow (OL) — digit3 == 0xF → value = inf
    # ------------------------------------------------------------------
    frame = build_frame(digits=(0, 0, 0xF, 0), decimal_pos=0, ohm=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("Overflow parses", r is not None)
    if r:
        check("Overflow value is inf", math.isinf(r.value), f"got {r.value}")

    # ------------------------------------------------------------------
    # 9. DC Current 0.250 A with milli prefix → 0.250 mA = 0.000250 A
    # ------------------------------------------------------------------
    frame = build_frame(digits=(0, 2, 5, 0), decimal_pos=1, dc=True, ampere=True, milli=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("DC 0.250mA parses", r is not None)
    if r:
        expected = 0.250e-3  # 0.250 * 10^(-3 + -3) = 0.250 * 10^-6? No...
        # digits = 0250 = 250, decimal_pos=1 → exponent=-3, milli → exponent-=3 → -6
        # value = 250 * 10^-6 = 0.000250
        check("DC 0.250mA value", abs(r.value - 0.000250) < 1e-7, f"got {r.value}")
        check("DC 0.250mA type",  r.measurement_type == "DC_CURRENT", f"got {r.measurement_type}")

    # ------------------------------------------------------------------
    # 10. Frequency 1.234 kHz → 1234 Hz
    # ------------------------------------------------------------------
    frame = build_frame(digits=(1, 2, 3, 4), decimal_pos=1, hz=True, kilo=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("1.234kHz parses", r is not None)
    if r:
        check("1.234kHz value", abs(r.value - 1234.0) < 0.1, f"got {r.value}")
        check("1.234kHz unit",  r.unit == "Hz", f"got {r.unit}")

    # ------------------------------------------------------------------
    # 11. Capacitance 4.700 nF → 4.7e-9 F
    # ------------------------------------------------------------------
    frame = build_frame(digits=(4, 7, 0, 0), decimal_pos=1, farad=True, nano=True)
    r = MastechMS8250DParser.parse_frame(frame)
    check("4.700nF parses", r is not None)
    if r:
        check("4.700nF value", abs(r.value - 4.7e-9) < 1e-11, f"got {r.value}")
        check("4.700nF unit",  r.unit == "F", f"got {r.unit}")

    # ------------------------------------------------------------------
    # 12. MultimeterReading.to_dict()
    # ------------------------------------------------------------------
    reading = MultimeterReading(
        raw_value="DEADBEEF", value=12.34, unit="V",
        measurement_type="DC_VOLTAGE", timestamp="2025-01-01T00:00:00",
        test_point_id="TP2", secondary_value=50.0, secondary_unit="Hz"
    )
    d = reading.to_dict()
    check("to_dict test_point",     d["test_point"] == "TP2")
    check("to_dict value",          d["value"] == 12.34)
    check("to_dict secondary",      d.get("secondary_value") == 50.0)

    reading_no_sec = MultimeterReading(
        raw_value="AA", value=1.0, unit="V",
        measurement_type="DC_VOLTAGE", timestamp="t"
    )
    d2 = reading_no_sec.to_dict()
    check("to_dict no secondary",   "secondary_value" not in d2)
    check("to_dict default tp",     d2["test_point"] == "MM1")

    # ------------------------------------------------------------------
    # 13. Invalid frames — parser must return None
    # ------------------------------------------------------------------
    check("None for short frame",   MastechMS8250DParser.parse_frame(b'\x00' * 10) is None)
    check("None for empty",         MastechMS8250DParser.parse_frame(b'') is None)

    # Both AC and DC → flags_valid rejects
    bad = build_frame(digits=(1, 0, 0, 0), dc=True, ac=True, volt=True)
    check("Reject AC+DC",           MastechMS8250DParser.parse_frame(bad) is None)

    # Two measurement types → flags_valid rejects
    bad = build_frame(digits=(1, 0, 0, 0), dc=True, volt=True, ohm=True)
    check("Reject volt+ohm",        MastechMS8250DParser.parse_frame(bad) is None)

    # Two multipliers → flags_valid rejects
    bad = build_frame(digits=(1, 0, 0, 0), dc=True, volt=True, kilo=True, milli=True)
    check("Reject kilo+milli",      MastechMS8250DParser.parse_frame(bad) is None)

    # No RS232 flag → rejected
    no_rs232 = bytearray(build_frame(digits=(1, 0, 0, 0), dc=True, volt=True))
    no_rs232[1] &= ~(1 << 1)  # clear RS232 bit
    check("Reject no RS232",        MastechMS8250DParser.parse_frame(bytes(no_rs232)) is None)

    # ------------------------------------------------------------------
    # 14. USBMultimeterClient._parse_binary_frame — sliding window
    # ------------------------------------------------------------------
    client = USBMultimeterClient.__new__(USBMultimeterClient)  # no __init__ / no serial
    valid_frame = build_frame(digits=(2, 4, 0, 0), decimal_pos=2, dc=True, volt=True)

    # Exact 18 bytes
    r = client._parse_binary_frame(valid_frame)
    check("Sliding window exact",   r is not None and abs(r.value - 24.00) < 0.01,
          f"got {r.value if r else None}")

    # Padded with garbage — frame embedded at offset 5
    padded = b'\xff' * 5 + valid_frame + b'\xff' * 5
    r = client._parse_binary_frame(padded)
    check("Sliding window padded",  r is not None and abs(r.value - 24.00) < 0.01,
          f"got {r.value if r else None}")

    # All garbage — should return None
    r = client._parse_binary_frame(b'\xff' * 36)
    check("Sliding window garbage", r is None)

    # Too short — should return None
    r = client._parse_binary_frame(b'\x00' * 10)
    check("Sliding window short",   r is None)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = passed + failed
    print(f"\n=== Results: {passed}/{total} passed", end="")
    if failed:
        print(f", {failed} FAILED ===\n")
    else:
        print(" ===\n")
    return failed == 0


# =============================================================================
# Live tests (require connected multimeter)
# =============================================================================

def run_live_switch_test(client: USBMultimeterClient):
    print('=== Live Mode Switch Test ===')

    mode_instructions = [
        ('DC_VOLTAGE', 'Set meter to DC voltage mode and measure a DC source.'),
        ('AC_VOLTAGE', 'Set meter to AC voltage mode and measure an AC source.'),
        ('DC_CURRENT', 'Set meter to DC current mode and measure a small current.'),
        ('RESISTANCE', 'Set meter to resistance mode and measure a resistor.'),
        ('CONTINUITY', 'Set meter to continuity mode and short probes.'),
        ('DIODE', 'Set meter to diode mode and probe diode forward drop.'),
    ]

    for expected_mode, instruction in mode_instructions:
        input(f"\n{instruction}\nPress Enter when ready to sample...")

        # Discard one sample to avoid previous-mode residue
        _ = client.read_measurement(timeout=1.0)
        time.sleep(0.2)

        final_reading = None
        for attempt in range(1, 4):
            reading = client.read_measurement(timeout=2.0)
            if not reading:
                print(f'  [ATTEMPT {attempt}] no reading')
                continue

            value_str = f"{reading.value:.6g}"
            unit = reading.unit or '??'
            match = expected_mode in reading.measurement_type

            print(f"  [ATTEMPT {attempt}] Raw frame: {reading.raw_value}")
            print(f"  [ATTEMPT {attempt}] {value_str} {unit} -> {reading.measurement_type}"
                  f" | expected {expected_mode} | match={match}")

            if match:
                final_reading = reading
                break
            final_reading = reading

        if final_reading is None:
            print(f'  [RESULT] no valid reading for {expected_mode}')
        else:
            value_str = f"{final_reading.value:.6g}"
            unit = final_reading.unit or '??'
            match = expected_mode in final_reading.measurement_type
            print(f"  [RESULT] {value_str} {unit} -> {final_reading.measurement_type}"
                  f" | expected {expected_mode} | match={match}")

    print('=== Live Mode Switch Test Complete ===\n')


def run_live_capture_test(client: USBMultimeterClient, sample_count: int = 10):
    print('=== Live Capture Test ===')

    readings = []
    for i in range(sample_count):
        r = client.read_measurement(timeout=3.0)
        if r:
            readings.append(r.value)
            print(f"  [{i+1}] {r.value:.6g} {r.unit} ({r.measurement_type})")
        else:
            print(f"  [{i+1}] no reading")

    if readings:
        avg = sum(readings) / len(readings)
        print(f"  stats: count={len(readings)} min={min(readings):.6g}"
              f" max={max(readings):.6g} avg={avg:.6g}")

    print('=== Live Capture Test Complete ===\n')


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    # Phase 1: Offline unit tests (always run)
    unit_ok = run_unit_tests()
    if not unit_ok:
        print('Some unit tests failed — review parser digit mappings.\n')

    # Phase 2: Live tests (only if --live flag passed)
    if '--live' not in sys.argv:
        print('Skipping live tests. Pass --live to run them.')
        sys.exit(0 if unit_ok else 1)

    print('\nAvailable serial ports:')
    ports = USBMultimeterClient.list_available_ports()
    if ports:
        for port in ports:
            print(f'  {port}')
    else:
        print('  (none found)')

    detected = USBMultimeterClient.detect_multimeter()
    print(f'Auto-detected multimeter port: {detected or "(none)"}')

    client = USBMultimeterClient(port=detected)
    if not client.connect():
        print('Failed to connect — check multimeter is connected via USB')
        sys.exit(1)

    try:
        run_live_switch_test(client)
        run_live_capture_test(client, sample_count=10)
    finally:
        client.disconnect()
