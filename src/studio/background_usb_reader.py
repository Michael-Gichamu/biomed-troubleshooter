"""
Background USB Multimeter Reader

This module provides a singleton background reader that continuously
reads from the USB multimeter and intelligently processes readings:
1. Ignores noise (very low values from air/probe handling)
2. Uses sliding window to find stable readings
3. Returns the stable average when values settle
"""

import threading
import time
import statistics
from typing import Optional
from dataclasses import dataclass, field
from collections import deque

from src.infrastructure.usb_multimeter import USBMultimeterClient, MultimeterReading


@dataclass
class ReadingStats:
    """Track reading statistics using sliding window for stabilization detection."""
    # Fluctuation thresholds by measurement type (as percentage)
    # Increased to be more robust for "real-world" probe handling
    FLUCTUATION_THRESHOLDS = {
        "AC_VOLTAGE": 10.0,      # 10% for AC
        "AC_CURRENT": 10.0,
        "DC_VOLTAGE": 7.0,       # 7% for DC (was 2%)
        "DC_CURRENT": 7.0,
        "RESISTANCE": 5.0,
        "DEFAULT": 7.0
    }
    
    # Sliding window size for stability check
    WINDOW_SIZE = 20
    
    # Noise threshold - ignore readings below this (air interference)
    NOISE_THRESHOLD = 0.5  # volts - ignore values below 0.5V
    
    # Use deque for sliding window
    _window: deque = field(default_factory=lambda: deque(maxlen=20))
    timestamps: list = field(default_factory=list)
    measurement_type: str = "DC_VOLTAGE"
    
    @property
    def readings(self) -> list:
        """Return readings list from window."""
        return list(self._window)
    
    def set_measurement_type(self, m_type: str):
        """Set the measurement type for threshold calculation."""
        self.measurement_type = m_type.upper() if m_type else "DEFAULT"
        self.clear()
    
    def add(self, reading: float):
        """Add a reading to the sliding window."""
        self._window.append(reading)
        self.timestamps.append(time.time())
    
    def clear(self):
        """Clear all readings."""
        self._window.clear()
        self.timestamps.clear()
    
    def get_fluctuation_threshold(self) -> float:
        """Get the fluctuation threshold percentage for current measurement type."""
        return self.FLUCTUATION_THRESHOLDS.get(self.measurement_type, self.FLUCTUATION_THRESHOLDS["DEFAULT"])
    
    def has_valid_readings(self) -> bool:
        """Check if we have enough valid readings (above noise threshold)."""
        valid_count = sum(1 for v in self._window if v >= self.NOISE_THRESHOLD)
        return valid_count >= 5
    
    def is_stable(self) -> bool:
        """Check if recent readings are stable using sub-sequence clustering.
        
        Look for at least 5 consecutive readings within the last WINDOW_SIZE
        that have low fluctuation.
        """
        readings = self.readings
        if len(readings) < 5:
            return False
            
        # Filter noise internally
        valid = [v for v in readings if v >= self.NOISE_THRESHOLD]
        if len(valid) < 5:
            return False
            
        # Check sub-sequences of length 5
        for i in range(len(valid) - 4):
            cluster = valid[i:i+5]
            mean = statistics.mean(cluster)
            if mean == 0: continue
            
            # Robust stability check: (max - min) / mean
            fluctuation = (max(cluster) - min(cluster)) / mean * 100
            
            if fluctuation <= self.get_fluctuation_threshold():
                return True
                
        return False
    
    def get_stable_average(self) -> Optional[float]:
        """Get average of the stable cluster with outlier rejection."""
        readings = self.readings
        # Filter noise
        valid = [v for v in readings if v >= self.NOISE_THRESHOLD]
        
        if len(valid) < 5:
            return None
            
        # Find the latest stable cluster (last 5 readings)
        # We prioritize the LATEST stable behavior
        for i in range(len(valid) - 5, -1, -1):
            cluster = valid[i:i+5]
            mean = statistics.mean(cluster)
            if mean < 0.01: continue # Avoid division by near-zero
            
            fluctuation = (max(cluster) - min(cluster)) / mean * 100
            
            # Also support a fixed epsilon (0.1V) for very stable but low readings
            is_tight_epsilon = (max(cluster) - min(cluster)) <= 0.1
            
            if fluctuation <= self.get_fluctuation_threshold() or is_tight_epsilon:
                # Stable cluster found! Apply outlier rejection (trim ends)
                sorted_cluster = sorted(cluster)
                # Trim min and max, average middle 3
                trimmed = sorted_cluster[1:4]
                return statistics.mean(trimmed)
                
        return None
    
    def get_last_valid_readings(self, count: int = 3) -> list:
        """Get the last N valid readings (above noise threshold)."""
        valid_readings = [v for v in self._window if v >= self.NOISE_THRESHOLD]
        return valid_readings[-count:] if len(valid_readings) >= count else valid_readings


@dataclass
class BackgroundReader:
    """Singleton background reader for USB multimeter with noise filtering."""
    
    # Noise threshold - ignore readings below this (air interference)
    NOISE_THRESHOLD = 0.7  # volts - ignore values below 0.7V
    
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
           - DC Voltage: 3% fluctuation max
           - AC Voltage: 7.5% fluctuation max
           - Resistance: 2% fluctuation max
        4. Return the stable average
        
        Args:
            timeout: Maximum time to wait in seconds
            measurement_type: Type of measurement (DC_VOLTAGE, AC_VOLTAGE, etc.)
            
        Returns:
            Stable averaged reading, or None if timeout
        """
        print(f"[DEBUG] get_reading_with_stabilization called: type={measurement_type}, timeout={timeout}")
        
        with self._lock:
            self._reading_stats.clear()
            self._reading_stats.set_measurement_type(measurement_type)
            self._stable_reading = None
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._lock:
                if self._stable_reading:
                    print(f"[DEBUG] Returning stable reading: {self._stable_reading.value}")
                    return self._stable_reading
                # Also return latest if it's been stable for a while (percentage-based)
                if self._reading_stats.is_stable():
                    avg = self._reading_stats.get_average()
                    if avg and self._latest_reading:
                        print(f"[DEBUG] Readings stable, avg={avg}, latest={self._latest_reading.value}")
                        threshold_pct = self._reading_stats.get_fluctuation_threshold()
                        stable = MultimeterReading(
                            value=avg,
                            unit=self._latest_reading.unit,
                            measurement_type=self._latest_reading.measurement_type,
                            timestamp=time.time(),
                            test_point_id=self._latest_reading.test_point_id
                        )
                        return stable
                
                # Debug: show readings status
                if self._reading_stats.readings:
                    print(f"[DEBUG] Current readings: {self._reading_stats.readings}, count={len(self._reading_stats.readings)}")
            
            time.sleep(0.2)
        
        # Timeout - return whatever we have if it's reasonable
        with self._lock:
            print(f"[DEBUG] Timeout. Latest reading: {self._latest_reading}, readings collected: {self._reading_stats.readings}")
            if self._latest_reading and abs(self._latest_reading.value) > self._reading_stats.NOISE_THRESHOLD:
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
        print(f"[DEBUG] Background reader not connected, attempting to start...")
        result = reader.start()
        print(f"[DEBUG] Background reader start result: {result}")
        return result
    print(f"[DEBUG] Background reader already connected")
    return True
