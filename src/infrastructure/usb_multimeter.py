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
    raw_value: str = ""     # Raw string or hex from device
    value: float = 0.0      # Numeric value
    unit: str = ""          # Unit (V, A, OHM, Hz, etc.)
    measurement_type: str = "UNKNOWN"
    timestamp: str = ""     # ISO timestamp
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


class FS9721Parser:
    """
    Parser for the Fortune Semiconductor FS9721 14-byte protocol.
    Used by many 4000-count/6600-count multimeters.
    Features "nibble-sync" (high nibble of byte i is i+1).
    """
    
    SEGMENT_MAP = {
        0xAF: "0", 0x06: "1", 0x6D: "2", 0x4F: "3", 0xC6: "4",
        0xCB: "5", 0xEB: "6", 0x0E: "7", 0xEF: "8", 0xCF: "9",
        0x00: " ", 0xE1: "L" 
    }

    @classmethod
    def decode_digit(cls, high_bits: int, low_bits: int) -> str:
        """Decode a 7-segment digit from two nibbles."""
        seg = (high_bits << 4) | low_bits
        return cls.SEGMENT_MAP.get(seg & 0x7F, " ")

    @classmethod
    def parse_frame(cls, buf: bytes) -> Optional[MultimeterReading]:
        if len(buf) < 14: return None
        for i in range(14):
            if (buf[i] >> 4) != (i + 1): return None
        n = [b & 0x0F for b in buf]
        try:
            is_negative = bool(n[0] & 0x08)
            d1 = cls.decode_digit(n[1], n[2])
            d2 = cls.decode_digit(n[3], n[4])
            d3 = cls.decode_digit(n[5], n[6])
            d4 = cls.decode_digit(n[7], n[8])
            val_str = (d1 + d2 + d3 + d4).strip()
            if not val_str: return None
            if n[3] & 0x08: val_str = d1 + "." + d2 + d3 + d4
            elif n[5] & 0x08: val_str = d1 + d2 + "." + d3 + d4
            elif n[7] & 0x08: val_str = d1 + d2 + d3 + "." + d4
            unit, m_type = "", "UNKNOWN"
            is_ac = bool(n[12] & 0x02)
            if n[12] & 0x04:
                unit, m_type = "V", "AC_VOLTAGE" if is_ac else "DC_VOLTAGE"
            elif n[12] & 0x02:
                unit, m_type = "A", "AC_CURRENT" if is_ac else "DC_CURRENT"
            elif n[11] & 0x01:
                unit, m_type = "Ω", "RESISTANCE"
                if n[12] & 0x01: m_type = "CONTINUITY"
            elif n[13] & 0x04: unit, m_type = "Hz", "FREQUENCY"
            elif n[10] & 0x04: unit, m_type = "F", "CAPACITANCE"
            elif n[12] & 0x01: unit, m_type = "V", "DIODE"
            multiplier = 1.0
            if n[10] & 0x08: multiplier = 1000.0
            elif n[10] & 0x04: multiplier = 1000000.0
            elif n[10] & 0x02: multiplier = 0.001
            elif n[9] & 0x08: multiplier = 1e-6
            elif n[9] & 0x04: multiplier = 1e-9
            if val_str == "L": value = float('inf')
            else:
                value = float(val_str)
                if is_negative: value *= -1
                value *= multiplier
            return MultimeterReading(
                raw_value=buf.hex().upper(), value=value, unit=unit,
                measurement_type=m_type, timestamp=datetime.utcnow().isoformat()
            )
        except: return None


