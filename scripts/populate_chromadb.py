#!/usr/bin/env python3
"""
Populate ChromaDB with Troubleshooting Documentation

Usage:
    python scripts/populate_chromadb.py [--reset]
"""

import argparse
import json
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.chromadb_client import create_chromadb_client


# Sample troubleshooting documentation for CCTV power supply
TROUBLESHOOTING_DOCS = [
    {
        "id": "CCTV-PSU-001",
        "title": "24W CCTV Power Supply - No Output",
        "content": """
        SYMPTOM: Power supply unit shows no output voltage (0V at TP2).

        POSSIBLE CAUSES:
        1. Failed buck converter IC (U5)
        2. Open feedback resistor (R2)
        3. Failed input fuse (F1)
        4. Primary side failure

        DIAGNOSTIC STEPS:
        1. Measure AC input at TP1. Expected: 170-265V RMS.
           - If AC input is normal, proceed to step 2.
           - If AC input is low/open, check input fuse and bridge rectifier.

        2. Measure feedback reference at TP3. Expected: 2.5V DC.
           - If 2.5V is present, fault is likely in output stage.
           - If 0V, feedback circuit is not functioning.

        3. Check feedback resistor R2. Expected: 470Ω ±1%.
           - If open/high resistance, replace R2.
           - If shorted/low, check downstream components.

        COMPONENT LOCATIONS:
        - U5: Buck converter IC (main controller)
        - R2: Feedback resistor (470Ω, located near U5)
        - F1: Input fuse (250V 1A, near AC input)
        - BR1: Bridge rectifier (4 diodes, AC input side)
        """,
        "equipment_model": "CCTV-PSU-24W-V1",
        "category": "no_output"
    },
    {
        "id": "CCTV-PSU-002",
        "title": "24W CCTV Power Supply - Overvoltage Output",
        "content": """
        SYMPTOM: Output voltage measures above 13V (expected 12V ±5%).

        POSSIBLE CAUSES:
        1. Open feedback resistor (R2)
        2. Failed reference voltage (U5 internal)
        3. Capacitor C12 degradation

        DIAGNOSTIC STEPS:
        1. Measure feedback reference at TP3. Expected: 2.5V DC.
           - If >2.5V, reference circuit has failed.
           - If 2.5V normal, feedback path is broken.

        2. Check R2 resistance. Expected: 470Ω.
           - If >>470Ω (open), R2 has failed.
           - If <<470Ω (shorted), R2 has shorted.

        3. Verify output capacitor C12 ESR.
           - Expected ESR < 0.2Ω.
           - If ESR > 1Ω, replace C12.

        CORRECTIVE ACTION:
        - Replace R2 with 470Ω ±1% resistor.
        - If issue persists, replace U5 (buck converter).
        """,
        "equipment_model": "CCTV-PSU-24W-V1",
        "category": "overvoltage"
    },
    {
        "id": "CCTV-PSU-003",
        "title": "24W CCTV Power Supply - Excessive Ripple",
        "content": """
        SYMPTOM: Output ripple voltage >100mV p-p (expected <50mV).

        POSSIBLE CAUSES:
        1. Degraded output capacitor (C12)
        2. Input voltage instability
        3. Inductor L1 degradation

        DIAGNOSTIC STEPS:
        1. Measure output capacitor ESR at C12.
           - Expected: <0.2Ω for new capacitor.
           - Measured: >1Ω indicates degradation.

        2. Check input voltage stability at TP1.
           - Should be stable 170-265V RMS.
           - Fluctuations will show in output.

        3. Verify inductor L1 continuity.
           - Should measure near 0Ω DC resistance.
           - Open inductor causes severe ripple.

        CORRECTIVE ACTION:
        - Replace C12 with low-ESR electrolytic capacitor (1000μF 16V).
        - If ripple persists, check input voltage quality.
        """,
        "equipment_model": "CCTV-PSU-24W-V1",
        "category": "ripple_noise"
    },
    {
        "id": "CCTV-PSU-004",
        "title": "24W CCTV Power Supply - Thermal Shutdown",
        "content": """
        SYMPTOM: Unit operates initially but shuts down after 5-10 minutes.

        POSSIBLE CAUSES:
        1. Inadequate heatsinking on U5
        2. Overload condition (current >2A)
        3. Ambient temperature exceedance
        4. Degraded thermal compound

        DIAGNOSTIC STEPS:
        1. Measure output current at full load.
           - Expected: ≤2A for 24W supply at 12V.
           - If >2A, load is excessive.

        2. Monitor U5 case temperature during operation.
           - Thermal shutdown typically activates at 90-100°C.
           - U5 should stay below 70°C in normal operation.

        3. Check heatsink attachment.
           - Thermal compound should be present and not dried.
           - Heatsink should be firmly attached.

        CORRECTIVE ACTION:
        - Improve thermal management: add/replace heatsink.
        - Ensure adequate airflow around unit.
        - Reduce load if current >2A.
        """,
        "equipment_model": "CCTV-PSU-24W-V1",
        "category": "thermal"
    },
    {
        "id": "CCTV-PSU-005",
        "title": "24W CCTV Power Supply - Primary Side Failure",
        "content": """
        SYMPTOM: No output, AC input side shows abnormal readings.

        POSSIBLE CAUSES:
        1. Failed bridge rectifier (BR1)
        2. Blown input fuse (F1)
        3. Failed MOV (surge protection)
        4. AC input connector failure

        DIAGNOSTIC STEPS:
        1. Measure AC input voltage at connector.
           - Expected: 170-265V RMS line-to-line.
           - If 0V, check mains source.

        2. Check input fuse F1 continuity.
           - Expected: <0.1Ω (continuity).
           - If open, fuse has blown.

        3. Test bridge rectifier BR1.
           - Measure diode drop across each pair.
           - Expected: ~0.7V forward drop.
           - Short in both directions = failed BR1.

        4. Check MOV (surge protector).
           - Should show open circuit when healthy.
           - Shorted MOV will blow fuse.

        CORRECTIVE ACTION:
        - Replace failed fuse F1 (250V 1A slow-blow).
        - If fuse blows again, check BR1 and MOV first.
        - Replace BR1 if diodes have failed.
        """,
        "equipment_model": "CCTV-PSU-24W-V1",
        "category": "primary_side"
    }
]


