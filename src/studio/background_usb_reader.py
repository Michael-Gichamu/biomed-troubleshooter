"""
Background USB Multimeter Reader

This module provides a singleton background reader that continuously
reads from the USB multimeter and intelligently processes readings:
1. Ignores noise (very low values from air/probe handling)
2. Uses MAD-based outlier rejection for robust stabilization
3. Enforces dwell-time: requires consecutive stable samples
4. Returns the median of the stable cluster

Stabilization States:
- guidance_shown: Test point guidance was just displayed
- sampling: Actively collecting samples
- stable: Valid stable cluster found
- timeout: No stable reading after timeout
"""

import math
import threading
import time
import statistics
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from src.infrastructure.usb_multimeter import USBMultimeterClient, MultimeterReading


class MeasurementPhase(Enum):
    """State machine for measurement flow."""
    IDLE = "idle"
    GUIDANCE_SHOWN = "guidance_shown"
    SAMPLING = "sampling"
    STABLE = "stable"
    TIMEOUT = "timeout"


@dataclass
class RobustStabilizer:
    """
    Robust sensor-reading algorithm using MAD-based outlier detection.
    
    Algorithm:
    1. Maintain sliding window of recent samples
    2. Reject obvious noise and impossible values
    3. Use median-based center estimate
    4. Use MAD (Median Absolute Deviation) for robust spread measure
    5. Accept reading only when consecutive cluster stays within threshold for dwell period
    6. Return median of stable cluster, not raw mean
    """
    
    # Measurement type specific thresholds (as percentage band)
    FLUCTUATION_THRESHOLDS = {
        "AC_VOLTAGE": 7.0,      # 7% for AC
        "AC_CURRENT": 7.0,
        "DC_VOLTAGE": 3.0,      # 3% for DC - tighter threshold
        "DC_CURRENT": 3.0,
        "RESISTANCE": 2.0,      # 2% or absolute based
        "CONTINUITY": 1.0,      # Very tight for continuity
        "DEFAULT": 5.0
    }
    
    # Absolute thresholds for low-value measurements (in ohms)
    ABSOLUTE_THRESHOLDS = {
        "RESISTANCE": 0.5,     # 0.5 ohm absolute
        "CONTINUITY": 0.3,     # 0.3 ohm absolute
        "DEFAULT": 0.1         # 0.1V absolute for voltage
    }
    
    # Window and dwell configuration
    WINDOW_SIZE = 30           # Keep 30 samples in rolling window
    MIN_CLUSTER_SIZE = 5       # Minimum cluster to consider
    DWELL_REQUIRED = 3         # Must have 3 consecutive stable samples
    MIN_VALID_SAMPLES = 10      # Minimum samples before checking stability
    
    # Noise threshold - ignore readings below this
    NOISE_THRESHOLD_VOLTS = 0.1   # matches BackgroundReader.NOISE_THRESHOLD; allows sub-0.5V test points
    NOISE_THRESHOLD_OHMS = 1.0
    
    _window: deque = field(default_factory=lambda: deque(maxlen=30))
    _valid_readings: deque = field(default_factory=lambda: deque(maxlen=30))
    timestamps: list = field(default_factory=list)
    measurement_type: str = "DC_VOLTAGE"
    
    # Dwell tracking
    _consecutive_stable_count: int = 0
    _last_stable_value: Optional[float] = None
    
    # Stable cluster tracking (for trimmed mean calculation)
    _stable_min: Optional[float] = None
    _stable_max: Optional[float] = None
    _stable_sample_count: int = 0
    _stable_cluster_values: list = field(default_factory=list)
    
    # State tracking
    phase: MeasurementPhase = MeasurementPhase.IDLE
    sample_count: int = 0
    
    @property
    def readings(self) -> list:
        """Return all readings from window."""
        return list(self._window)
    
    @property
    def valid_readings(self) -> list:
        """Return only valid (above noise threshold) readings."""
        return list(self._valid_readings)
    
    # Types that share the same physical measurement mode on the meter.
    # Switching between these should NOT reset accumulated samples.
    _COMPATIBLE_GROUPS = [{"RESISTANCE", "CONTINUITY"}]

    def set_measurement_type(self, m_type: str):
        """Set the measurement type for threshold calculation.
        Only resets when the type actually changes to preserve accumulated samples.
        Compatible type transitions (e.g. RESISTANCE ↔ CONTINUITY) update the type
        but preserve samples, since they represent the same physical measurement.
        """
        new_type = m_type.upper() if m_type else "DEFAULT"
        if new_type == self.measurement_type:
            return  # Same type — preserve accumulated samples
        # Don't reset for compatible type transitions
        for group in self._COMPATIBLE_GROUPS:
            if new_type in group and self.measurement_type in group:
                self.measurement_type = new_type
                return  # update type but preserve accumulated samples
        self.measurement_type = new_type
        self.reset()
    
    def reset(self):
        """Reset all state for a new measurement."""
        self._window.clear()
        self._valid_readings.clear()
        self.timestamps.clear()
        self._consecutive_stable_count = 0
        self._last_stable_value = None
        self._stable_min = None
        self._stable_max = None
        self._stable_sample_count = 0
        self._stable_cluster_values.clear()
        self.phase = MeasurementPhase.GUIDANCE_SHOWN
        self.sample_count = 0
    
    def start_sampling(self):
        """Mark that we've started actual sampling after guidance."""
        if self.phase == MeasurementPhase.GUIDANCE_SHOWN:
            self.phase = MeasurementPhase.SAMPLING
    
    def get_fluctuation_threshold(self) -> float:
        """Get the fluctuation threshold percentage for current measurement type."""
        return self.FLUCTUATION_THRESHOLDS.get(
            self.measurement_type, 
            self.FLUCTUATION_THRESHOLDS["DEFAULT"]
        )
    
    def get_absolute_threshold(self) -> float:
        """Get absolute threshold for low-value measurements."""
        return self.ABSOLUTE_THRESHOLDS.get(
            self.measurement_type,
            self.ABSOLUTE_THRESHOLDS["DEFAULT"]
        )
    
    def _get_noise_threshold(self) -> float:
        """Get noise threshold based on measurement type."""
        if "VOLTAGE" in self.measurement_type or "CURRENT" in self.measurement_type:
            return self.NOISE_THRESHOLD_VOLTS
        elif self.measurement_type in ("RESISTANCE", "CONTINUITY"):
            return self.NOISE_THRESHOLD_OHMS
        return 0.1
    
    def add(self, reading: float) -> bool:
        """
        Add a reading to the window.
        
        Returns:
            True if reading passed noise filter and was added
        """
        self.sample_count += 1
        self._window.append(reading)
        self.timestamps.append(time.time())
        
        # Start sampling phase if still in guidance
        self.start_sampling()
        
        # Check noise threshold
        noise_threshold = self._get_noise_threshold()
        
        # For resistance/continuity, don't filter low values
        if self.measurement_type in ("RESISTANCE", "CONTINUITY"):
            self._valid_readings.append(reading)
            return True
        
        # For voltage/current, filter noise
        if reading >= noise_threshold:
            self._valid_readings.append(reading)
            return True
        
        return False
    
    def _calculate_median(self, values: list) -> float:
        """Calculate median of a list."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 0:
            return (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
        return sorted_vals[n//2]
    
    def _calculate_mad(self, values: list) -> float:
        """
        Calculate Median Absolute Deviation.
        
        MAD is a robust measure of spread that is less affected by outliers
        than standard deviation.
        
        MAD = median(|Xi - median(X)|)
        """
        if len(values) < 2:
            return 0.0
        
        median = self._calculate_median(values)
        deviations = [abs(v - median) for v in values]
        return self._calculate_median(deviations)
    
    def _is_outlier(self, value: float, center: float, mad: float, threshold_multiplier: float = 3.0) -> bool:
        """
        Determine if a value is an outlier using MAD-based test.
        
        Modified z-score = 0.6745 * (x - median) / MAD
        Values with modified z-score > threshold_multiplier are outliers
        """
        if mad == 0:
            # No spread - check absolute difference
            return abs(value - center) > self.get_absolute_threshold()
        
        modified_z = 0.6745 * abs(value - center) / mad
        return modified_z > threshold_multiplier
    
    def _find_stable_clusters(self, values: list) -> List[Tuple[int, int, float, float]]:
        """
        Find stable clusters in the readings.
        
        Returns:
            List of (start_idx, end_idx, cluster_median, cluster_mad) for each stable cluster
        """
        if len(values) < self.MIN_CLUSTER_SIZE:
            return []
        
        clusters = []
        
        # Check clusters of MIN_CLUSTER_SIZE consecutive readings
        for i in range(len(values) - self.MIN_CLUSTER_SIZE + 1):
            cluster = values[i:i + self.MIN_CLUSTER_SIZE]
            
            # Skip if cluster contains outliers
            cluster_median = self._calculate_median(cluster)
            cluster_mad = self._calculate_mad(cluster)
            
            # Calculate cluster spread
            cluster_min = min(cluster)
            cluster_max = max(cluster)
            
            # Percentage-based check
            pct_threshold = self.get_fluctuation_threshold()
            abs_threshold = self.get_absolute_threshold()
            
            if cluster_median > 0:
                pct_spread = (cluster_max - cluster_min) / cluster_median * 100
            else:
                pct_spread = float('inf')
            
            # Check against both percentage and absolute thresholds
            is_stable = (pct_spread <= pct_threshold) or ((cluster_max - cluster_min) <= abs_threshold)
            
            if is_stable:
                clusters.append((i, i + self.MIN_CLUSTER_SIZE, cluster_median, cluster_mad))
        
        return clusters
    
    def _prefer_newest_cluster(self, clusters: List[Tuple[int, int, float, float]]) -> Optional[Tuple[float, float]]:
        """
        Prefer the newest stable cluster (highest start index).
        
        Returns:
            (median, mad) of the newest stable cluster, or None
        """
        if not clusters:
            return None
        
        # Sort by start index (prefer newest), then by smallest MAD (prefer tightest)
        clusters.sort(key=lambda x: (x[0], x[3] if x[3] is not None else float('inf')))
        
        # Return the median and MAD of the newest cluster
        newest = clusters[-1]
        return (newest[2], newest[3])
    
    def is_stable(self) -> bool:
        """
        Check if we have a stable reading using robust MAD-based algorithm.
        
        Requirements:
        1. Have minimum valid samples
        2. Find at least one stable cluster
        3. Track consecutive stable samples (dwell time)
        """
        valid = self.valid_readings
        
        if len(valid) < self.MIN_VALID_SAMPLES:
            return False
        
        # Find all stable clusters
        clusters = self._find_stable_clusters(valid)
        
        if not clusters:
            # Reset dwell counter if no stable cluster
            self._consecutive_stable_count = 0
            return False
        
        # Get the newest stable cluster
        stable_result = self._prefer_newest_cluster(clusters)
        
        if stable_result is None:
            self._consecutive_stable_count = 0
            return False
        
        median_val, mad_val = stable_result
        
        # Check if this is the same stable value as last check
        if self._last_stable_value is not None:
            abs_diff = abs(median_val - self._last_stable_value)
            threshold = self.get_absolute_threshold()
            
            if abs_diff <= threshold:
                # Still stable - increment dwell counter
                self._consecutive_stable_count += 1
            else:
                # Value changed significantly - reset dwell
                self._consecutive_stable_count = 0
        else:
            # First stable detection
            self._consecutive_stable_count = 1
        
        self._last_stable_value = median_val
        
        # Check dwell requirement
        if self._consecutive_stable_count >= self.DWELL_REQUIRED:
            self.phase = MeasurementPhase.STABLE
            return True
        
        return False
    
    def get_stable_reading(self) -> Optional[float]:
        """
        Get the stable reading value using trimmed mean.
        
        Returns the trimmed mean (20% top/bottom removed) of the newest stable cluster.
        Also tracks min, max, and sample count for the stable cluster.
        """
        valid = self.valid_readings
        
        if len(valid) < self.MIN_VALID_SAMPLES:
            return None
        
        # Find stable clusters
        clusters = self._find_stable_clusters(valid)
        
        if not clusters:
            return None
        
        # Get newest stable cluster
        stable_result = self._prefer_newest_cluster(clusters)
        
        if stable_result is None:
            return None
        
        median_val, _ = stable_result
        
        # Collect cluster values from the newest samples
        cluster_values = []
        for i in range(len(valid) - self.MIN_CLUSTER_SIZE + 1, len(valid)):
            # Only consider the newest samples
            cluster_values.append(valid[i])
        
        if len(cluster_values) < 3:
            # Not enough for trimming, use median
            self._stable_min = min(cluster_values) if cluster_values else None
            self._stable_max = max(cluster_values) if cluster_values else None
            self._stable_sample_count = len(cluster_values)
            self._stable_cluster_values = cluster_values.copy()
            return median_val
        
        # Sort and calculate trimmed mean (remove top/bottom 20%)
        sorted_cluster = sorted(cluster_values)
        n = len(sorted_cluster)
        trim_count = max(1, int(n * 0.2))  # At least 1 from each side
        
        trimmed = sorted_cluster[trim_count:-trim_count] if trim_count < n else sorted_cluster
        
        # Track stable cluster statistics
        self._stable_min = min(sorted_cluster)
        self._stable_max = max(sorted_cluster)
        self._stable_sample_count = len(sorted_cluster)
        self._stable_cluster_values = sorted_cluster.copy()
        
        return statistics.mean(trimmed) if trimmed else median_val
    
    def get_stable_result(self) -> Optional[dict]:
        """
        Get the final structured result with trimmed mean and stability info.
        
        Returns:
            Dict with:
            - value: trimmed mean of stable cluster
            - min: minimum value in stable cluster
            - max: maximum value in stable cluster
            - samples: number of samples in stable cluster
            - method: "trimmed_mean"
        """
        value = self.get_stable_reading()
        
        if value is None:
            return None
        
        return {
            "value": round(value, 2),
            "min": round(self._stable_min, 2) if self._stable_min is not None else None,
            "max": round(self._stable_max, 2) if self._stable_max is not None else None,
            "samples": self._stable_sample_count,
            "method": "trimmed_mean"
        }
    
    def get_statistics(self) -> dict:
        """Get current statistics for debugging."""
        valid = self.valid_readings
        return {
            "phase": self.phase.value,
            "total_samples": self.sample_count,
            "valid_samples": len(valid),
            "consecutive_stable": self._consecutive_stable_count,
            "last_value": self._window[-1] if self._window else None,
            "median": self._calculate_median(valid) if valid else None,
            "mad": self._calculate_mad(valid) if valid else None,
            "threshold_pct": self.get_fluctuation_threshold(),
            "threshold_abs": self.get_absolute_threshold(),
            "window_values": list(self._window)[-5:] if self._window else [],  # Last 5 for debugging
            "valid_readings": list(self._valid_readings)[-5:] if self._valid_readings else []
        }


@dataclass
class BackgroundReader:
    """Singleton background reader for USB multimeter with robust stabilization."""
    
    # Noise threshold - ignore readings below this (air interference)
    # Lowered from 0.7V to 0.1V to allow legitimate low voltage readings
    NOISE_THRESHOLD = 0.1  # volts - ignore values below 0.1V
    
    client: Optional[USBMultimeterClient] = None
    _thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _latest_reading: Optional[MultimeterReading] = None
    _stable_reading: Optional[MultimeterReading] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _is_running: bool = False
    
    # Robust stabilizer for measurement
    _stabilizer: RobustStabilizer = field(default_factory=RobustStabilizer)
    _last_probe_time: float = 0.0
    _regime_change_count: int = 0  # consecutive readings far from current stable
    _last_printed_stable: Optional[float] = None  # for change-only terminal output
    
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
        """Background reading loop with noise filtering and stabilization."""
        while not self._stop_event.is_set():
            try:
                if self.client:
                    reading = self.client.read_measurement(timeout=0.5)
                    if reading and reading.value is not None:
                        value = abs(reading.value)  # Use absolute value
                        
                        # Filter noise based on measurement type
                        is_voltage = "VOLTAGE" in reading.measurement_type
                        is_ohmic = reading.measurement_type in ("RESISTANCE", "CONTINUITY")
                        if is_ohmic:
                            threshold = 0.0   # Accept all values including 0.0Ω
                        elif is_voltage:
                            threshold = self.NOISE_THRESHOLD  # 0.1V
                        else:
                            threshold = 0.01

                        if value < threshold:
                            # Too low - likely noise; skip but don't destroy
                            # accumulated samples (RobustStabilizer.add() already
                            # filters noise via its own _valid_readings gate)
                            continue

                        # Skip non-finite values (multimeter OL/overload display,
                        # parser edge cases) -- float('inf') or nan must not enter
                        # the stabilizer or appear in terminal output
                        if not math.isfinite(value):
                            continue

                        # Set measurement type for threshold calculation
                        self._stabilizer.set_measurement_type(reading.measurement_type)

                        # Add to stabilizer - check if it passes noise filter
                        with self._lock:
                            # ── Regime change detection ───────────────────────────────────
                            # If the engineer moved probes to a new test point the incoming
                            # values will be far from the current stable reading.  The
                            # RobustStabilizer's dwell counter would block the new value from
                            # ever being accepted (it keeps comparing against _last_stable_value).
                            # After 5 consecutive readings that are >50% away from current
                            # stable we reset the stabilizer so it can lock onto the new range.
                            if self._stable_reading is not None and value > 0:
                                stable_val = self._stable_reading.value
                                relative_diff = abs(value - stable_val) / max(abs(stable_val), 1.0)
                                if relative_diff > 0.50:   # >50% away from last stable
                                    self._regime_change_count += 1
                                    if self._regime_change_count >= 5:
                                        self._stabilizer.reset()
                                        self._stable_reading = None
                                        self._regime_change_count = 0
                                        print(f"[BACKGROUND_READER] Regime change: "
                                              f"{round(stable_val, 2)} -> {round(value, 2)}"
                                              f" -- stabilizer reset")
                                else:
                                    self._regime_change_count = 0
                            else:
                                self._regime_change_count = 0

                            was_added = self._stabilizer.add(value)
                            self._latest_reading = reading

                            if was_added:
                                # Check if readings are now stable
                                if self._stabilizer.is_stable():
                                    stable_val = self._stabilizer.get_stable_reading()
                                    if stable_val is not None:
                                        # Stable reading found! Create a stable reading
                                        self._stable_reading = MultimeterReading(
                                            raw_value=f"stable:{stable_val}",
                                            value=stable_val,
                                            unit=reading.unit,
                                            measurement_type=reading.measurement_type,
                                            timestamp=reading.timestamp,
                                            test_point_id=reading.test_point_id
                                        )
                                        # Note: Don't clear stabilizer - allow continuous monitoring
                                        rounded = round(stable_val, 3)
                                        if self._last_printed_stable != rounded:
                                            print(f"[BACKGROUND_READER] Stable reading: "
                                                  f"{rounded} {reading.unit}")
                                            self._last_printed_stable = rounded
                                
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
    
    def get_reading_with_stabilization(
        self, 
        timeout: float = 10.0, 
        measurement_type: str = "DC_VOLTAGE"
    ) -> Optional[MultimeterReading]:
        """
        Wait for stable reading with robust MAD-based stabilization.
        
        Algorithm:
        1. Set measurement type (only resets if type changed)
        2. Clear stable-reading flag to re-evaluate freshly
        3. Wait for minimum valid samples (10+)
        4. Check for stable cluster using MAD-based outlier rejection
        5. Require dwell time: 3 consecutive stable samples
        6. Return median of stable cluster
        
        Args:
            timeout: Maximum time to wait in seconds
            measurement_type: Type of measurement (DC_VOLTAGE, AC_VOLTAGE, etc.)
            
        Returns:
            Stable reading, or None if timeout
        """
        print(f"[DEBUG] get_reading_with_stabilization called: type={measurement_type}, timeout={timeout}")

        # How long to wait after Resume before accepting any reading.
        # The engineer needs to walk back to the test point and place both probes.
        PROBE_SETTLE_SECS = 5.0

        with self._lock:
            # Set measurement type and ALWAYS reset so pre-Resume data is discarded.
            # Without this reset the stabilizer's dwell counter is still satisfied
            # from the previous measurement and will return stale data instantly.
            self._stabilizer.set_measurement_type(measurement_type)
            self._stabilizer.reset()            # discard all pre-Resume samples
            self._stable_reading = None
            self._regime_change_count = 0       # reset alongside stabilizer

        probe_settle_end = time.time() + PROBE_SETTLE_SECS
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(0.2)

            # Don't accept any reading during the settle window -- the engineer
            # is still walking back to the test point after pressing Resume.
            if time.time() < probe_settle_end:
                continue

            with self._lock:
                # Check if background loop already promoted a stable reading
                if self._stable_reading and math.isfinite(self._stable_reading.value):
                    print(f"[DEBUG] Returning stable reading: {self._stable_reading.value}")
                    return self._stable_reading

                # Check stabilizer directly
                if self._stabilizer.is_stable():
                    stable_val = self._stabilizer.get_stable_reading()
                    if stable_val is not None and math.isfinite(stable_val) and self._latest_reading:
                        print(f"[DEBUG] Stabilizer indicates stable, value={stable_val}")
                        self._stable_reading = MultimeterReading(
                            raw_value=f"stabilized:{stable_val}",
                            value=stable_val,
                            unit=self._latest_reading.unit,
                            measurement_type=self._latest_reading.measurement_type,
                            timestamp=datetime.utcnow().isoformat(),
                            test_point_id=self._latest_reading.test_point_id
                        )
                        return self._stable_reading

                # Debug: show statistics periodically
                if self._stabilizer.sample_count % 20 == 0 and self._stabilizer.sample_count > 0:
                    stats = self._stabilizer.get_statistics()
                    print(f"[DEBUG] Stabilizer stats: {stats}")

        # Timeout - return best effort reading if we have any valid data
        with self._lock:
            print(f"[DEBUG] Timeout. Stabilizer stats: {self._stabilizer.get_statistics()}")

            # Try to return whatever stable reading we might have
            if self._stable_reading and math.isfinite(self._stable_reading.value):
                return self._stable_reading

            # If we have valid readings but no stability, try to return median
            valid = self._stabilizer.valid_readings
            if len(valid) >= 5 and self._latest_reading:
                median_val = self._stabilizer._calculate_median(valid[-10:])  # Last 10
                if math.isfinite(median_val):
                    print(f"[DEBUG] No stable reading, returning median of last 10: {median_val}")
                    return MultimeterReading(
                        raw_value=f"median:{median_val}",
                        value=median_val,
                        unit=self._latest_reading.unit,
                        measurement_type=self._latest_reading.measurement_type,
                        timestamp=datetime.utcnow().isoformat(),
                        test_point_id=self._latest_reading.test_point_id
                    )

            # Last resort: return latest if above noise threshold and finite
            if (self._latest_reading
                    and math.isfinite(self._latest_reading.value)
                    and abs(self._latest_reading.value) > self._stabilizer._get_noise_threshold()):
                print(f"[DEBUG] Timeout, returning latest: {self._latest_reading.value}")
                return self._latest_reading

        print(f"[DEBUG] Complete timeout - no readings")
        return None
    
    def get_sample_count(self) -> int:
        """Get the number of samples collected."""
        with self._lock:
            return self._stabilizer.sample_count
    
    def get_stabilizer_stats(self) -> dict:
        """Get current stabilizer statistics."""
        with self._lock:
            return self._stabilizer.get_statistics()
    
    def get_stable_result(self) -> Optional[dict]:
        """
        Get the structured stable result with trimmed mean and stability info.
        
        Returns:
            Dict with value, min, max, samples, method, or None if not stable.
        """
        with self._lock:
            return self._stabilizer.get_stable_result()
    
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