class MastechMS8250DParser:
    """Strict parser for the MASTECH MS8250D (18-byte protocol)."""
    PACKET_SIZE = 18
    DIGITS_MAIN = {
        0x533: "0", 0x003: "1", 0x721: "2", 0x703: "3", 0x213: "4",
        0x712: "5", 0x732: "6", 0x103: "7", 0x733: "8", 0x713: "9",
        0x430: "L", 0x000: " "
    }
    DIGITS_SEC = {
        0x00: "0", 0x7D: "0", 0x05: "1", 0x1B: "2", 0x1F: "3", 0x27: "4",
        0x3E: "5", 0x7E: "6", 0x15: "7", 0x7F: "8", 0x3F: "9"
    }

    @classmethod
    def parse_main_digit(cls, word: int) -> str:
        return cls.DIGITS_MAIN.get(word & 0x733, " ")

    @classmethod
    def parse_sec_digit(cls, byte: int) -> str:
        return cls.DIGITS_SEC.get(byte & 0x7F, " ")

    @classmethod
    def _flags(cls, buf: bytes) -> dict:
        return {
            "is_volt": bool(buf[9] & (1 << 4)),
            "is_ohm": bool(buf[9] & (1 << 6)),
            "is_ampere": bool(buf[10] & (1 << 0)),
            "is_hz": bool(buf[10] & (1 << 2)),
            "is_farad": bool(buf[10] & (1 << 1)),
            "is_micro": bool(buf[9] & (1 << 1)) if (buf[10] & (1 << 1)) else bool(buf[8] & (1 << 4)),
            "is_nano": bool(buf[8] & (1 << 5)),
            "is_milli": bool(buf[9] & (1 << 0)),
            "is_kilo": bool(buf[9] & (1 << 2)),
            "is_mega": bool(buf[8] & (1 << 6)),
            "is_rs232": bool(buf[1] & (1 << 1)),
            "is_ac": bool(buf[1] & (1 << 4)),
            "is_dc": bool(buf[2] & (1 << 1)),
            "is_diode": bool(buf[11] & (1 << 0)),
            "is_beep": bool(buf[11] & (1 << 1)),
        }

    @classmethod
    def _flags_valid(cls, flags: dict) -> bool:
        if not flags["is_rs232"]: return False
        measurement_count = sum(1 for k in ("is_hz", "is_ohm", "is_farad", "is_ampere", "is_volt") if flags[k])
        if measurement_count != 1: return False
        if flags["is_ac"] and flags["is_dc"]: return False
        return True

    @classmethod
    def parse_frame(cls, buf: bytes) -> Optional[MultimeterReading]:
        if len(buf) != 18 or buf[17] != 0x00: return None
        flags = cls._flags(buf)
        if not cls._flags_valid(flags): return None
        try:
            d1_word = ((buf[3] & 0x07) << 8) | (buf[2] & 0x30) | ((buf[3] & 0x30) >> 4)
            d2_word = ((buf[4] & 0x73) << 4) | (buf[5] & 0x03)
            d3_word = ((buf[6] & 0x07) << 8) | (buf[5] & 0x30) | ((buf[6] & 0x30) >> 4)
            d4_word = ((buf[7] & 0x73) << 4) | (buf[8] & 0x03)
            s = [cls.parse_main_digit(w) for w in [d1_word, d2_word, d3_word, d4_word]]
            if " " in s: return None
            if "L" in s: value = float('inf')
            else:
                val_str = "".join(s)
                if buf[3] & 0x40: val_str = val_str[0] + "." + val_str[1:]
                elif buf[5] & 0x40: val_str = val_str[:2] + "." + val_str[2:]
                elif buf[7] & 0x04: val_str = val_str[:3] + "." + val_str[3:]
                sign = -1 if (buf[0] & 0x04) else 1
                value = float(val_str) * sign
                if flags["is_nano"]: value *= 1e-9
                elif flags["is_micro"]: value *= 1e-6
                elif flags["is_milli"]: value *= 1e-3
                elif flags["is_kilo"]: value *= 1e3
                elif flags["is_mega"]: value *= 1e6
            unit, m_type = "", "UNKNOWN"
            if flags["is_beep"]: unit, m_type = "Ω", "CONTINUITY"
            elif flags["is_diode"]: unit, m_type = "V", "DIODE"
            elif flags["is_ohm"]: unit, m_type = "Ω", "RESISTANCE"
            elif flags["is_hz"]: unit, m_type = "Hz", "FREQUENCY"
            elif flags["is_farad"]: unit, m_type = "F", "CAPACITANCE"
            elif flags["is_ampere"]: unit, m_type = "A", "AC_CURRENT" if flags["is_ac"] else "DC_CURRENT"
            elif flags["is_volt"]: unit, m_type = "V", "AC_VOLTAGE" if flags["is_ac"] else "DC_VOLTAGE"
            return MultimeterReading(
                raw_value=buf.hex().upper(), value=value, unit=unit,
                measurement_type=m_type, timestamp=datetime.utcnow().isoformat()
            )
        except: return None
