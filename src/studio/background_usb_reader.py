"""
Background USB Multimeter Reader

This module provides a singleton background reader that continuously
reads from the USB multimeter and intelligently processes readings:
1. Ignores noise (very low values from air/probe handling)
2. Collects readings for a short period
3. Averages stable readings (ignores outliers)
4. Returns the stable average when values settle
"""

import threading
import time
import statistics
from typing import Optional
from dataclasses import dataclass, field

from src.infrastructure.usb_multimeter import USBMultimeterClient, MultimeterReading


@dataclass
class ReadingStats:
    """Track reading statistics for stabilization detection."""
    # Fluctuation thresholds by measurement type (as percentage)
    FLUCTUATION_THRESHOLDS = {
        "AC_VOLTAGE": 2.5,      # 2.5% for AC
        "AC_CURRENT": 2.5,
        "DC_VOLTAGE": 0.5,      # 0.5% for DC (very stable)
        "DC_CURRENT": 1.0,       # 1% for DC current
        "RESISTANCE": 1.0,       # 1% for resistance
        "DEFAULT": 1.0           # Default 1%
    }
    
    # Noise threshold - ignore readings below this (air interference)
    NOISE_THRESHOLD = 0.5  # volts
    
    readings: list = field(default_factory=list)
    timestamps: list = field(default_factory=list)
    measurement_type: str = "DC_VOLTAGE"
    
    def set_measurement_type(self, m_type: str):
        """Set the measurement type for threshold calculation."""
        self.measurement_type = m_type.upper() if m_type else "DEFAULT"
        self.clear()
    
    def add(self, reading: float):
        """Add a reading."""
        self.readings.append(reading)
        self.timestamps.append(time.time())
        # Keep only last 30 readings
        if len(self.readings) > 30:
            self.readings.pop(0)
            self.timestamps.pop(0)
    
    def clear(self):
        """Clear all readings."""
        self.readings.clear()
        self.timestamps.clear()
    
    def get_fluctuation_threshold(self) -> float:
        """Get the fluctuation threshold percentage for current measurement type."""
        return self.FLUCTUATION_THRESHOLDS.get(self.measurement_type, self.FLUCTUATION_THRESHOLDS["DEFAULT"])
    
    def is_stable(self, min_readings: int = 5) -> bool:
        """Check if readings are stable based on percentage fluctuation."""
        if len(self.readings) < min_readings:
            return False
        if len(self.readings) < 3:
            return False
        
        mean = statistics.mean(self.readings)
        if mean == 0:
            return False
        
        # Calculate percentage fluctuation
        std_dev = statistics.stdev(self.readings) if len(self.readings) > 1 else 0
        percent_fluctuation = (std_dev / mean) * 100
        
        threshold = self.get_fluctuation_threshold()
        return percent_fluctuation <= threshold
    
    def get_average(self) -> Optional[float]:
        """Get average of readings."""
        if not self.readings:
            return None
        return statistics.mean(self.readings)
    
    def get_stable_average(self) -> Optional[float]:
        """Get average only if stable, otherwise None."""
        if not self.is_stable():
            return None
        return statistics.mean(self.readings)