def populate_chromadb(reset: bool = False) -> dict:
    """
    Populate ChromaDB with troubleshooting documentation.

    Args:
        reset: If True, reset collection before adding

    Returns:
        Stats dict with document count
    """
    print("Initializing ChromaDB...")

    client = create_chromadb_client(persist_directory="data/chromadb")

    if reset:
        print("Resetting collection...")
        client.reset()

    if client.is_initialized:
        print("Collection already exists, skipping population")
        return client.get_collection_stats()

    print("Populating with troubleshooting documentation...")

    # Prepare data for ChromaDB
    documents = [doc["content"] for doc in TROUBLESHOOTING_DOCS]
    metadatas = [
        {
            "title": doc["title"],
            "equipment_model": doc["equipment_model"],
            "category": doc["category"]
        }
        for doc in TROUBLESHOOTING_DOCS
    ]
    ids = [doc["id"] for doc in TROUBLESHOOTING_DOCS]

    # Add to collection
    client.add_documents(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    print(f"Added {len(documents)} documents to ChromaDB")

    return client.get_collection_stats()


def main():
    parser = argparse.ArgumentParser(
        description="Populate ChromaDB with troubleshooting documentation"
    )
    parser.add_argument(
        "--reset", "-r",
        action="store_true",
        help="Reset collection before populating"
    )

    args = parser.parse_args()

    stats = populate_chromadb(reset=args.reset)

    print(f"\nCollection Stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
