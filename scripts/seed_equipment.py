"""Seed / upsert the Postgres equipment catalogue from ``data/equipment/*.yaml``.

Usage
-----
    # Local dev (docker-compose Postgres already up):
    DATABASE_URL=postgresql://biomed:biomed@localhost:5432/biomed \
        python scripts/seed_equipment.py

    # Cloud Run Job (see README deployment section):
    gcloud run jobs execute biomed-seed --region us-central1 --wait

Idempotency
-----------
* Each equipment row is upserted by ``equipment_id`` — re-running is safe.
* Signals, faults, and signal_dependencies are rebuilt for each equipment
  (delete-then-insert) so removed entries in the YAML drop out of the DB.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from sqlalchemy import delete, select

# Make the script runnable without `pip install -e .`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.infrastructure.db.engine import get_engine, session_scope  # noqa: E402
from src.infrastructure.db.models import (  # noqa: E402
    Equipment,
    Fault,
    Signal,
    SignalDependency,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("seed_equipment")


def _upsert_one(equipment_path: Path) -> str:
    """Upsert a single YAML file into the catalogue. Returns the equipment_id."""
    with equipment_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    meta = raw.get("metadata") or {}
    equipment_id = meta.get("equipment_id") or equipment_path.stem
    name = meta.get("name", equipment_id)
    manufacturer = meta.get("manufacturer")
    category = meta.get("category")
    version = meta.get("version")
    description = meta.get("description")

    with session_scope() as session:
        # --- equipment row ---
        existing = session.execute(
            select(Equipment).where(Equipment.equipment_id == equipment_id)
        ).scalar_one_or_none()

        if existing is None:
            equipment = Equipment(
                equipment_id=equipment_id,
                name=name,
                manufacturer=manufacturer,
                category=category,
                version=version,
                description=description,
                raw_config=raw,
            )
            session.add(equipment)
        else:
            existing.name = name
            existing.manufacturer = manufacturer
            existing.category = category
            existing.version = version
            existing.description = description
            existing.raw_config = raw

        # --- flush then rebuild index tables for this equipment ---
        session.flush()
        session.execute(delete(Signal).where(Signal.equipment_id == equipment_id))
        session.execute(delete(Fault).where(Fault.equipment_id == equipment_id))
        session.execute(
            delete(SignalDependency).where(SignalDependency.equipment_id == equipment_id)
        )

        for s in raw.get("signals", []) or []:
            session.add(
                Signal(
                    equipment_id=equipment_id,
                    signal_id=s.get("signal_id"),
                    name=s.get("name", s.get("signal_id", "")),
                    parameter=s.get("parameter"),
                    unit=s.get("unit"),
                    test_point=s.get("test_point"),
                    diagnostic_meaning=s.get("diagnostic_meaning"),
                )
            )

        for fault in raw.get("faults", []) or []:
            session.add(
                Fault(
                    equipment_id=equipment_id,
                    fault_id=fault.get("fault_id"),
                    name=fault.get("name", fault.get("fault_id", "")),
                    priority=fault.get("priority"),
                    description=fault.get("description"),
                )
            )

        for dep in raw.get("signal_dependencies", []) or []:
            upstream = dep.get("upstream")
            downstream = dep.get("downstream")
            if not upstream or not downstream:
                continue
            session.add(
                SignalDependency(
                    equipment_id=equipment_id,
                    upstream_signal_id=upstream,
                    downstream_signal_id=downstream,
                    relationship_type=dep.get("relationship"),
                )
            )

    logger.info(
        "Upserted equipment %s (%d signals, %d faults)",
        equipment_id,
        len(raw.get("signals", []) or []),
        len(raw.get("faults", []) or []),
    )
    return equipment_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data" / "equipment",
        help="Directory containing <equipment_id>.yaml files.",
    )
    parser.add_argument(
        "--equipment-id",
        type=str,
        default=None,
        help="Upsert only this equipment_id instead of all files.",
    )
    args = parser.parse_args()

    if get_engine() is None:
        print("DATABASE_URL is not set — aborting.", file=sys.stderr)
        return 2

    data_dir: Path = args.data_dir
    if not data_dir.exists():
        print(f"Equipment directory does not exist: {data_dir}", file=sys.stderr)
        return 1

    if args.equipment_id:
        target = data_dir / f"{args.equipment_id}.yaml"
        if not target.exists():
            print(f"No YAML for equipment_id: {args.equipment_id}", file=sys.stderr)
            return 1
        _upsert_one(target)
        return 0

    paths = sorted(data_dir.glob("*.yaml"))
    if not paths:
        print(f"No equipment YAML found in {data_dir}", file=sys.stderr)
        return 1

    count = 0
    for path in paths:
        _upsert_one(path)
        count += 1
    logger.info("Seed complete — %d equipment upserted.", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
