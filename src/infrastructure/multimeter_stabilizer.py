"""
Multimeter Stabilization Engine

Provides stable reading extraction from noisy multimeter measurements using
statistical algorithms including rolling window stability detection, trimmed mean,
and cluster detection.
"""

import time
from typing import Optional

# Try to use numpy for statistical calculations, fall back to statistics module
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    import statistics
    HAS_NUMPY = False


class MultimeterStabilizer:
    """
    Stabilizes multimeter readings by filtering noise and applying statistical algorithms.
    
    Supports rolling window stability detection, trimmed mean filtering,
    cluster detection for outlier identification, and context-aware zero detection.
    """
    
    def __init__(
        self,
        max_samples: int = 50,
        min_samples: int = 5,
        max_duration: float = 180.0,
        window_size: int = 10,
        stability_threshold: float = 0.01,
        cluster_tolerance: float = 0.05,
        zero_threshold: float = 0.01
    ):
        """
        Initialize the MultimeterStabilizer.
        
        Args:
            max_samples: Maximum number of samples to keep in buffer (default: 50)
            min_samples: Minimum samples required for stabilization (default: 5)
            max_duration: Maximum time window in seconds (default: 180)
            window_size: Size of rolling window for stability detection (default: 10)
            stability_threshold: Std dev threshold for stability (default: 0.01)
            cluster_tolerance: Tolerance for cluster detection as fraction (default: 0.05 = ±5%)
            zero_threshold: Threshold below which values are considered zero (default: 0.01)
        """
        self.max_samples = max_samples
        self.min_samples = min_samples
        self.max_duration = max_duration
        self.window_size = window_size
        self.stability_threshold = stability_threshold
        self.cluster_tolerance = cluster_tolerance
        self.zero_threshold = zero_threshold
        
        # Sample storage
        self._samples: list[tuple[float, float]] = []  # (value, timestamp)
        
    def add_sample(self, value: float, timestamp: Optional[float] = None) -> dict:
        """
        Add a new sample and return current stabilization status.
        
        Args:
            value: The multimeter reading value
            timestamp: Optional timestamp (defaults to current time)
            
        Returns:
            Dictionary with current stabilization status
        """
        if timestamp is None:
            timestamp = time.time()
            
        # Add sample to buffer
        self._samples.append((value, timestamp))
        
        # Trim old samples beyond max_samples
        if len(self._samples) > self.max_samples:
            self._samples = self._samples[-self.max_samples:]
        
        # Trim samples beyond max_duration
        current_time = timestamp
        self._samples = [
            (v, t) for v, t in self._samples
            if current_time - t <= self.max_duration
        ]
        
        # Return current status
        return self.get_stable_reading()
        
    def get_stable_reading(self) -> dict:
        """
        Get the final stabilized reading using the stabilization algorithm.
        
        Applies:
        1. Rolling window stability check
        2. Trimmed mean if not stable
        3. Cluster detection if trimmed mean not applicable
        4. Zero reading validation
        
        Returns:
            Dictionary with:
                - value: stabilized reading
                - confidence: "HIGH" | "MEDIUM" | "LOW"
                - samples_used: number of samples used
                - stability_status: "stable" | "stabilizing" | "unstable"
        """
        if len(self._samples) < self.min_samples:
            return {
                "value": self._samples[-1][0] if self._samples else 0.0,
                "confidence": "LOW",
                "samples_used": len(self._samples),
                "stability_status": "stabilizing"
            }
        
        # Extract values
        values = [v for v, t in self._samples]
        
        # Get rolling window for stability check
        window = values[-self.window_size:]
        if len(window) < 5:
            window = values
        
        # Check stability
        is_stable = self._is_stable(window)
        
        if is_stable:
            # If stable, return mean of stable window
            if HAS_NUMPY:
                value = float(np.mean(window))
            else:
                value = statistics.mean(window)
                
            return {
                "value": value,
                "confidence": "HIGH",
                "samples_used": len(window),
                "stability_status": "stable"
            }
        
        # Not stable - apply trimmed mean
        trimmed_value = self._apply_trimmed_mean(values)
        
        # Apply cluster detection
        cluster_value, cluster_count, cluster_variance = self._apply_cluster_detection(values)
        
        # Use cluster result if it has more samples or lower variance
        if cluster_count > len(values) * 0.3:  # At least 30% of samples in cluster
            final_value = cluster_value
            confidence = "MEDIUM" if cluster_variance < self.stability_threshold * 10 else "LOW"
        else:
            final_value = trimmed_value
            confidence = "MEDIUM"
            
        # Check for zero reading validity
        if abs(final_value) < self.zero_threshold:
            if self._is_zero_reading_valid(values):
                # Zero is valid fault reading - keep it
                confidence = "HIGH"
        
        # Determine stability status
        if len(self._samples) < self.min_samples:
            stability_status = "stabilizing"
        elif is_stable:
            stability_status = "stable"
        else:
            stability_status = "unstable"
            
        return {
            "value": final_value,
            "confidence": confidence,
            "samples_used": len(values),
            "stability_status": stability_status
        }
        
    def _calculate_std_dev(self, values: list[float]) -> float:
        """
        Calculate standard deviation of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Standard deviation
        """
        if len(values) < 2:
            return 0.0
            
        if HAS_NUMPY:
            return float(np.std(values))
        else:
            return statistics.stdev(values) if len(values) > 1 else 0.0
            
    def _is_stable(self, window: list[float]) -> bool:
        """
        Check if the rolling window is stable based on standard deviation.
        
        Args:
            window: List of values in the rolling window
            
        Returns:
            True if stable (std_dev < threshold), False otherwise
        """
        if len(window) < 5:
            return False
            
        std_dev = self._calculate_std_dev(window)
        
        # Calculate relative threshold based on mean
        if HAS_NUMPY:
            mean = float(np.mean(window))
        else:
            mean = statistics.mean(window)
            
        if abs(mean) < self.zero_threshold:
            # For near-zero values, use absolute threshold
            return std_dev < self.stability_threshold
            
        # Use relative threshold (std_dev / mean < threshold)
        relative_std = std_dev / abs(mean)
        return relative_std < self.stability_threshold
        
    def _apply_trimmed_mean(self, samples: list[float]) -> float:
        """
        Apply trimmed mean - sort samples and remove top/bottom 10%.
        
        Args:
            samples: List of sample values
            
        Returns:
            Trimmed mean value
        """
        if len(samples) < 3:
            return samples[0] if samples else 0.0
            
        # Sort samples
        sorted_samples = sorted(samples)
        
        # Calculate number to trim (10% on each side)
        trim_count = max(1, int(len(sorted_samples) * 0.1))
        
        # Trim from both ends
        trimmed = sorted_samples[trim_count:-trim_count] if trim_count > 0 else sorted_samples
        
        if not trimmed:
            return sorted_samples[0] if sorted_samples else 0.0
            
        if HAS_NUMPY:
            return float(np.mean(trimmed))
        else:
            return statistics.mean(trimmed)
            
    def _apply_cluster_detection(self, samples: list[float]) -> tuple[float, int, float]:
        """
        Apply cluster detection - group values within ±tolerance and select best cluster.
        
        Selects cluster with highest count, then lowest variance.
        
        Args:
            samples: List of sample values
            
        Returns:
            Tuple of (cluster_value, cluster_count, cluster_variance)
        """
        if len(samples) < 2:
            return (samples[0] if samples else 0.0, len(samples), 0.0)
            
        # Sort samples for clustering
        sorted_samples = sorted(samples)
        
        # Find clusters
        clusters: list[list[float]] = []
        current_cluster = [sorted_samples[0]]
        
        for i in range(1, len(sorted_samples)):
            # Calculate tolerance based on current cluster mean
            cluster_mean = sum(current_cluster) / len(current_cluster)
            tolerance = abs(cluster_mean) * self.cluster_tolerance
            
            # Use minimum tolerance for near-zero values
            if cluster_mean == 0:
                tolerance = self.zero_threshold
                
            # Check if current value fits in cluster
            if abs(sorted_samples[i] - cluster_mean) <= max(tolerance, self.zero_threshold):
                current_cluster.append(sorted_samples[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [sorted_samples[i]]
                
        # Add final cluster
        clusters.append(current_cluster)
        
        # Select best cluster based on:
        # 1. Highest count
        # 2. Lowest variance (tie-breaker)
        best_cluster = None
        best_count = 0
        best_variance = float('inf')
        
        for cluster in clusters:
            count = len(cluster)
            variance = self._calculate_variance(cluster)
            
            if count > best_count or (count == best_count and variance < best_variance):
                best_count = count
                best_variance = variance
                best_cluster = cluster
                
        if best_cluster is None:
            return (0.0, 0, float('inf'))
            
        # Return cluster mean, count, and variance
        cluster_mean = sum(best_cluster) / len(best_cluster)
        return (cluster_mean, best_count, best_variance)
        
    def _calculate_variance(self, values: list[float]) -> float:
        """
        Calculate variance of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Variance
        """
        if len(values) < 2:
            return 0.0
            
        if HAS_NUMPY:
            return float(np.var(values))
        else:
            return statistics.variance(values) if len(values) > 1 else 0.0
            
    def _is_zero_reading_valid(self, samples: list[float]) -> bool:
        """
        Determine if zero reading is valid (fault condition) or noise.
        
        Rule:
        - If majority of samples ≈ 0 → VALID (fault condition)
        - If minority of samples ≈ 0 → treat as noise
        
        Args:
            samples: List of sample values
            
        Returns:
            True if zero is valid fault reading, False if noise
        """
        if not samples:
            return False
            
        # Count samples near zero
        zero_count = sum(1 for v in samples if abs(v) < self.zero_threshold)
        total_count = len(samples)
        
        # Majority rule - if more than 50% are near zero, it's valid
        return zero_count > total_count / 2
        
    def reset(self) -> None:
        """Clear all stored samples."""
        self._samples.clear()
        
    def get_sample_count(self) -> int:
        """Get current number of stored samples."""
        return len(self._samples)
        
    @property
    def samples(self) -> list[tuple[float, float]]:
        """Get all stored samples as list of (value, timestamp) tuples."""
        return self._samples.copy()
