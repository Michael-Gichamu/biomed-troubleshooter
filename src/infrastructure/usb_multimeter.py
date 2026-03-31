import serial
import serial.tools.list_ports
from dataclasses import dataclass
from typing import Optional, List, Callable, Dict
from datetime import datetime
import threading
import re
import time


@dataclass
class MultimeterReading:
    """A single reading from the multimeter."""
    raw_value: str          # Raw string or hex from device
    value: float            # Numeric value
    unit: str               # Unit (V, A, OHM, Hz, etc.)
    measurement_type: str   # DC, AC, OHM, CONT, DIODE, etc.
    timestamp: str          # ISO timestamp
    test_point_id: str = "" # Optional test point identifier
    secondary_value: Optional[float] = None
    secondary_unit: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for agent consumption."""
        res = {
            "test_point": self.test_point_id or "MM1",
            "value": self.value,
            "unit": self.unit,
            "measurement_type": self.measurement_type,
            "raw": self.raw_value,
            "timestamp": self.timestamp
        }
        if self.secondary_value is not None:
            res["secondary_value"] = self.secondary_value
            res["secondary_unit"] = self.secondary_unit
        return res


class MastechMS8250DParser:
    """
    Parser for the Mastech MS8250D 18-byte binary protocol.
    Protocol: 2400 baud, 8N1, unidirectional.
    Based on libsigrok ms8250d.c implementation.
    """
    
    # 7-segment digit mapping for main display
    DIGITS_MAIN = {
        0x533: 0,
        0x003: 1,
        0x721: 2,
        0x703: 3,
        0x213: 4,
        0x712: 5,
        0x732: 6,
        0x103: 7,
        0x733: 8,
        0x713: 9,
        0x430: 0xF,  # Overflow
    }
    
    # 7-segment digit mapping for secondary display
    DIGITS_SEC = {
        0x00: 0,
        0x7D: 0,
        0x05: 1,
        0x1B: 2,
        0x1F: 3,
        0x27: 4,
        0x3E: 5,
        0x7E: 6,
        0x15: 7,
        0x7F: 8,
        0x3F: 9,
    }

    @classmethod
    def parse_main_digit(cls, word: int) -> int:
        """Parse main display digit from 11-bit word."""
        return cls.DIGITS_MAIN.get(word, -1)

    @classmethod
    def parse_sec_digit(cls, byte: int) -> int:
        """Parse secondary display digit from 7-bit byte."""
        return cls.DIGITS_SEC.get(byte & 0x7F, -1)

    @classmethod
    def parse_flags(cls, buf: bytes) -> dict:
        """Parse measurement flags from buffer."""
        flags = {
            'is_volt': bool(buf[9] & (1 << 4)),
            'is_ohm': bool(buf[9] & (1 << 6)),
            'is_ampere': bool(buf[10] & (1 << 0)),
            'is_hz': bool(buf[10] & (1 << 2)),
            'is_farad': bool(buf[10] & (1 << 1)),
            'is_micro': bool(buf[8] & (1 << 4)) if not (buf[10] & (1 << 1)) else bool(buf[9] & (1 << 1)),  # uF has different bit
            'is_nano': bool(buf[8] & (1 << 5)),
            'is_milli': bool(buf[9] & (1 << 0)),
            'is_kilo': bool(buf[9] & (1 << 2)),
            'is_mega': bool(buf[8] & (1 << 6)),
            'is_autotimer': bool(buf[1] & (1 << 0)),
            'is_rs232': bool(buf[1] & (1 << 1)),
            'is_ac': bool(buf[1] & (1 << 4)),
            'is_dc': bool(buf[2] & (1 << 1)),
            'is_auto': bool(buf[16] & (1 << 4)),
            'is_bat': bool(buf[1] & (1 << 5)),
            'is_min': bool(buf[16] & (1 << 2)),
            'is_max': bool(buf[16] & (1 << 1)),
            'is_rel': bool(buf[15] & (1 << 7)),
            'is_hold': bool(buf[16] & (1 << 3)),
            'is_diode': bool(buf[11] & (1 << 0)),
            'is_beep': bool(buf[11] & (1 << 1)),
            'is_ncv': bool(buf[0] & (1 << 0)),
        }
        return flags

    @classmethod
    def flags_valid(cls, flags: dict) -> bool:
        """Validate that flags are consistent."""
        # More than one multiplier
        multipliers = [flags['is_nano'], flags['is_micro'], flags['is_milli'], flags['is_kilo'], flags['is_mega']]
        if sum(multipliers) > 1:
            return False
        
        # More than one measurement type
        types = [flags['is_hz'], flags['is_ohm'], flags['is_farad'], flags['is_ampere'], flags['is_volt']]
        if sum(types) > 1:
            return False
        
        # Both AC and DC
        if flags['is_ac'] and flags['is_dc']:
            return False
        
        # No RS232 flag
        if not flags['is_rs232']:
            return False
        
        return True

    @classmethod
    def parse_frame(cls, buf: bytes) -> Optional[MultimeterReading]:
        if len(buf) != 18:
            return None
        # Per sigrok sr_ms8250d_packet_valid: byte 17 must be 0x00
        if buf[17] != 0x00:
            return None

        try:
            # Parse flags
            flags = cls.parse_flags(buf)
            if not cls.flags_valid(flags):
                return None
            
            # Parse main display digits
            d1_word = ((buf[3] & 0x07) << 8) | (buf[2] & 0x30) | ((buf[3] & 0x30) >> 4)
            d2_word = ((buf[4] & 0x73) << 4) | (buf[5] & 0x03)
            d3_word = ((buf[6] & 0x07) << 8) | (buf[5] & 0x30) | ((buf[6] & 0x30) >> 4)
            d4_word = ((buf[7] & 0x73) << 4) | (buf[8] & 0x03)
            
            digit1 = cls.parse_main_digit(d1_word)
            digit2 = cls.parse_main_digit(d2_word)
            digit3 = cls.parse_main_digit(d3_word)
            digit4 = cls.parse_main_digit(d4_word)
            
            # Reject misaligned frames: all four digits must decode to a valid
            # 7-segment pattern.  parse_main_digit() returns -1 for unrecognised
            # bit patterns, which is the primary signal of byte misalignment.
            if digit1 < 0 or digit2 < 0 or digit3 < 0 or digit4 < 0:
                return None

            # Build numeric value
            value = digit1 * 1000 + digit2 * 100 + digit3 * 10 + digit4
            
            # Decimal point position
            exponent = 0
            if (buf[3] & (1 << 6)):
                exponent = -3  # X.XXX
            elif (buf[5] & (1 << 6)):
                exponent = -2  # XX.XX
            elif (buf[7] & (1 << 2)):
                exponent = -1  # XXX.X
            
            # Apply multipliers
            if flags['is_nano']:
                exponent -= 9
            if flags['is_micro']:
                exponent -= 6
            if flags['is_milli']:
                exponent -= 3
            if flags['is_kilo']:
                exponent += 3
            if flags['is_mega']:
                exponent += 6
            
            value *= (10 ** exponent)
            
            # Sign
            if (buf[0] & (1 << 2)):
                value = -value
            
            # Check for overflow
            if digit3 == 0xF:
                value = float('inf')
            
            # Determine unit and measurement type
            unit = ""
            m_type = "UNKNOWN"
            
            if flags['is_volt']:
                unit = "V"
                m_type = "VOLTAGE"
            elif flags['is_ampere']:
                unit = "A"
                m_type = "CURRENT"
            elif flags['is_ohm']:
                unit = "Ω"
                m_type = "RESISTANCE"
            elif flags['is_hz']:
                unit = "Hz"
                m_type = "FREQUENCY"
            elif flags['is_farad']:
                unit = "F"
                m_type = "CAPACITANCE"
            elif flags['is_beep']:
                unit = "Ω"
                m_type = "CONTINUITY"
                # Keep actual resistance from digit parsing.
                # OL (inf) is already set by the overflow check above
                # and will be filtered by math.isfinite() downstream.
            elif flags['is_diode']:
                unit = "V"
                m_type = "DIODE"
            
            # AC/DC flags
            if flags['is_ac']:
                m_type = "AC_" + m_type
            elif flags['is_dc']:
                m_type = "DC_" + m_type
            
            # Parse secondary display
            sec_digit1 = cls.parse_sec_digit(buf[12])
            sec_digit2 = cls.parse_sec_digit(buf[13])
            sec_digit3 = cls.parse_sec_digit(buf[14])
            sec_digit4 = cls.parse_sec_digit(buf[15])
            
            if all(d != -1 for d in [sec_digit1, sec_digit2, sec_digit3, sec_digit4]):
                sec_value = sec_digit1 * 1000 + sec_digit2 * 100 + sec_digit3 * 10 + sec_digit4
                
                # Secondary decimal point
                sec_exponent = 0
                if (buf[14] & (1 << 7)):
                    sec_exponent = -3
                elif (buf[13] & (1 << 7)):
                    sec_exponent = -2
                elif (buf[12] & (1 << 7)):
                    sec_exponent = -1
                
                sec_value *= (10 ** sec_exponent)
                sec_unit = ""  # Could be determined based on context
            else:
                sec_value = None
                sec_unit = None
            
            return MultimeterReading(
                raw_value=buf.hex().upper(),
                value=value,
                unit=unit,
                measurement_type=m_type,
                timestamp=datetime.utcnow().isoformat(),
                secondary_value=sec_value,
                secondary_unit=sec_unit
            )
        except Exception as e:
            print(f"[MS8250D] Parse error: {e}")
            return None


class USBMultimeterClient:
    """
    Client for Mastech MS8250D USB Multimeter.
    
    The MS8250D transmits data via USB-serial at:
    - Baud rate: 2400 (default) or 9600 depending on version
    - Data bits: 8
    - Parity: None
    - Stop bits: 1
    """
    
    # Common baud rates for multimeters
    BAUD_RATES = [2400, 9600, 19200]
    
    # Regex patterns for parsing readings
    PATTERNS = {
        "dc_voltage": re.compile(r"DC\s*([\d.]+)\s*([mVkM]?V)?", re.IGNORECASE),
        "ac_voltage": re.compile(r"AC\s*([\d.]+)\s*([mVkM]?V)?", re.IGNORECASE),
        "dc_current": re.compile(r"DC\s*([\d.]+)\s*([mun]?A)?", re.IGNORECASE),
        "ac_current": re.compile(r"AC\s*([\d.]+)\s*([mun]?A)?", re.IGNORECASE),
        "resistance": re.compile(r"(OHM|Ω)\s*([\d.]+)\s*([kM])?", re.IGNORECASE),
        "continuity": re.compile(r"CONT\s*([\d.]+)?", re.IGNORECASE),
        "diode": re.compile(r"DIODE\s*([\d.]+)", re.IGNORECASE),
        "frequency": re.compile(r"([\d.]+)\s*(Hz|kHz|MHz)", re.IGNORECASE),
        "capacitance": re.compile(r"([\d.]+)\s*([nun]F)", re.IGNORECASE),
        # Generic pattern for any reading
        "generic": re.compile(r"([\d.]+)\s*([a-zA-ZΩ]+)?"),
    }
    
    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 2400,
        timeout: float = 1.0,
        on_reading_callback: Optional[Callable[[MultimeterReading], None]] = None
    ):
        """
        Initialize USB multimeter client.
        
        Args:
            port: COM port (e.g., "COM3" on Windows, "/dev/ttyUSB0" on Linux)
                  If None, will auto-detect
            baud_rate: Serial baud rate (default 2400 for MS8250D)
            timeout: Read timeout in seconds
            on_reading_callback: Callback function for each reading
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.on_reading_callback = on_reading_callback
        
        self._serial: Optional[serial.Serial] = None
        self._connected = False
        self._reading_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_reading: Optional[MultimeterReading] = None
        
    @staticmethod
    def list_available_ports() -> List[str]:
        """
        List all available COM ports.
        
        Returns:
            List of port device names
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    @staticmethod
    def detect_multimeter() -> Optional[str]:
        """
        Auto-detect the multimeter port.
        
        Looks for common USB-serial chips used in multimeters:
        - CH340 (common in Chinese multimeters)
        - FTDI (higher quality)
        - CP210x (Silicon Labs)
        
        Returns:
            Port device name or None if not found
        """
        ports = serial.tools.list_ports.comports()
        
        # Known USB-serial chip vendors
        multimeter_vendors = [
            "10C4",  # Silicon Labs (CP210x) - PRIORITIZED
            "1A86",  # QinHeng Electronics (CH340)
            "0403",  # FTDI
            "067B",  # Prolific (PL2303)
        ]
        
        for port in ports:
            if hasattr(port, 'vid') and port.vid:
                if f"{port.vid:04X}" in multimeter_vendors:
                    return port.device
            
            # Fallback: check description for keywords
            desc = port.description.lower()
            if any(kw in desc for kw in ['usb-serial', 'ch340', 'ftdi', 'cp210', 'multimeter']):
                return port.device
        
        # If no specific device found, return first available port
        if ports:
            return ports[0].device
        
        return None
    
    def connect(self) -> bool:
        """
        Connect to the multimeter.
        
        Returns:
            True if connection successful
        """
        try:
            # Auto-detect port if not specified
            if not self.port:
                self.port = self.detect_multimeter()
                if not self.port:
                    print("[USB] No multimeter port detected")
                    return False
            
            # Try different baud rates
            for baud in [self.baud_rate] + [b for b in self.BAUD_RATES if b != self.baud_rate]:
                try:
                    self._serial = serial.Serial(
                        port=self.port,
                        baudrate=baud,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=self.timeout
                    )
                    # Match raw_dump.py settings that produce valid frames
                    self._serial.dtr = True
                    self._serial.rts = False
                    time.sleep(0.1)
                    self._serial.reset_input_buffer()
                    self.baud_rate = baud
                    break
                except serial.SerialException:
                    continue
            
            if not self._serial or not self._serial.is_open:
                print(f"[USB] Failed to open port {self.port}")
                return False
            
            self._connected = True
            print(f"[USB] Connected to multimeter on {self.port} at {self.baud_rate} baud")
            return True
            
        except Exception as e:
            print(f"[USB] Connection error: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the multimeter."""
        self._stop_event.set()
        
        if self._reading_thread and self._reading_thread.is_alive():
            self._reading_thread.join(timeout=2.0)
        
        if self._serial and self._serial.is_open:
            self._serial.close()
        
        self._connected = False
        print("[USB] Disconnected from multimeter")
    
    def is_connected(self) -> bool:
        """Check if connected to multimeter."""
        return self._connected and self._serial and self._serial.is_open

    def reconnect(self) -> bool:
        """Close the current connection and attempt to reconnect.

        Useful when the COM port becomes inaccessible (USB disconnect,
        PermissionError, device sleep) and needs to be re-opened.

        Returns:
            True if reconnection succeeded.
        """
        # Silently close whatever state exists
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception:
            pass
        self._serial = None
        self._connected = False

        # Re-use existing connect() which handles auto-detect + baud cycling
        return self.connect()
    
    def _parse_reading(self, raw_data: str) -> Optional[MultimeterReading]:
        """
        Parse raw data string into a reading.
        
        Args:
            raw_data: Raw string from multimeter
            
        Returns:
            MultimeterReading or None if parsing failed
        """
        raw_data = raw_data.strip()
        if not raw_data:
            return None
        
        # Try each pattern
        for reading_type, pattern in self.PATTERNS.items():
            match = pattern.search(raw_data)
            if match:
                groups = match.groups()
                
                # Extract value and unit based on pattern type
                if reading_type == "resistance":
                    value = float(groups[1]) if len(groups) > 1 else 0.0
                    unit = "Ω"
                    if len(groups) > 2 and groups[2]:
                        multiplier = groups[2].upper()
                        if multiplier == 'K':
                            value *= 1000
                        elif multiplier == 'M':
                            value *= 1000000
                    measurement_type = "RESISTANCE"
                    
                elif reading_type in ["dc_voltage", "ac_voltage"]:
                    value = float(groups[0])
                    unit = groups[1] if len(groups) > 1 and groups[1] else "V"
                    measurement_type = "DC_VOLTAGE" if "dc" in reading_type else "AC_VOLTAGE"
                    
                elif reading_type in ["dc_current", "ac_current"]:
                    value = float(groups[0])
                    unit = groups[1] if len(groups) > 1 and groups[1] else "A"
                    measurement_type = "DC_CURRENT" if "dc" in reading_type else "AC_CURRENT"
                    
                elif reading_type == "frequency":
                    value = float(groups[0])
                    unit = groups[1] if len(groups) > 1 else "Hz"
                    measurement_type = "FREQUENCY"
                    
                elif reading_type == "capacitance":
                    value = float(groups[0])
                    unit = groups[1] if len(groups) > 1 else "F"
                    measurement_type = "CAPACITANCE"
                    
                else:
                    # Generic parsing
                    value = float(groups[0])
                    unit = groups[1] if len(groups) > 1 and groups[1] else ""
                    measurement_type = reading_type.upper()
                
                return MultimeterReading(
                    raw_value=raw_data,
                    value=value,
                    unit=unit,
                    measurement_type=measurement_type,
                    timestamp=datetime.utcnow().isoformat()
                )
        
        # If no pattern matched, try generic numeric extraction
        numbers = re.findall(r"([\d.]+)", raw_data)
        if numbers:
            try:
                return MultimeterReading(
                    raw_value=raw_data,
                    value=float(numbers[0]),
                    unit="",
                    measurement_type="UNKNOWN",
                    timestamp=datetime.utcnow().isoformat()
                )
            except ValueError:
                pass
        
        return None
    
    def _parse_binary_frame(self, raw_bytes: bytes) -> Optional[MultimeterReading]:
        """
        Parse binary frame from MS8250D multimeter.

        Uses ONLY the verified 18-byte MS8250D protocol (sigrok-based).
        Slides through the buffer looking for a valid frame where
        buf[17]==0x00 and flags pass validation.

        Args:
            raw_bytes: Raw binary data from multimeter

        Returns:
            MultimeterReading or None if parsing failed
        """
        if not raw_bytes or len(raw_bytes) < 18:
            return None

        # Slide through buffer looking for a valid 18-byte MS8250D frame
        for i in range(len(raw_bytes) - 17):
            candidate = raw_bytes[i:i+18]
            reading = MastechMS8250DParser.parse_frame(candidate)
            if reading and reading.measurement_type != "UNKNOWN":
                return reading

        return None
    def _parse_new_frame_format(self, frame: bytes) -> Optional[MultimeterReading]:
        """
        Parse the new MS8250D frame format (C8FEEC or C8EECC).
        
        The Mastech MS8250D often uses a 14-byte frame where digits are 
        encoded as segments or specific byte patterns.
        """
        try:
            if len(frame) < 10 or frame[0] != 0xC8:
                return None
            
            # Support both C8 FE EC and C8 EE CC headers
            is_new_header = (frame[1] == 0xFE and frame[2] == 0xEC) or (frame[1] == 0xEE and frame[2] == 0xCC)
            if not is_new_header:
                return None
            
            # DEBUG: Log this parsing path
            # print(f"[DEBUG _parse_new_frame_format] Parsing frame: {frame.hex().upper()}")
                
            # Improved Digit Extraction
            # In many Mastech devices, digits are in fixed positions or marked by 0x3X
            digits = []
            for b in frame[3:]:
                if 0x30 <= b <= 0x39:
                    digits.append(b - 0x30)
            
            # If standard ASCII extraction fails, try segment-like mapping or just raw value extraction
            # For now, we will lean on the observed ASCII pattern but add more robust type detection
            
            if not digits:
                # Fallback: maybe the value is in bytes 4-8 directly?
                # This is common in some binary protocols
                pass

            if len(digits) >= 2:
                # Basic value reconstruction
                # If we have 4 digits, it's likely D1 D2 D3 D4 with a decimal point
                if len(digits) == 4:
                    value = digits[0] * 1000 + digits[1] * 100 + digits[2] * 10 + digits[3]
                    # Scale based on decimal point (often byte 7 or 8)
                    # For now, heuristic scaling
                    if value > 1000: value /= 100.0 
                else:
                    value = float("".join(map(str, digits[:4]))) / 10.0
                
                # Mode/Function Detection
                # MS8250D uses "Func" button. We need to look for AC vs DC bits.
                # Usually byte 3 or byte 9 contains status flags.
                unit = "V"
                measurement_type = "DC_VOLTAGE"
                
                # Status Byte analysis (Byte 3 or 9 often contains AC/DC/Auto flags)
                status_byte = frame[3] if len(frame) > 3 else 0x00
                
                # Heuristic for MS8250D:
                # 0xAC or 0x21 often indicates AC
                if 0xAC in frame or 0x21 in frame or (status_byte & 0x08):
                    measurement_type = "AC_VOLTAGE"
                
                # Check for Current (A/mA/uA)
                if 0x1F in frame or 0x3F in frame:
                    unit = "A"
                    measurement_type = "DC_CURRENT"
                    if "AC" in measurement_type or 0xAC in frame:
                        measurement_type = "AC_CURRENT"
                
                # Check for Resistance (Ω)
                if 0x72 in frame or 0x52 in frame or 0xDF in frame:
                    unit = "Ω"
                    measurement_type = "RESISTANCE"

                return MultimeterReading(
                    raw_value=f"0x{frame.hex().upper()}",
                    value=value,
                    unit=unit,
                    measurement_type=measurement_type,
                    timestamp=datetime.utcnow().isoformat()
                )
        
        except Exception as e:
            print(f"[USB] New format parse error: {e}")
        
        return None

    def _parse_um24c_frame(self, frame: bytes) -> Optional[MultimeterReading]:
        """
        Parse MS8250D style binary frame (older format).
        Format example: 0x44 0x22 0x03 0x00 0x00 0x30 0x35 0x04 0x03 0x10
        
        Frame structure analysis from captured data:
        - Byte 0: 0x40 or 0x44 (start marker)
        - Byte 1-2: Function code
        - Byte 3-4: Measurement mode/unit
        - Bytes 5-6: Value (ASCII digits, 0x30-0x39)
        - Byte 7: Decimal point position
        - Byte 8: Additional mode info
        - Byte 9: 0x10 (end marker)
        """
        try:
            # DEBUG: Log the raw frame
            print(f"[DEBUG _parse_um24c_frame] frame={frame.hex().upper()}, len={len(frame)}")
            
            # Extract voltage/current from frame
            if len(frame) >= 9 and frame[0] in [0x40, 0x44]:
                # Relaxed checks for end marker as it varies by device
                # Bytes 5-6 are ASCII digits
                digit1 = frame[5] - 0x30
                digit2 = frame[6] - 0x30
                
                # DEBUG: Log digits
                print(f"[DEBUG] digit1={digit1} (0x{frame[5]:02x}), digit2={digit2} (0x{frame[6]:02x})")
                
                if 0 <= digit1 <= 9 and 0 <= digit2 <= 9:
                    # Byte 7 indicates decimal point position
                    decimal_pos = frame[7]
                    
                    # DEBUG: Log the values
                    print(f"[DEBUG PARSE] frame={frame.hex().upper()}, digit1={digit1}, digit2={digit2}, decimal_pos=0x{decimal_pos:02x}")
                    
                    # Calculate value based on decimal position
                    if decimal_pos == 0x01:
                        value = digit1 + digit2 / 10.0
                    elif decimal_pos == 0x02:
                        value = digit1 / 10.0 + digit2 / 100.0
                    elif decimal_pos == 0x03:
                        value = digit1 * 10 + digit2
                    elif decimal_pos == 0x04:
                        value = digit1 * 100 + digit2 * 10
                    elif decimal_pos == 0x57:
                        # Special case from our data - this seems to represent 0.5V
                        value = 0.5
                    elif decimal_pos == 0x76:
                        # Special case - seems to represent 5.0V
                        value = 5.0
                    else:
                        value = digit1 + digit2
                    
                    # DEBUG: Log value before mode detection
                    print(f"[DEBUG] Calculated value={value}, mode_byte=0x{frame[3]:02x}, unit_byte=0x{frame[4]:02x}")
                    
                    # Determine measurement type and unit from bytes 3-4
                    mode_byte = frame[3]
                    unit_byte = frame[4]
                    
                    # Handle unknown modes - check for common patterns
                    # Mode 0x75 with unit 0x53 appears to be a valid DC voltage reading
                    if mode_byte == 0x75:
                        # Unknown mode - default to DC voltage but log for investigation
                        print(f"[DEBUG] Unknown mode 0x75 detected - defaulting to DC_VOLTAGE")
                        unit = "V"
                        measurement_type = "DC_VOLTAGE"
                    elif mode_byte == 0x03 and unit_byte == 0x00:
                        # DC Voltage
                        unit = "V"
                        measurement_type = "DC_VOLTAGE"
                    elif mode_byte == 0x02 and unit_byte == 0x00:
                        # DC Current
                        unit = "A"
                        measurement_type = "DC_CURRENT"
                    elif mode_byte == 0x02 and unit_byte == 0x21:
                        # AC Voltage
                        unit = "V"
                        measurement_type = "AC_VOLTAGE"
                    elif mode_byte == 0x01 and unit_byte == 0x00:
                        # Resistance
                        unit = "Ω"
                        measurement_type = "RESISTANCE"
                    else:
                        # DEBUG: Log when we hit the default case
                        print(f"[DEBUG] Unknown mode! mode_byte=0x{mode_byte:02x}, unit_byte=0x{unit_byte:02x} - defaulting to DC_VOLTAGE")
                        # Default to DC Voltage if unknown
                        unit = "V"
                        measurement_type = "DC_VOLTAGE"
                        
                    return MultimeterReading(
                        raw_value=f"0x{frame.hex().upper()}",
                        value=value,
                        unit=unit,
                        measurement_type=measurement_type,
                        timestamp=datetime.utcnow().isoformat()
                    )
        
        except Exception as e:
            print(f"[USB] Binary parse error: {e}")
        
        return None
    
    def read_measurement(self, timeout: float = 2.0) -> Optional[MultimeterReading]:
        """
        Read a single measurement from the multimeter.
        
        Args:
            timeout: Maximum time to wait for reading
            
        Returns:
            MultimeterReading or None if timeout/error
        """
        if not self.is_connected():
            print("[USB] Not connected to multimeter")
            return None
        
        try:
            # Read until we get a complete frame or timeout
            start_time = time.time()
            buffer = b""
            
            while time.time() - start_time < timeout:
                if self._serial.in_waiting > 0:
                    buffer += self._serial.read(self._serial.in_waiting)

                    # Only try parsing when we have enough for a full 18-byte MS8250D frame
                    if len(buffer) >= 18:
                        binary_reading = self._parse_binary_frame(buffer)
                        if binary_reading:
                            self._last_reading = binary_reading
                            return binary_reading

                    # Limit buffer size -- keep last 2 potential frames
                    if len(buffer) > 64:
                        buffer = buffer[-36:]

                else:
                    time.sleep(0.01)
            
            # Timeout - no valid frame received
            return None
            
        except PermissionError as e:
            # Windows ClearCommError(13) = COM port truly gone (USB
            # disconnect, device sleep, another process grabbed port).
            print(f"[USB] Port lost: {e}")
            self._connected = False
            return None
        except Exception as e:
            print(f"[USB] Read error: {e}")
            return None
    
    def start_continuous_reading(self) -> None:
        """Start continuous reading in background thread."""
        if self._reading_thread and self._reading_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._reading_thread = threading.Thread(target=self._continuous_read_loop, daemon=True)
        self._reading_thread.start()
    
    def stop_continuous_reading(self) -> None:
        """Stop continuous reading."""
        self._stop_event.set()
        if self._reading_thread:
            self._reading_thread.join(timeout=2.0)
    
    def _continuous_read_loop(self) -> None:
        """Background thread for continuous reading."""
        while not self._stop_event.is_set() and self.is_connected():
            reading = self.read_measurement(timeout=0.5)
            if reading and self.on_reading_callback:
                self.on_reading_callback(reading)
    
    def get_last_reading(self) -> Optional[MultimeterReading]:
        """Get the most recent reading."""
        return self._last_reading


