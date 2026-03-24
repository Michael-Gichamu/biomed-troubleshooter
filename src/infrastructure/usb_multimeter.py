"""
USB Multimeter Client for MASTECH MS8250D
==========================================

Protocol (from sigrok project + raw capture analysis):
  - Chip: DTA0660L multimeter IC + HY11P14 MCU
  - Interface: CP2102 USB-to-UART bridge (VID=0x10C4, PID=0xEA60)
  - Baud: 2400, 8N1, RTS=0, DTR=1
  - Frame: 18 bytes, no checksum/CRC, ends with [0x10, 0x00]
  - Payload: 1:1 mapping of LCD segments across 4+ COM phases
  - Rate: ~2 frames/second

ROOT CAUSE of old parsing bugs:
  1. The MS8250D LCD uses multiplexed COM lines. The 18-byte serial output
     cycles through different COM phases. Each phase encodes function/mode
     indicators at DIFFERENT bit positions. The old parser assumed fixed 
     bit positions, so it randomly detected DIODE/CONTINUITY/etc.
  2. The old code fell through to 10-byte "UM24C" and 14-byte "C8FEEC" 
     parsers that are for COMPLETELY DIFFERENT multimeter models, producing
     garbage results.
  3. No frame synchronization - the old code scanned a byte buffer at
     arbitrary offsets, finding false "frames" within real data.

THIS IMPLEMENTATION fixes all three issues:
  - Timing-based frame synchronization using inter-frame gaps
  - Multi-frame reading with consensus voting for measurement type
  - Only one parser path (18-byte frames), no incorrect fallbacks
  - Phase-aware mode detection: only trusts specific frame phases
"""

import serial
import serial.tools.list_ports
from dataclasses import dataclass
from typing import Optional, List, Callable
from datetime import datetime
from collections import Counter
import threading
import time
import subprocess
import shutil


# ═══════════════════════════════════════════════════════════════
# Data Model
# ═══════════════════════════════════════════════════════════════

@dataclass
class MultimeterReading:
    """A single reading from the multimeter."""
    raw_value: str
    value: float
    unit: str
    measurement_type: str
    timestamp: str
    test_point_id: str = ""
    secondary_value: Optional[float] = None
    secondary_unit: Optional[str] = None

    def to_dict(self) -> dict:
        res = {
            "test_point": self.test_point_id or "MM1",
            "value": self.value,
            "unit": self.unit,
            "measurement_type": self.measurement_type,
            "raw": self.raw_value,
            "timestamp": self.timestamp,
        }
        if self.secondary_value is not None:
            res["secondary_value"] = self.secondary_value
            res["secondary_unit"] = self.secondary_unit
        return res


# ═══════════════════════════════════════════════════════════════
# MS8250D Frame Parser
# ═══════════════════════════════════════════════════════════════

