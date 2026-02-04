"""
Equipment Configuration Loader

Loads and manages equipment-specific configurations from YAML files.
All equipment knowledge lives in data files - NO hard-coded logic.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path
import yaml


@dataclass
class SignalConfig:
    """Configuration for a single signal."""
    signal_id: str
    name: str
    test_point: str
    parameter: str
    unit: str
    measurability: str = "internal"

    @classmethod
    def from_dict(cls, data: dict) -> "SignalConfig":
        return cls(
            signal_id=data["signal_id"],
            name=data["name"],
            test_point=data["test_point"],
            parameter=data["parameter"],
            unit=data["unit"],
            measurability=data.get("measurability", "internal")
        )


@dataclass
class ThresholdState:
    """A semantic state with numerical boundaries."""
    name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "ThresholdState":
        return cls(
            name=name,
            min_value=data.get("min"),
            max_value=data.get("max"),
            description=data.get("description", "")
        )


@dataclass
class ThresholdConfig:
    """Threshold configuration for a signal."""
    signal_id: str
    states: Dict[str, ThresholdState] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ThresholdConfig":
        states = {}
        for name, value in data.get("states", {}).items():
            states[name] = ThresholdState.from_dict(name, value)
        return cls(signal_id=data["signal_id"], states=states)

    def get_state(self, value: float) -> Optional[str]:
        """Determine semantic state from raw value."""
        for name, state in self.states.items():
            if state.min_value is not None and value < state.min_value:
                continue
            if state.max_value is not None and value > state.max_value:
                continue
            return name
        return None


@dataclass
class RecoveryStep:
    """A single recovery step."""
    step: int
    action: str
    target: str
    instruction: str
    verification: str = ""
    safety: str = ""
    estimated_time: str = ""
    difficulty: str = ""
    tools: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "RecoveryStep":
        return cls(
            step=data["step"],
            action=data["action"],
            target=data["target"],
            instruction=data["instruction"],
            verification=data.get("verification", ""),
            safety=data.get("safety", ""),
            estimated_time=data.get("estimated_time", ""),
            difficulty=data.get("difficulty", ""),
            tools=data.get("tools", [])
        )


@dataclass
class FaultHypothesis:
    """A hypothesis about the cause of a fault."""
    rank: int
    component: str
    failure_mode: str
    cause: str
    confidence: float

    @classmethod
    def from_dict(cls, data: dict) -> "FaultHypothesis":
        return cls(
            rank=data["rank"],
            component=data["component"],
            failure_mode=data["failure_mode"],
            cause=data["cause"],
            confidence=data["confidence"]
        )


@dataclass
class FaultConfig:
    """Configuration for a fault."""
    fault_id: str
    name: str
    description: str
    signatures: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[FaultHypothesis] = field(default_factory=list)
    recovery: List[RecoveryStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "FaultConfig":
        hypotheses = [FaultHypothesis.from_dict(h) for h in data.get("hypotheses", [])]
        recovery = [RecoveryStep.from_dict(r) for r in data.get("recovery", [])]
        return cls(
            fault_id=data["fault_id"],
            name=data["name"],
            description=data["description"],
            signatures=data.get("signatures", []),
            hypotheses=hypotheses,
            recovery=recovery
        )

    def get_best_hypothesis(self) -> Optional[FaultHypothesis]:
        """Get the highest-ranked hypothesis."""
        if not self.hypotheses:
            return None
        return min(self.hypotheses, key=lambda h: h.rank)


@dataclass
class ImageConfig:
    """Configuration for a reference image."""
    image_id: str
    filename: str
    description: str
    test_points: List[str] = field(default_factory=list)
    annotations: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ImageConfig":
        return cls(
            image_id=data["image_id"],
            filename=data["filename"],
            description=data["description"],
            test_points=data.get("test_points", []),
            annotations=data.get("annotations", [])
        )

    def get_annotation(self, test_point: str) -> Optional[Dict[str, str]]:
        """Get annotation for a specific test point."""
        for ann in self.annotations:
            if ann.get("target") == test_point:
                return ann
        return None


@dataclass
class EquipmentMetadata:
    """Equipment metadata."""
    equipment_id: str
    name: str
    category: str
    manufacturer: str
    version: str
    created: str

    @classmethod
    def from_dict(cls, data: dict) -> "EquipmentMetadata":
        return cls(
            equipment_id=data["equipment_id"],
            name=data["name"],
            category=data["category"],
            manufacturer=data.get("manufacturer", ""),
            version=data["version"],
            created=data["created"]
        )


@dataclass
class EquipmentConfig:
    """
    Complete equipment configuration.

    All equipment-specific knowledge is loaded from this configuration.
    NO hard-coded logic should exist in the agent code.
    """
    metadata: EquipmentMetadata
    signals: Dict[str, SignalConfig] = field(default_factory=dict)
    thresholds: Dict[str, ThresholdConfig] = field(default_factory=dict)
    faults: Dict[str, FaultConfig] = field(default_factory=dict)
    images: Dict[str, ImageConfig] = field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: str) -> "EquipmentConfig":
        """Load equipment config from YAML file."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        metadata = EquipmentMetadata.from_dict(data["metadata"])

        signals = {}
        for s in data.get("signals", []):
            signal = SignalConfig.from_dict(s)
            signals[signal.signal_id] = signal

        thresholds = {}
        for t in data.get("thresholds", []):
            threshold = ThresholdConfig.from_dict(t)
            thresholds[threshold.signal_id] = threshold

        faults = {}
        for f in data.get("faults", []):
            fault = FaultConfig.from_dict(f)
            faults[fault.fault_id] = fault

        images = {}
        for i in data.get("images", []):
            image = ImageConfig.from_dict(i)
            images[image.image_id] = image

        return cls(
            metadata=metadata,
            signals=signals,
            thresholds=thresholds,
            faults=faults,
            images=images
        )

    def get_signal(self, signal_id: str) -> Optional[SignalConfig]:
        """Get signal configuration by ID."""
        return self.signals.get(signal_id)

    def get_threshold(self, signal_id: str) -> Optional[ThresholdConfig]:
        """Get threshold configuration by signal ID."""
        return self.thresholds.get(signal_id)

    def interpret_signal(self, signal_id: str, value: float) -> Optional[str]:
        """Interpret a signal value to get semantic state."""
        threshold = self.get_threshold(signal_id)
        if threshold:
            return threshold.get_state(value)
        return None

    def find_fault(self, signal_states: Dict[str, str]) -> Optional[FaultConfig]:
        """
        Find matching fault based on observed signal states.

        Returns the first fault whose signatures match the observed states.
        """
        for fault in self.faults.values():
            if self._matches_fault(fault, signal_states):
                return fault
        return None

    def _matches_fault(self, fault: FaultConfig, signal_states: Dict[str, str]) -> bool:
        """Check if fault signatures match observed signal states."""
        for sig in fault.signatures:
            sig_signal_id = sig.get("signal_id")
            sig_state = sig.get("state")
            observed_state = signal_states.get(sig_signal_id)
            if observed_state != sig_state:
                return False
        return True

    def get_image(self, image_id: str) -> Optional[ImageConfig]:
        """Get image configuration by ID."""
        return self.images.get(image_id)

    def get_image_for_test_point(self, test_point: str) -> Optional[ImageConfig]:
        """Get an image that shows a specific test point."""
        for image in self.images.values():
            if test_point in image.test_points:
                return image
        return None


