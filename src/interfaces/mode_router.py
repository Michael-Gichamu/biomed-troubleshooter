"""
Mode Router

Routes signal input based on current mode (usb).
Implements the Strategy pattern for signal sources.
"""

import os
import json
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from src.domain.models import SignalCollection, SignalBatch, Signal, TestPoint, Measurement


class SignalSource(ABC):
    """Abstract base class for signal sources."""

    @abstractmethod
    def receive_signals(self, equipment_id: str) -> Optional[SignalBatch]:
        """Receive signals for equipment."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection if needed."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up connection."""
        pass


class USBMultimeterSource(SignalSource):
    """USB Multimeter signal source for Mastech MS8250D."""

    def __init__(self, port: Optional[str] = None):
        """
        Initialize USB multimeter source.
        
        Args:
            port: COM port (e.g., "COM3"). Auto-detects if None.
        """
        self.port = port
        self._client = None
        self._connected = False
        self._readings: List[Signal] = []
        self._reading_count = 0
        self._max_readings = 10  # Collect up to 10 readings

    def connect(self) -> bool:
        """Connect to USB multimeter."""
        try:
            from src.infrastructure.usb_multimeter import USBMultimeterClient
            
            self._client = USBMultimeterClient(port=self.port)
            if self._client.connect():
                self._connected = True
                return True
            return False
        except ImportError:
            print("[USB] pyserial not installed. Install with: pip install pyserial")
            return False
        except Exception as e:
            print(f"[USB] Connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from multimeter."""
        if self._client:
            self._client.disconnect()
        self._connected = False

    def receive_signals(self, equipment_id: str) -> Optional[SignalBatch]:
        """
        Collect readings from multimeter.
        
        Reads multiple measurements and returns them as a batch.
        """
        if not self._connected or not self._client:
            return None

        signals = []
        timestamp = datetime.utcnow().isoformat()
        
        # Collect readings
        print("\n[USB] Collecting measurements (press Enter when done)...")
        print("[USB] Reading from multimeter...")
        
        for i in range(self._max_readings):
            reading = self._client.read_measurement(timeout=5.0)
            if reading:
                signal = Signal(
                    test_point=TestPoint(
                        id=f"MM{i+1}",
                        name=f"Measurement {i+1}",
                        location="USB Multimeter"
                    ),
                    value=reading.value,
                    unit=reading.unit,
                    accuracy=0.01,  # Typical multimeter accuracy
                    measurement_type=reading.measurement_type.lower(),
                    timestamp=reading.timestamp
                )
                signals.append(signal)
                print(f"  [{i+1}] {reading.measurement_type}: {reading.value} {reading.unit}")
            else:
                break

        if not signals:
            return None

        return SignalBatch(
            timestamp=timestamp,
            equipment_id=equipment_id,
            signals=signals
        )

    def is_connected(self) -> bool:
        """Check if connected to multimeter."""
        return self._connected


class ModeRouter:
    """Routes to appropriate signal source based on mode."""

    def __init__(self):
        self.config = self._load_config()
        self._source: Optional[SignalSource] = None

    def _load_config(self) -> Dict[str, Any]:
        """Load mode configuration from environment."""
        return {
            "mode": os.getenv("APP_MODE", "usb").lower(),
            "usb_port": os.getenv("USB_PORT", None),  # Auto-detect if None
        }

    @property
    def source(self) -> SignalSource:
        """Get the active signal source (lazy initialization)."""
        if self._source is None:
            if self.config["mode"] == "usb":
                self._source = USBMultimeterSource(self.config["usb_port"])
            else:
                # Default to USB
                self._source = USBMultimeterSource(self.config.get("usb_port"))
        return self._source

    def get_mode(self) -> str:
        """Get current mode."""
        return self.config["mode"]

    def connect(self) -> bool:
        """Establish connection for active mode."""
        return self.source.connect()

    def disconnect(self) -> None:
        """Clean up connection."""
        if self._source:
            self._source.disconnect()

    def receive_signals(self, equipment_id: str) -> Optional[SignalBatch]:
        """Receive signals from active source."""
        return self.source.receive_signals(equipment_id)

    def get_mode_info(self) -> Dict[str, Any]:
        """Get information about current mode."""
        return {
            "mode": self.config["mode"],
            "usb_port": self.config["usb_port"] or "auto-detect"
        }

    def switch_mode(self, new_mode: str) -> None:
        """
        Switch to a different mode.
        
        Args:
            new_mode: "usb"
        """
        if self._source:
            self._source.disconnect()
            self._source = None

        # Update environment
        os.environ["APP_MODE"] = new_mode
        self.config["mode"] = new_mode


# =============================================================================
# Convenience Functions
# =============================================================================

def create_signal_source(mode: str = None, **kwargs) -> SignalSource:
    """
    Factory function to create a signal source.
    
    Args:
        mode: "usb". Uses APP_MODE env var if None.
        **kwargs: Additional arguments for the source
        
    Returns:
        SignalSource instance
    """
    if mode is None:
        mode = os.getenv("APP_MODE", "usb").lower()
    
    if mode == "usb":
        return USBMultimeterSource(kwargs.get("port"))
    else:
        raise ValueError(f"Unknown mode: {mode}")
