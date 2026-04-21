"""
Equipment Configuration Loader

Loads and manages equipment-specific configurations from YAML files.
All equipment knowledge lives in data files - NO hard-coded logic.
"""

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.infrastructure.config import get_image_base_url

# Equipment IDs are slugs: lowercase letters, digits, and hyphens.
# Enforced length cap protects against oversized LLM-extracted inputs.
_EQUIPMENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
_EQUIPMENT_ID_MAX_LEN = 64


class InvalidEquipmentIdError(ValueError):
    """Raised when an equipment_id fails validation before any file I/O."""


def _validate_equipment_id(equipment_id: str) -> str:
    """Reject malformed or dangerous equipment IDs before touching the filesystem.

    Raises InvalidEquipmentIdError for anything that is not a simple slug.
    Prevents path traversal (``../``), absolute paths, null bytes, and
    separator injection from user-controlled LLM extraction.
    """
    if not isinstance(equipment_id, str) or not equipment_id:
        raise InvalidEquipmentIdError("equipment_id must be a non-empty string")
    if len(equipment_id) > _EQUIPMENT_ID_MAX_LEN:
        raise InvalidEquipmentIdError(
            f"equipment_id exceeds {_EQUIPMENT_ID_MAX_LEN} chars"
        )
    if not _EQUIPMENT_ID_PATTERN.match(equipment_id):
        raise InvalidEquipmentIdError(
            f"equipment_id must match slug pattern (got: {equipment_id!r})"
        )
    return equipment_id


def get_full_image_url(image_path: str) -> str:
    """Construct full image URL from relative path using configured IMAGE_BASE_URL.
    
    Args:
        image_path: Relative path to image (e.g., "cctv-psu-24w-v1-test-points/image.png")
                    or full URL (which will be returned as-is)
    
    Returns:
        Full URL - either the input URL if already complete, or with IMAGE_BASE_URL prepended
    """
    if not image_path:
        return ""
    
    # If it's already a full URL (GitHub RAW, etc.), return as-is
    if image_path.startswith('http://') or image_path.startswith('https://'):
        return image_path
    
    # Otherwise, use the configured base URL
    base_url = get_image_base_url().rstrip('/')
    if not base_url:
        # No base URL configured, return relative path as-is
        return image_path
    
    return f"{base_url}/{image_path.lstrip('/')}"


@dataclass
class SignalConfig:
    """Configuration for a single signal."""
    signal_id: str
    name: str
    test_point: str
    parameter: str
    unit: str
    measurability: str = "internal"
    physical_description: str | None = ""
    image_url: str | None = ""
    pro_tips: list[str] = field(default_factory=list)
    probe_placement: str | None = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SignalConfig":
        return cls(
            signal_id=data["signal_id"],
            name=data["name"],
            test_point=data["test_point"],
            parameter=data["parameter"],
            unit=data["unit"],
            measurability=data.get("measurability", "internal"),
            physical_description=data.get("physical_description", ""),
            image_url=data.get("image_url", ""),
            pro_tips=data.get("pro_tips", []),
            probe_placement=data.get("probe_placement", "")
        )


