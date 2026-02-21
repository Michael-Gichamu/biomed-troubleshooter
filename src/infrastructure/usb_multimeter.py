"""
USB Multimeter Client for Mastech MS8250D

Receives measurement data from Mastech MS8250D multimeter via USB.
The multimeter appears as a virtual COM port when connected.

Protocol Information:
- The MS8250D uses a USB-to-serial chip (typically CH340 or similar)
- Data is transmitted as serial text at 2400 baud (default)
- Format: "DC 24.5V" or "AC 230V" or "OHM 1.5k" etc.

Usage:
    from src.infrastructure.usb_multimeter import USBMultimeterClient
    
    client = USBMultimeterClient(port="COM3")
    if client.connect():
        reading = client.read_measurement()
        print(f"Value: {reading.value} {reading.unit}")
"""

import serial
import serial.tools.list_ports
from dataclasses import dataclass
from typing import Optional, List, Callable
from datetime import datetime
import threading
import re
import time


@dataclass
class MultimeterReading:
    """A single reading from the multimeter."""
    raw_value: str          # Raw string from device
    value: float            # Numeric value
    unit: str               # Unit (V, A, OHM, Hz, etc.)
    measurement_type: str   # DC, AC, OHM, CONT, DIODE, etc.
    timestamp: str          # ISO timestamp
    test_point_id: str = "" # Optional test point identifier
    
    def to_dict(self) -> dict:
        """Convert to dictionary for agent consumption."""
        return {
            "test_point": self.test_point_id or "MM1",
            "value": self.value,
            "unit": self.unit,
            "measurement_type": self.measurement_type,
            "raw": self.raw_value,
            "timestamp": self.timestamp
        }


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
            "1A86",  # QinHeng Electronics (CH340)
            "0403",  # FTDI
            "10C4",  # Silicon Labs (CP210x)
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
                    unit = groups[1] if len(groups) > 1 else ""
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
            # Read until we get a complete line
            start_time = time.time()
            buffer = ""
            
            while time.time() - start_time < timeout:
                if self._serial.in_waiting > 0:
                    byte = self._serial.read(1)
                    char = byte.decode('ascii', errors='ignore')
                    
                    if char in ['\n', '\r']:
                        if buffer.strip():
                            reading = self._parse_reading(buffer)
                            if reading:
                                self._last_reading = reading
                                return reading
                            buffer = ""
                    else:
                        buffer += char
                else:
                    time.sleep(0.01)
            
            # Timeout - try to parse whatever we have
            if buffer.strip():
                reading = self._parse_reading(buffer)
                if reading:
                    self._last_reading = reading
                    return reading
            
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