# =============================================================================
# Convenience Functions
# =============================================================================

def create_multimeter_client(
    port: Optional[str] = None,
    on_reading_callback: Optional[Callable[[MultimeterReading], None]] = None
) -> USBMultimeterClient:
    """
    Create a multimeter client with auto-detection.
    
    Args:
        port: Optional port override
        on_reading_callback: Callback for readings
        
    Returns:
        Configured USBMultimeterClient
    """
    return USBMultimeterClient(
        port=port,
        on_reading_callback=on_reading_callback
    )


def quick_read(port: Optional[str] = None) -> Optional[MultimeterReading]:
    """
    Quick one-time read from multimeter.
    
    Args:
        port: Optional port override
        
    Returns:
        Single reading or None
    """
    client = USBMultimeterClient(port=port)
    if client.connect():
        reading = client.read_measurement()
        client.disconnect()
        return reading
    return None


if __name__ == "__main__":
    # Test the multimeter client
    print("Available ports:", USBMultimeterClient.list_available_ports())
    
    detected = USBMultimeterClient.detect_multimeter()
    print(f"Detected multimeter: {detected}")
    
    if detected:
        client = USBMultimeterClient(port=detected)
        if client.connect():
            print("Reading measurements (press Ctrl+C to stop)...")
            try:
                while True:
                    reading = client.read_measurement()
                    if reading:
                        print(f"  {reading.measurement_type}: {reading.value} {reading.unit}")
            except KeyboardInterrupt:
                pass
            client.disconnect()