class USBMultimeterClient:
    """MS8250D USB multimeter client (strict 18-byte binary protocol)."""
    BAUD_RATES = [2400]

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 2400,
        timeout: float = 1.0,
        on_reading_callback: Optional[Callable[[MultimeterReading], None]] = None
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
        self._buffer = b""

    @staticmethod
    def list_available_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def detect_multimeter() -> Optional[str]:
        ports = serial.tools.list_ports.comports()
        for p in ports:
            v, pi = getattr(p, "vid", None), getattr(p, "pid", None)
            if v == 0x10C4 and pi == 0xEA60: return p.device # CP2102
            desc = (p.description or "").lower()
            if any(x in desc for x in ["cp210", "silicon labs", "usb serial"]): return p.device
        return ports[0].device if ports else None

    def connect(self) -> bool:
        try:
            if not self.port: self.port = self.detect_multimeter()
            if not self.port: return False
            baud = self.baud_rate or 2400
            self._serial = serial.Serial(
                port=self.port, baudrate=baud, bytesize=8, parity='N', stopbits=1, timeout=self.timeout
            )
            if self._serial.is_open:
                self._connected, self._buffer = True, b""
                print(f"[USB] Connected to {self.port} at {baud} baud")
                return True
            return False
        except Exception as e:
            print(f"[USB] Connection error: {e}"); return False

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._reading_thread and self._reading_thread.is_alive():
            self._reading_thread.join(timeout=2.0)
        ser = self._serial
        if ser and ser.is_open: ser.close()
        self._connected = False
        print("[USB] Disconnected")

    def __enter__(self) -> "USBMultimeterClient":
        self.connect(); return self

    def __exit__(self, t, v, tb) -> None:
        self.disconnect()

    def is_connected(self) -> bool:
        return bool(self._connected and self._serial and self._serial.is_open)

    def _try_parse_buffer(self) -> Optional[MultimeterReading]:
        """Scan buffer for tight 18-byte MS8250D frame, then 14-byte FS9721."""
        if len(self._buffer) < 14: return None
        
        # 1. Try 18-byte Mastech
        if len(self._buffer) >= 18:
            limit = len(self._buffer) - 18 + 1
            for i in range(limit):
                reading = MastechMS8250DParser.parse_frame(self._buffer[i:i+18])
                if reading:
                    self._buffer = self._buffer[i+18:]
                    return reading

        # 2. Try 14-byte FS9721 (with nibble-sync)
        limit = len(self._buffer) - 14 + 1
        for i in range(limit):
            if (self._buffer[i] >> 4) == 1:
                reading = FS9721Parser.parse_frame(self._buffer[i:i+14])
                if reading:
                    self._buffer = self._buffer[i+14:]
                    return reading

        if len(self._buffer) > 128: self._buffer = self._buffer[-64:]
        return None

    def read_measurement(self, timeout: float = 2.0) -> Optional[MultimeterReading]:
        if not self.is_connected(): return None
        try:
            start = time.time()
            while time.time() - start < timeout:
                waiting = int(self._serial.in_waiting or 0)
                if waiting > 0:
                    self._buffer += self._serial.read(waiting)
                    reading = self._try_parse_buffer()
                    if reading:
                        self._last_reading = reading
                        return reading
                time.sleep(0.01)
            return None
        except PermissionError:
            # Bare PermissionError (non-Windows or older pyserial)
            print("[USB] PermissionError, reconnecting...")
            self.disconnect()
            time.sleep(1.0)
            self.connect()
            return None
        except Exception as e:
            # On Windows, pyserial wraps ClearCommError / WriteFile / ReadFile
            # OS errors inside SerialException — the bare PermissionError handler
            # above will NOT match.  Detect by inspecting the message string.
            err_str = str(e)
            if "PermissionError" in err_str or "Access is denied" in err_str:
                print(f"[USB] Windows COM-port access denied (SerialException) — reconnecting...")
                self.disconnect()
                time.sleep(1.5)   # give the OS a moment to release the handle
                self.connect()
            else:
                print(f"[USB] Read error: {e}")
            return None

    def start_continuous_reading(self) -> None:
        if self._reading_thread and self._reading_thread.is_alive(): return
        self._stop_event.clear()
        self._reading_thread = threading.Thread(target=self._continuous_read_loop, daemon=True)
        self._reading_thread.start()

    def _continuous_read_loop(self) -> None:
        while not self._stop_event.is_set() and self.is_connected():
            reading = self.read_measurement(timeout=0.5)
            if reading and self.on_reading_callback: self.on_reading_callback(reading)

    def get_last_reading(self) -> Optional[MultimeterReading]:
        return self._last_reading


def create_multimeter_client(
    port: Optional[str] = None, 
    on_reading_callback: Optional[Callable[[MultimeterReading], None]] = None
) -> USBMultimeterClient:
    return USBMultimeterClient(port=port, on_reading_callback=on_reading_callback)


def quick_read(port: Optional[str] = None) -> Optional[MultimeterReading]:
    with USBMultimeterClient(port=port) as client:
        return client.read_measurement()