@dataclass
class ThresholdState:
    """A semantic state with numerical boundaries."""
    name: str
    min_value: float | None = None
    max_value: float | None = None
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
    states: dict[str, ThresholdState] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ThresholdConfig":
        states = {}
        for name, value in data.get("states", {}).items():
            states[name] = ThresholdState.from_dict(name, value)
        return cls(signal_id=data["signal_id"], states=states)

    def get_state(self, value: float) -> str | None:
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
    tools: list[str] = field(default_factory=list)

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
    priority: int = 999  # Lower number = higher priority
    signatures: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[FaultHypothesis] = field(default_factory=list)
    recovery: list[RecoveryStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "FaultConfig":
        hypotheses = [FaultHypothesis.from_dict(h) for h in data.get("hypotheses", [])]
        recovery = [RecoveryStep.from_dict(r) for r in data.get("recovery", [])]
        return cls(
            fault_id=data["fault_id"],
            name=data["name"],
            description=data["description"],
            priority=data.get("priority", 999),
            signatures=data.get("signatures", []),
            hypotheses=hypotheses,
            recovery=recovery
        )

    def get_best_hypothesis(self) -> FaultHypothesis | None:
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
    test_points: list[str] = field(default_factory=list)
    annotations: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ImageConfig":
        return cls(
            image_id=data["image_id"],
            filename=data["filename"],
            description=data["description"],
            test_points=data.get("test_points", []),
            annotations=data.get("annotations", [])
        )

    def get_annotation(self, test_point: str) -> dict[str, str] | None:
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
class SignalDependency:
    """Dependency relationship between two signals."""
    upstream: str
    downstream: str
    relationship: str

    @classmethod
    def from_dict(cls, data: dict) -> "SignalDependency":
        return cls(
            upstream=data["upstream"],
            downstream=data["downstream"],
            relationship=data["relationship"]
        )


@dataclass
class EquipmentConfig:
    """
    Complete equipment configuration.

    All equipment-specific knowledge is loaded from this configuration.
    NO hard-coded logic should exist in the agent code.
    """
    metadata: EquipmentMetadata
    signals: dict[str, SignalConfig] = field(default_factory=dict)
    thresholds: dict[str, ThresholdConfig] = field(default_factory=dict)
    faults: dict[str, FaultConfig] = field(default_factory=dict)
    images: dict[str, ImageConfig] = field(default_factory=dict)
    signal_dependencies: list[SignalDependency] = field(default_factory=list)

    @classmethod
    def from_file(cls, file_path: str) -> "EquipmentConfig":
        """Load equipment config from YAML file."""
        with open(file_path) as f:
            data = yaml.safe_load(f)

        metadata = EquipmentMetadata.from_dict(data["metadata"])

        signals = {}
        for s in data.get("signals", []):
            signal = SignalConfig.from_dict(s)
            signals[signal.signal_id] = signal

        thresholds = {}
        thresholds_data = data.get("thresholds", {})
        # Handle both dict format (preferred) and legacy list format
        if isinstance(thresholds_data, dict):
            for signal_id, threshold_dict in thresholds_data.items():
                # Ensure signal_id is in the data for from_dict
                threshold_dict_copy = dict(threshold_dict)
                threshold_dict_copy["signal_id"] = signal_id
                threshold = ThresholdConfig.from_dict(threshold_dict_copy)
                thresholds[threshold.signal_id] = threshold
        elif isinstance(thresholds_data, list):
            # Legacy list format
            for t in thresholds_data:
                threshold = ThresholdConfig.from_dict(t)
                thresholds[threshold.signal_id] = threshold

        faults = {}
        for f in data.get("faults", []):
            fault = FaultConfig.from_dict(f)
            faults[fault.fault_id] = fault

        images = {}
        images_data = data.get("images", {})
        # Handle both dict format (preferred) and legacy list format
        if isinstance(images_data, dict):
            for image_id, image_dict in images_data.items():
                image_dict_copy = dict(image_dict)
                image_dict_copy["image_id"] = image_id
                image = ImageConfig.from_dict(image_dict_copy)
                images[image.image_id] = image
        elif isinstance(images_data, list):
            # Legacy list format
            for i in images_data:
                image = ImageConfig.from_dict(i)
                images[image.image_id] = image

        signal_dependencies = []
        for d in data.get("signal_dependencies", []):
            signal_dependencies.append(SignalDependency.from_dict(d))

        return cls(
            metadata=metadata,
            signals=signals,
            thresholds=thresholds,
            faults=faults,
            images=images,
            signal_dependencies=signal_dependencies
        )

    def get_signal(self, signal_id: str) -> SignalConfig | None:
        """Get signal configuration by ID."""
        return self.signals.get(signal_id)

    def get_threshold(self, signal_id: str) -> ThresholdConfig | None:
        """Get threshold configuration by signal ID."""
        return self.thresholds.get(signal_id)

    def interpret_signal(self, signal_id: str, value: float) -> str | None:
        """Interpret a signal value to get semantic state."""
        threshold = self.get_threshold(signal_id)
        if threshold:
            return threshold.get_state(value)
        return None

    def find_fault(self, signal_states: dict[str, str]) -> FaultConfig | None:
        """
        Find matching fault based on observed signal states.

        Returns the first fault whose signatures match the observed states.
        """
        for fault in self.faults.values():
            if self._matches_fault(fault, signal_states):
                return fault
        return None

    def _matches_fault(self, fault: FaultConfig, signal_states: dict[str, str]) -> bool:
        """Check if fault signatures match observed signal states."""
        for sig in fault.signatures:
            sig_signal_id = sig.get("signal_id")
            sig_state = sig.get("state")
            observed_state = signal_states.get(sig_signal_id)
            if observed_state != sig_state:
                return False
        return True

    def get_image(self, image_id: str) -> ImageConfig | None:
        """Get image configuration by ID."""
        return self.images.get(image_id)

    def get_image_for_test_point(self, test_point: str) -> ImageConfig | None:
        """Get an image that shows a specific test point."""
        for image in self.images.values():
            if test_point in image.test_points:
                return image
        return None

    def get_image_url(self, image_id: str) -> str:
        """Get full URL for an image by ID using configured IMAGE_BASE_URL.
        
        Args:
            image_id: The image ID
            
        Returns:
            Full URL with IMAGE_BASE_URL prepended to the image filename
        """
        image = self.images.get(image_id)
        if not image:
            return ""
        return get_full_image_url(image.filename)

    def get_test_point_guidance(self, tp_id: str) -> dict[str, Any]:
        """
        Get consolidated guidance for a test point, including a base64 image.
        """
        # Find signal
        signal = self.get_signal(tp_id)
        if not signal:
            # Try finding by test_point name if signal_id doesn't match
            for s in self.signals.values():
                if s.test_point == tp_id:
                    signal = s
                    break

        if not signal:
            return {"error": f"Test point {tp_id} not found"}

        # Construct full image URL using configured IMAGE_BASE_URL
        full_image_url = get_full_image_url(signal.image_url) if signal.image_url else ""

        guidance = {
            "name": signal.name,
            "test_point": signal.test_point,
            "physical_description": signal.physical_description,
            "pro_tips": signal.pro_tips,
            "image_url": full_image_url
        }

        return guidance


class EquipmentConfigLoader:
    """
    Loader for equipment configurations.

    Manages loading and caching of equipment configs.
    """

    def __init__(self, config_dir: str = "data/equipment"):
        self.config_dir = Path(config_dir)
        self._cache: dict[str, EquipmentConfig] = {}
        self._cache_lock = threading.Lock()

    def load(self, equipment_id: str) -> EquipmentConfig:
        """
        Load equipment configuration.

        Args:
            equipment_id: The equipment ID (e.g., "cctv-psu-24w-v1")

        Returns:
            EquipmentConfig object

        Raises:
            InvalidEquipmentIdError: If equipment_id fails validation.
            FileNotFoundError: If the validated config file does not exist
                or resolves outside ``config_dir``.
        """
        equipment_id = _validate_equipment_id(equipment_id)

        # Check cache first (lock-free fast path)
        cached = self._cache.get(equipment_id)
        if cached is not None:
            return cached

        # Build and verify the resolved path stays inside config_dir
        # (defense in depth — slug validation already prevents traversal).
        config_root = self.config_dir.resolve()
        file_path = (self.config_dir / f"{equipment_id}.yaml").resolve()
        try:
            file_path.relative_to(config_root)
        except ValueError as exc:
            raise FileNotFoundError(
                f"Equipment config path escapes config_dir: {file_path}"
            ) from exc

        if not file_path.exists():
            raise FileNotFoundError(f"Equipment config not found: {file_path}")

        config = EquipmentConfig.from_file(str(file_path))

        with self._cache_lock:
            # Another thread may have populated between our check and the lock.
            self._cache.setdefault(equipment_id, config)
            return self._cache[equipment_id]

    def list_available(self) -> list[str]:
        """Return sorted list of equipment IDs with YAML config files on disk."""
        if not self.config_dir.exists():
            return []
        return sorted(p.stem for p in self.config_dir.glob("*.yaml"))

    def load_all(self) -> dict[str, EquipmentConfig]:
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
_loader: EquipmentConfigLoader | None = None
_loader_lock = threading.Lock()


def get_equipment_loader() -> EquipmentConfigLoader:
    """Get the singleton EquipmentConfigLoader instance (thread-safe)."""
    global _loader
    if _loader is None:
        with _loader_lock:
            if _loader is None:
                _loader = EquipmentConfigLoader()
    return _loader


def get_equipment_config(equipment_id: str) -> EquipmentConfig:
    """Get equipment configuration by validated ID.

    Raises InvalidEquipmentIdError if ``equipment_id`` is malformed.
    """
    return get_equipment_loader().load(equipment_id)