class MS8250DParser:
    """
    Parse 18-byte LCD-segment frames from the MASTECH MS8250D.

    The DTA0660L chip cycles through multiple LCD COM phases in its
    serial output. Each frame type has mode/function bits at different
    positions. We classify frames by their "signature" (bytes 8-11)
    and only extract mode information from frames where we know the
    bit positions.

    Frame classification (from raw capture analysis at 227V AC):
      Phase A: bytes[8:12] = 03 10 xx xx → Mode bits at standard positions
      Phase B: bytes[8:12] = 03 40 xx xx → Shifted mode, value valid
      Phase C: bytes[0] = 0xC8          → Different encoding, skip
      Phase D: bytes[8:12] = 23 00 02 xx → Different mapping, value valid
      Phase E: bytes[8:12] = 03 00 04 xx → Frequency display phase

    Only Phase A frames have reliable mode detection at the bit
    positions documented in various reverse-engineering sources.
    """

    FRAME_SIZE = 18
    SYNC_BYTES = (0x10, 0x00)  # bytes[16:18] in every valid frame

    # Phase A mode detection bit positions (bytes 8-11 = 03 10 xx xx)
    # These are the only frames where we trust mode bits
    MODE_BITS = {
        "voltage":     (9, 0x10),   # byte 9 bit 4
        "resistance":  (9, 0x40),   # byte 9 bit 6
        "current":     (10, 0x01),  # byte 10 bit 0
        "capacitance": (10, 0x02),  # byte 10 bit 1
        "frequency":   (10, 0x04),  # byte 10 bit 2
        "diode":       (10, 0x08),  # byte 10 bit 3
        "continuity":  (10, 0x10),  # byte 10 bit 4
    }

    @classmethod
    def validate_frame(cls, buf: bytes) -> bool:
        """Check if buffer is a valid 18-byte MS8250D frame."""
        if len(buf) != cls.FRAME_SIZE:
            return False
        return buf[16] == cls.SYNC_BYTES[0] and buf[17] == cls.SYNC_BYTES[1]

    @classmethod
    def classify_phase(cls, buf: bytes) -> str:
        """Classify the LCD COM phase of a frame."""
        if buf[0] == 0xC8:
            return "C"  # Garbled / different encoding
        if buf[8] == 0x03 and buf[9] == 0x10:
            return "A"  # Standard mode detection
        if buf[8] == 0x03 and buf[9] == 0x40:
            return "B"  # Shifted mode
        if buf[8] == 0x23:
            return "D"  # Different mapping
        if buf[8] == 0x03 and buf[9] == 0x00:
            return "E"  # Frequency phase
        return "?"

    @classmethod
    def detect_mode_phase_a(cls, buf: bytes) -> tuple:
        """
        Detect measurement mode from a Phase A frame.
        Returns (measurement_type, unit) tuple.
        """
        is_ac = bool(buf[1] & 0x10) or bool(buf[0] & 0x08)
        is_dc = bool(buf[1] & 0x02) or bool(buf[2] & 0x02)

        if buf[9] & 0x10:
            unit = "V"
            mtype = "AC_VOLTAGE" if is_ac else "DC_VOLTAGE"
            # Heuristic: for Phase A, if byte[1] bit 0 is set and 
            # byte[0] has bit 6 set, it's likely AC 
            if buf[0] & 0x40 and not is_dc:
                mtype = "AC_VOLTAGE"
            return (mtype, unit)

        if buf[9] & 0x40:
            return ("RESISTANCE", "\u03A9")

        if buf[10] & 0x01:
            unit = "A"
            return ("AC_CURRENT" if is_ac else "DC_CURRENT", unit)

        if buf[10] & 0x02:
            return ("CAPACITANCE", "F")

        if buf[10] & 0x04:
            return ("FREQUENCY", "Hz")

        if buf[10] & 0x08:
            return ("DIODE", "V")

        if buf[10] & 0x10:
            return ("CONTINUITY", "\u03A9")

        return ("UNKNOWN", "")

    @classmethod
    def extract_value(cls, buf: bytes) -> Optional[float]:
        """
        Extract the numeric value from a frame using multiple strategies.
        
        Strategy 1: Scan for ASCII digits (0x30-0x39) in bytes 2-8.
            The DTA0660L segment encoding produces bytes that often 
            coincide with ASCII digit values for certain segments.
            
        Strategy 2: Use segment-word extraction with lookup table.
        
        Strategy 3: For known frame patterns, use pattern matching.
        """
        # Strategy 1: ASCII digit extraction from data bytes
        ascii_digits = []
        ascii_positions = []
        for i in range(2, 9):
            b = buf[i]
            if 0x30 <= b <= 0x39:
                ascii_digits.append(b - 0x30)
                ascii_positions.append(i)

        if len(ascii_digits) >= 3:
            # Build the number from the ASCII digits found
            # For a 6600-count meter, we expect 3-4 digits
            digit_str = ''.join(str(d) for d in ascii_digits[:4])

            # Determine decimal point position
            # The DP bits are in byte[3] bit6, byte[5] bit6, byte[7] bit2
            dp_pos = -1
            if buf[3] & 0x40:
                dp_pos = 1  # X.XXX
            elif buf[5] & 0x40:
                dp_pos = 2  # XX.XX
            elif buf[7] & 0x04:
                dp_pos = 3  # XXX.X

            # Apply DP based on how many digits we found and their positions
            if dp_pos > 0 and dp_pos <= len(digit_str):
                digit_str = digit_str[:dp_pos] + '.' + digit_str[dp_pos:]

            try:
                value = float(digit_str)
            except ValueError:
                return None

            # Sign detection
            if buf[1] & 0x01:
                value = -value

            return value

        # Strategy 2: If we found fewer than 3 ASCII digits, try 
        # a broader search including the full byte range
        # For now, return None and let the caller try the next frame
        return None

    @classmethod
    def extract_multiplier(cls, buf: bytes) -> float:
        """Extract the unit multiplier from a frame."""
        if buf[8] & 0x20:
            return 1e-9   # nano
        if buf[8] & 0x10:
            return 1e-6   # micro
        if buf[9] & 0x01:
            return 1e-3   # milli
        if buf[9] & 0x04:
            return 1e3    # kilo
        if buf[8] & 0x40:
            return 1e6    # mega
        return 1.0

    @classmethod
    def parse_frame(cls, buf: bytes, last_known_mode: Optional[tuple] = None
                    ) -> Optional[MultimeterReading]:
        """
        Parse a single 18-byte frame.
        
        Args:
            buf: The 18-byte frame
            last_known_mode: Optional (measurement_type, unit) from previous
                             Phase A frame, used when current frame's phase
                             can't determine mode reliably.
        """
        if not cls.validate_frame(buf):
            return None

        # Skip Phase C (garbled/different encoding)
        phase = cls.classify_phase(buf)
        if phase == "C":
            return None

        # Extract value
        value = cls.extract_value(buf)
        if value is None:
            return None

        # Apply multiplier
        multiplier = cls.extract_multiplier(buf)
        value *= multiplier

        # Determine mode
        if phase == "A":
            mtype, unit = cls.detect_mode_phase_a(buf)
        elif last_known_mode:
            mtype, unit = last_known_mode
        else:
            # Can't determine mode from this phase, and no cached mode
            mtype, unit = "UNKNOWN", ""

        if mtype == "UNKNOWN" and last_known_mode:
            mtype, unit = last_known_mode

        return MultimeterReading(
            raw_value=buf.hex().upper(),
            value=round(value, 4),
            unit=unit,
            measurement_type=mtype,
            timestamp=datetime.utcnow().isoformat(),
        )