@dataclass
class BackgroundReader:
    """Singleton background reader for USB multimeter with noise filtering."""
    
    # Noise threshold - ignore readings below this (air interference)
    NOISE_THRESHOLD = 0.5  # volts - ignore values below 0.5V
    
    client: Optional[USBMultimeterClient] = None
    _thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _latest_reading: Optional[MultimeterReading] = None
    _stable_reading: Optional[MultimeterReading] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _is_running: bool = False
    
    # Reading buffer for stabilization
    _reading_stats: ReadingStats = field(default_factory=ReadingStats)
    _last_probe_time: float = 0.0
    
    def start(self) -> bool:
        """Start the background reader."""
        if self._is_running:
            return True
            
        # Try to connect to multimeter
        self.client = USBMultimeterClient()
        
        if not self.client.connect():
            print("[BACKGROUND_READER] Could not connect to multimeter")
            self.client = None
            return False
        
        # Start background thread
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self._is_running = True
        print("[BACKGROUND_READER] Started")
        return True
    
    def _read_loop(self):
        """Background reading loop with noise filtering."""
        while not self._stop_event.is_set():
            try:
                if self.client:
                    reading = self.client.read_measurement(timeout=0.5)
                    if reading and reading.value is not None:
                        value = abs(reading.value)  # Use absolute value
                        
                        # Filter noise - ignore very low values (air interference)
                        if value < self.NOISE_THRESHOLD:
                            # Too low - likely noise from air or probe handling
                            # Reset the reading stats to start fresh
                            with self._lock:
                                self._reading_stats.clear()
                            continue
                        
                        # Set measurement type for threshold calculation
                        self._reading_stats.set_measurement_type(reading.measurement_type)
                        
                        # Valid reading - add to buffer
                        with self._lock:
                            self._reading_stats.add(value)
                            self._latest_reading = reading
                            
                            # Check if readings are stable (percentage-based)
                            stable_avg = self._reading_stats.get_stable_average()
                            if stable_avg is not None:
                                # Stable reading found! Create a stable reading
                                self._stable_reading = MultimeterReading(
                                    value=stable_avg,
                                    unit=reading.unit,
                                    measurement_type=reading.measurement_type,
                                    timestamp=reading.timestamp,
                                    test_point_id=reading.test_point_id
                                )
                                # Clear stats after finding stable reading
                                # so we can detect new probe placements
                                self._reading_stats.clear()
                                
            except Exception as e:
                # Continue on error
                pass
            
            time.sleep(0.1)  # Small delay between reads
    
    def get_latest_reading(self) -> Optional[MultimeterReading]:
        """Get the latest raw reading."""
        with self._lock:
            return self._latest_reading
    
    def get_stable_reading(self) -> Optional[MultimeterReading]:
        """Get the stable averaged reading (if available)."""
        with self._lock:
            return self._stable_reading
    
    def get_reading_with_stabilization(self, timeout: float = 10.0, measurement_type: str = "DC_VOLTAGE") -> Optional[MultimeterReading]:
        """
        Wait for stable reading with percentage-based stabilization.
        
        Algorithm:
        1. Clear previous readings
        2. Wait for readings above noise threshold (0.5V)
        3. Collect readings until stable:
           - DC Voltage: 0.5% fluctuation max
           - AC Voltage: 2.5% fluctuation max
           - Resistance: 1% fluctuation max
        4. Return the stable average
        
        Args:
            timeout: Maximum time to wait in seconds
            measurement_type: Type of measurement (DC_VOLTAGE, AC_VOLTAGE, etc.)
            
        Returns:
            Stable averaged reading, or None if timeout
        """
        with self._lock:
            self._reading_stats.clear()
            self._reading_stats.set_measurement_type(measurement_type)
            self._stable_reading = None
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._lock:
                if self._stable_reading:
                    return self._stable_reading
                # Also return latest if it's been stable for a while (percentage-based)
                if self._reading_stats.is_stable(min_readings=5):
                    avg = self._reading_stats.get_average()
                    if avg and self._latest_reading:
                        threshold_pct = self._reading_stats.get_fluctuation_threshold()
                        stable = MultimeterReading(
                            value=avg,
                            unit=self._latest_reading.unit,
                            measurement_type=self._latest_reading.measurement_type,
                            timestamp=time.time(),
                            test_point_id=self._latest_reading.test_point_id
                        )
                        return stable
            
            time.sleep(0.2)
        
        # Timeout - return whatever we have if it's reasonable
        with self._lock:
            if self._latest_reading and abs(self._latest_reading.value) > self.NOISE_THRESHOLD:
                return self._latest_reading
        
        return None
    
    def stop(self):
        """Stop the background reader."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.client:
            self.client.disconnect()
        self._is_running = False
        print("[BACKGROUND_READER] Stopped")
    
    def is_connected(self) -> bool:
        """Check if connected to multimeter."""
        return self.client is not None and self.client._connected


# Global singleton instance
_background_reader: Optional[BackgroundReader] = None
_reader_lock = threading.Lock()


def get_background_reader() -> BackgroundReader:
    """Get the global background reader instance."""
    global _background_reader
    with _reader_lock:
        if _background_reader is None:
            _background_reader = BackgroundReader()
        return _background_reader


def ensure_reader_running() -> bool:
    """Ensure the background reader is running."""
    reader = get_background_reader()
    if not reader.is_connected():
        return reader.start()
    return True
