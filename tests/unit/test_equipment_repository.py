"""Tests for :mod:`src.infrastructure.db.equipment_repository` and the Postgres
backend of :class:`EquipmentConfigLoader`.

Uses an in-memory SQLite engine — the JSONB column falls back to JSON on
non-Postgres dialects (see :mod:`src.infrastructure.db.models`).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db import engine as engine_mod
from src.infrastructure.db.engine import Base
from src.infrastructure.db.equipment_repository import (
    list_equipment_ids,
    load_equipment_raw,
)
from src.infrastructure.db.models import Equipment
from src.infrastructure.equipment_config import EquipmentConfigLoader


@pytest.fixture
def sqlite_engine(monkeypatch):
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, expire_on_commit=False)
    monkeypatch.setattr(engine_mod, "_engine", eng, raising=False)
    monkeypatch.setattr(engine_mod, "_SessionFactory", factory, raising=False)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()
    monkeypatch.setattr(engine_mod, "_engine", None, raising=False)
    monkeypatch.setattr(engine_mod, "_SessionFactory", None, raising=False)


@pytest.fixture
def sample_raw_config():
    return {
        "metadata": {
            "equipment_id": "test-psu-v1",
            "name": "Test PSU",
            "category": "psu",
            "version": "1",
            "created": "2026-04-21",
        },
        "signals": [
            {
                "signal_id": "primary_mosfet",
                "name": "Primary MOSFET",
                "test_point": "Q1",
                "parameter": "continuity",
                "unit": "ohm",
            },
        ],
        "thresholds": {},
        "faults": [],
        "images": {},
        "signal_dependencies": [],
    }


def _insert(session_factory, raw: dict) -> None:
    with session_factory() as s:
        s.add(
            Equipment(
                equipment_id=raw["metadata"]["equipment_id"],
                name=raw["metadata"]["name"],
                category=raw["metadata"].get("category"),
                version=raw["metadata"].get("version"),
                raw_config=raw,
                updated_at=datetime.now(timezone.utc),
            )
        )
        s.commit()


def test_load_equipment_raw_roundtrip(sqlite_engine, sample_raw_config):
    factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    _insert(factory, sample_raw_config)

    raw = load_equipment_raw("test-psu-v1")
    assert raw is not None
    assert raw["metadata"]["name"] == "Test PSU"
    assert raw["signals"][0]["signal_id"] == "primary_mosfet"


def test_load_equipment_raw_missing_returns_none(sqlite_engine):
    assert load_equipment_raw("does-not-exist") is None


def test_list_equipment_ids(sqlite_engine, sample_raw_config):
    factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    _insert(factory, sample_raw_config)
    ids = list_equipment_ids()
    assert ids == ["test-psu-v1"]


def test_loader_postgres_backend(sqlite_engine, sample_raw_config):
    """EquipmentConfigLoader with backend='postgres' returns same shape as YAML."""
    factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    _insert(factory, sample_raw_config)

    loader = EquipmentConfigLoader(backend="postgres")
    config = loader.load("test-psu-v1")
    assert config.metadata.equipment_id == "test-psu-v1"
    assert "primary_mosfet" in config.signals
    assert config.signals["primary_mosfet"].name == "Primary MOSFET"


def test_loader_postgres_backend_falls_back_to_yaml(sqlite_engine, tmp_path, monkeypatch):
    """When the row is absent from Postgres, loader falls back to YAML on disk."""
    yaml_dir = tmp_path / "equipment"
    yaml_dir.mkdir()
    (yaml_dir / "fallback-dev-v1.yaml").write_text(
        "metadata:\n"
        "  equipment_id: fallback-dev-v1\n"
        "  name: Fallback\n"
        "  category: test\n"
        "  version: '1'\n"
        "  created: '2026-04-21'\n"
        "signals: []\n"
        "thresholds: {}\n"
        "faults: []\n"
        "images: {}\n"
        "signal_dependencies: []\n",
        encoding="utf-8",
    )

    loader = EquipmentConfigLoader(config_dir=str(yaml_dir), backend="postgres")
    cfg = loader.load("fallback-dev-v1")
    assert cfg.metadata.name == "Fallback"
