"""Unit tests for :mod:`src.infrastructure.equipment_config`.

Focus: validator correctness and path-traversal defense. We do NOT test the
YAML parsing pipeline here — that is covered by the integration-style fixtures
when the graph runs end-to-end.
"""

import pytest
import yaml

from src.infrastructure.equipment_config import (
    EquipmentConfigLoader,
    InvalidEquipmentIdError,
    _validate_equipment_id,
)


class TestValidateEquipmentId:
    @pytest.mark.parametrize("valid_id", [
        "psu-v1",
        "cctv-psu-24w-v1",
        "model-a1-b2-c3",
        "x-y",
    ])
    def test_accepts_valid_slugs(self, valid_id):
        assert _validate_equipment_id(valid_id) == valid_id

    @pytest.mark.parametrize("bad_id", [
        "",                      # empty
        "no_underscore",         # no hyphen at all → rejected by pattern
        "PSU-V1",                # uppercase
        "../etc/passwd",         # traversal
        "/absolute/path",        # absolute
        "a/b",                   # separator
        "a\x00b",                # null byte
        "a" * 65,                # too long
        "1-starts-digit",        # must start with letter
    ])
    def test_rejects_bad_ids(self, bad_id):
        with pytest.raises(InvalidEquipmentIdError):
            _validate_equipment_id(bad_id)

    def test_rejects_non_string(self):
        with pytest.raises(InvalidEquipmentIdError):
            _validate_equipment_id(None)
        with pytest.raises(InvalidEquipmentIdError):
            _validate_equipment_id(42)


class TestEquipmentConfigLoader:
    @pytest.fixture
    def loader_with_tmp_config(self, tmp_path):
        cfg_dir = tmp_path / "equipment"
        cfg_dir.mkdir()
        (cfg_dir / "psu-v1.yaml").write_text(yaml.safe_dump({
            "metadata": {
                "equipment_id": "psu-v1",
                "name": "Test PSU",
                "category": "power",
                "manufacturer": "Acme",
                "version": "1.0",
                "created": "2025-01-01",
            },
            "signals": [],
            "thresholds": {},
            "faults": [],
        }), encoding="utf-8")
        return EquipmentConfigLoader(config_dir=str(cfg_dir))

    def test_load_valid_id_returns_config(self, loader_with_tmp_config):
        cfg = loader_with_tmp_config.load("psu-v1")
        assert cfg.metadata.equipment_id == "psu-v1"

    def test_load_caches_result(self, loader_with_tmp_config):
        first = loader_with_tmp_config.load("psu-v1")
        second = loader_with_tmp_config.load("psu-v1")
        assert first is second  # same object → cache hit

    def test_load_rejects_traversal_before_io(self, loader_with_tmp_config):
        with pytest.raises(InvalidEquipmentIdError):
            loader_with_tmp_config.load("../psu-v1")

    def test_load_missing_file_raises(self, loader_with_tmp_config):
        with pytest.raises(FileNotFoundError):
            loader_with_tmp_config.load("does-not-exist")

    def test_list_available_returns_sorted_ids(self, tmp_path):
        cfg_dir = tmp_path / "eq"
        cfg_dir.mkdir()
        for name in ("psu-v2", "psu-v1", "cctv-v1"):
            (cfg_dir / f"{name}.yaml").write_text("metadata: {}", encoding="utf-8")
        loader = EquipmentConfigLoader(config_dir=str(cfg_dir))
        assert loader.list_available() == ["cctv-v1", "psu-v1", "psu-v2"]

    def test_list_available_returns_empty_when_dir_missing(self, tmp_path):
        loader = EquipmentConfigLoader(config_dir=str(tmp_path / "nope"))
        assert loader.list_available() == []