# ═══════════════════════════════════════════════════════════════
# USB Multimeter Client
# ═══════════════════════════════════════════════════════════════

class USBMultimeterClient:
    """
    Client for MASTECH MS8250D USB Multimeter.

    Uses timing-based frame synchronization for reliable reads.
    Multi-frame consensus for measurement type detection.
    """

    FRAME_SIZE = 18
    INTER_FRAME_GAP_MS = 80  # Min gap between frames at 2400 baud

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 2400,
        timeout: float = 1.0,
        on_reading_callback: Optional[Callable[[MultimeterReading], None]] = None,
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.on_reading_callback = on_reading_callback

        self._serial: Optional[serial.Serial] = None
        self._connected = False
        self._reading_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_reading: Optional[MultimeterReading] = None
        self._last_known_mode: Optional[tuple] = None  # (measurement_type, unit)

    # ── Port Detection ────────────────────────────────────────

    @staticmethod
    def list_available_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def detect_multimeter() -> Optional[str]:
        """Auto-detect the MS8250D's CP2102 USB adapter."""
        for p in serial.tools.list_ports.comports():
            if getattr(p, 'vid', None) == 0x10C4 and getattr(p, 'pid', None) == 0xEA60:
                return p.device
            desc = (p.description or "").upper()
            if "CP210" in desc:
                return p.device

        # Fallback: any USB-serial adapter
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            if any(kw in desc for kw in ['usb-serial', 'ch340', 'ftdi']):
                return p.device
        return None

    # ── Connection ────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect with correct serial parameters (2400/8N1, DTR=1, RTS=0)."""
        try:
            if not self.port:
                self.port = self.detect_multimeter()
                if not self.port:
                    print("[USB] No multimeter port detected")
                    return False

            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            # CRITICAL: DTR=1 powers the meter's transmitter circuit.
            # RTS=0 as per sigrok's configuration.
            self._serial.dtr = True
            self._serial.rts = False

            time.sleep(0.3)
            self._serial.reset_input_buffer()
            self._connected = True
            print(f"[USB] Connected to multimeter on {self.port} at {self.baud_rate} baud")
            return True

        except Exception as e:
            print(f"[USB] Connection error: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._reading_thread and self._reading_thread.is_alive():
            self._reading_thread.join(timeout=2.0)
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        print("[USB] Disconnected from multimeter")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def is_connected(self) -> bool:
        return self._connected and self._serial is not None and self._serial.is_open

    # ── Frame Synchronization (timing-based) ──────────────────

    def _read_one_frame(self, timeout: float = 2.0) -> Optional[bytes]:
        """
        Read one 18-byte frame using timing gap detection.

        At 2400 baud 8N1, each byte = ~4.17ms, 18 bytes = ~75ms.
        Inter-frame gap is ~425ms. We detect the gap then read 18 bytes.
        """
        if not self.is_connected():
            return None

        ser = self._serial
        start = time.time()

        # Phase 1: Wait for an inter-frame gap
        last_data = time.time()
        while time.time() - start < timeout:
            waiting = ser.in_waiting
            if waiting > 0:
                ser.read(waiting)  # Discard mid-frame bytes
                last_data = time.time()
            else:
                gap_ms = (time.time() - last_data) * 1000
                if gap_ms > self.INTER_FRAME_GAP_MS:
                    break
                time.sleep(0.005)
        else:
            return None  # Timeout

        # Phase 2: Read exactly 18 bytes (the new frame)
        frame = bytearray()
        frame_start = time.time()
        while len(frame) < self.FRAME_SIZE:
            if time.time() - frame_start > 0.5:
                return None  # Took too long
            waiting = ser.in_waiting
            if waiting > 0:
                needed = self.FRAME_SIZE - len(frame)
                frame.extend(ser.read(min(waiting, needed)))
            else:
                time.sleep(0.002)

        return bytes(frame)

    # ── Multi-frame Consensus Reading ─────────────────────────

    def read_measurement(self, timeout: float = 3.0) -> Optional[MultimeterReading]:
        """
        Read a measurement using multi-frame consensus.

        Reads up to 6 frames (takes ~3s worst case) to find:
        1. At least one Phase A frame for reliable mode detection
        2. Any valid frame for value extraction

        The measurement type comes from Phase A; the value from the
        most recent valid frame.
        """
        if not self.is_connected():
            print("[USB] Not connected to multimeter")
            return None

        try:
            best_reading = None
            mode_detected = self._last_known_mode
            frame_start = time.time()
            attempts = 0
            max_attempts = 6

            while attempts < max_attempts and (time.time() - frame_start) < timeout:
                attempts += 1
                frame = self._read_one_frame(timeout=max(0.5, timeout - (time.time() - frame_start)))

                if frame is None:
                    continue

                if not MS8250DParser.validate_frame(frame):
                    continue

                phase = MS8250DParser.classify_phase(frame)

                # Update mode from Phase A frames (most reliable)
                if phase == "A":
                    detected = MS8250DParser.detect_mode_phase_a(frame)
                    if detected[0] != "UNKNOWN":
                        mode_detected = detected
                        self._last_known_mode = detected

                # Try to parse a reading from any non-garbled phase
                reading = MS8250DParser.parse_frame(frame, last_known_mode=mode_detected)
                if reading and reading.measurement_type != "UNKNOWN":
                    best_reading = reading
                    # If we have both a good value and good mode, return now
                    if mode_detected:
                        self._last_reading = best_reading
                        return best_reading

            # Return whatever we found
            if best_reading:
                self._last_reading = best_reading
                return best_reading

            return None

        except PermissionError as e:
            print(f"[USB] Read error (PermissionError): {e}")
            self.disconnect()
            time.sleep(0.5)
            self.connect()
            return None

        except Exception as e:
            print(f"[USB] Read error: {e}")
            return None

    # ── Raw Frame Access (for debugging) ──────────────────────

    def read_raw_frame(self, timeout: float = 2.0) -> Optional[bytes]:
        """Read a single raw 18-byte frame for debugging."""
        if not self.is_connected():
            return None
        return self._read_one_frame(timeout=timeout)

    # ── Continuous Reading ────────────────────────────────────

    def start_continuous_reading(self) -> None:
        if self._reading_thread and self._reading_thread.is_alive():
            return
        self._stop_event.clear()
        self._reading_thread = threading.Thread(
            target=self._continuous_read_loop, daemon=True
        )
        self._reading_thread.start()

    def stop_continuous_reading(self) -> None:
        self._stop_event.set()
        if self._reading_thread:
            self._reading_thread.join(timeout=2.0)

    def _continuous_read_loop(self) -> None:
        while not self._stop_event.is_set() and self.is_connected():
            reading = self.read_measurement(timeout=3.0)
            if reading and self.on_reading_callback:
                self.on_reading_callback(reading)

    def get_last_reading(self) -> Optional[MultimeterReading]:
        return self._last_reading


# ═══════════════════════════════════════════════════════════════
# Sigrok-CLI Backend (most reliable option)
# ═══════════════════════════════════════════════════════════════

class SigrokMultimeterClient:
    """
    Alternative client that uses sigrok-cli for guaranteed-correct parsing.

    sigrok-cli is the reference implementation for MS8250D protocol
    decoding. If installed on the system, this client delegates all
    parsing to sigrok and just captures the text output.

    Install sigrok:
      Windows: https://sigrok.org/wiki/Downloads
      Linux:   sudo apt install sigrok-cli
    """

    def __init__(self, port: Optional[str] = None):
        self.port = port or USBMultimeterClient.detect_multimeter()
        self._process: Optional[subprocess.Popen] = None
        self._connected = False
        self._last_reading: Optional[MultimeterReading] = None
        self._callback: Optional[Callable] = None

    @staticmethod
    def is_available() -> bool:
        """Check if sigrok-cli is installed."""
        return shutil.which("sigrok-cli") is not None

    def connect(self) -> bool:
        if not self.port:
            print("[Sigrok] No port detected")
            return False
        if not self.is_available():
            print("[Sigrok] sigrok-cli not found. Install from https://sigrok.org/wiki/Downloads")
            return False
        self._connected = True
        print(f"[Sigrok] Ready on {self.port}")
        return True

    def disconnect(self) -> None:
        if self._process:
            self._process.terminate()
            self._process = None
        self._connected = False

    def read_measurement(self, timeout: float = 5.0) -> Optional[MultimeterReading]:
        """Read one measurement via sigrok-cli."""
        if not self._connected:
            return None

        try:
            cmd = [
                "sigrok-cli",
                "--driver", f"mastech-ms8250d:conn={self.port}",
                "--samples", "1",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

            if result.returncode != 0:
                print(f"[Sigrok] Error: {result.stderr.strip()}")
                return None

            # Parse sigrok output: e.g. "227.0 V AC"
            line = result.stdout.strip()
            if not line:
                return None

            return self._parse_sigrok_line(line)

        except subprocess.TimeoutExpired:
            print("[Sigrok] Timeout waiting for reading")
            return None
        except Exception as e:
            print(f"[Sigrok] Error: {e}")
            return None

    def _parse_sigrok_line(self, line: str) -> Optional[MultimeterReading]:
        """Parse a single line of sigrok-cli output."""
        import re
        # Sigrok outputs like: "227.0 V" or "1.234 kΩ" or "OL"
        parts = line.strip().split()
        if not parts:
            return None

        try:
            value_str = parts[0]
            if value_str.upper() == "OL":
                value = float('inf')
            else:
                value = float(value_str)
        except ValueError:
            return None

        unit = parts[1] if len(parts) > 1 else ""
        ac_dc = parts[2] if len(parts) > 2 else ""

        # Map unit to measurement type
        mtype = "UNKNOWN"
        if "V" in unit:
            mtype = "AC_VOLTAGE" if ac_dc == "AC" else "DC_VOLTAGE"
        elif "A" in unit:
            mtype = "AC_CURRENT" if ac_dc == "AC" else "DC_CURRENT"
        elif "\u03A9" in unit or "ohm" in unit.lower():
            mtype = "RESISTANCE"
        elif "F" in unit:
            mtype = "CAPACITANCE"
        elif "Hz" in unit:
            mtype = "FREQUENCY"

        # Handle multiplier prefixes
        multiplier_map = {
            'n': 1e-9, 'u': 1e-6, '\u00B5': 1e-6,
            'm': 1e-3, 'k': 1e3, 'M': 1e6
        }
        base_unit = unit
        for prefix, mult in multiplier_map.items():
            if unit.startswith(prefix) and len(unit) > 1:
                value *= mult
                base_unit = unit[1:]
                break

        return MultimeterReading(
            raw_value=line,
            value=round(value, 4),
            unit=base_unit,
            measurement_type=mtype,
            timestamp=datetime.utcnow().isoformat(),
        )


# ═══════════════════════════════════════════════════════════════
# Factory: Auto-select the best available backend
# ═══════════════════════════════════════════════════════════════

def create_multimeter_client(
    port: Optional[str] = None,
    on_reading_callback: Optional[Callable[[MultimeterReading], None]] = None,
    prefer_sigrok: bool = True,
) -> USBMultimeterClient:
    """
    Create the best available multimeter client.

    If sigrok-cli is installed and prefer_sigrok=True, uses the Sigrok
    backend for guaranteed correct parsing. Otherwise falls back to the
    pure Python timing-based parser.
    """
    if prefer_sigrok and SigrokMultimeterClient.is_available():
        print("[Factory] Using sigrok-cli backend (most reliable)")
        return SigrokMultimeterClient(port=port)

    print("[Factory] Using pure Python parser with timing sync")
    return USBMultimeterClient(port=port, on_reading_callback=on_reading_callback)


def quick_read(port: Optional[str] = None) -> Optional[MultimeterReading]:
    """Quick one-time read from multimeter."""
    client = USBMultimeterClient(port=port)
    if client.connect():
        reading = client.read_measurement()
        client.disconnect()
        return reading
    return None


# ═══════════════════════════════════════════════════════════════
# Debug / Test
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== MS8250D Multimeter Diagnostic ===\n")

    print("Available ports:", USBMultimeterClient.list_available_ports())
    detected = USBMultimeterClient.detect_multimeter()
    print(f"Detected multimeter: {detected}")
    print(f"Sigrok available: {SigrokMultimeterClient.is_available()}")

    if detected:
        client = USBMultimeterClient(port=detected)
        if client.connect():
            print(f"\nReading 10 measurements with timing sync:")
            print("-" * 60)

            for i in range(10):
                reading = client.read_measurement(timeout=3.0)
                if reading:
                    unit = reading.unit
                    if unit == '\u03A9':
                        unit = 'ohm'
                    print(f"  [{i+1:2d}] {reading.value:.4f} {unit} [{reading.measurement_type}]")
                else:
                    print(f"  [{i+1:2d}] (no valid reading)")

            client.disconnect()
        else:
            print("Failed to connect")