class EquipmentConfigLoader:
    """
    Loader for equipment configurations.

    Manages loading and caching of equipment configs.
    """

    def __init__(self, config_dir: str = "data/equipment"):
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, EquipmentConfig] = {}

    def load(self, equipment_id: str) -> EquipmentConfig:
        """
        Load equipment configuration.

        Args:
            equipment_id: The equipment ID (e.g., "cctv-psu-24w-v1")

        Returns:
            EquipmentConfig object

        Raises:
            FileNotFoundError: If equipment config file doesn't exist
        """
        # Check cache first
        if equipment_id in self._cache:
            return self._cache[equipment_id]

        # Load from file
        file_path = self.config_dir / f"{equipment_id}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Equipment config not found: {file_path}")

        config = EquipmentConfig.from_file(str(file_path))

        # Cache for future use
        self._cache[equipment_id] = config

        return config

    def load_all(self) -> Dict[str, EquipmentConfig]:
        """Load all equipment configurations from the config directory."""
        configs = {}
        for file_path in self.config_dir.glob("*.yaml"):
            equipment_id = file_path.stem
            configs[equipment_id] = self.load(equipment_id)
        return configs

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()


# Singleton loader instance
_loader: Optional[EquipmentConfigLoader] = None


def get_equipment_config(equipment_id: str) -> EquipmentConfig:
    """Get equipment configuration by ID."""
    global _loader
    if _loader is None:
        _loader = EquipmentConfigLoader()
    return _loader.load(equipment_id)
