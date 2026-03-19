"""
LangChain Tools for Conversational LangGraph Studio Agent

This module defines the tools that the conversational agent uses to:
- Query the diagnostic knowledge base (RAG)
- Retrieve equipment configuration
- Read from USB multimeter
- Accept manual measurements

All guidance MUST come from RAG to prevent hallucination.
"""

from typing import Optional, Any
import time
from langchain_core.tools import tool

# Lazy imports to avoid DLL loading issues on Windows
# Import RAG only when the tool is actually called
_rag_repo = None
_equipment_config = None

def _get_equipment_config():
    """Lazy initialization of equipment config to avoid unnecessary imports."""
    global _equipment_config
    if _equipment_config is None:
        from src.infrastructure.equipment_config import get_equipment_config
        _equipment_config = get_equipment_config
    return _equipment_config

def _get_rag_repository():
    """Lazy initialization of RAG repository to avoid DLL loading issues."""
    global _rag_repo
    if _rag_repo is None:
        from src.infrastructure.rag_repository import RAGRepository
        _rag_repo = RAGRepository.from_directory("data/chromadb")
    return _rag_repo


@tool
def query_diagnostic_knowledge(
    query: str,
    equipment_model: str,
    category: Optional[str] = None,
    top_k: int = 5
) -> dict:
    """
    Query the diagnostic knowledge base for troubleshooting guidance.
    
    ALL guidance must come from RAG to prevent hallucination. Use this tool
    whenever you need to provide diagnostic guidance to the engineer.
    
    Args:
        query: Natural language query describing the symptom or measurement need
        equipment_model: Equipment model identifier (e.g., "cctv-psu-24w-v1")
        category: Optional filter - "measurement", "fault", "component", "safety"
        top_k: Maximum number of results to return
        
    Returns:
        Dict containing relevant document snippets with relevance scores.
        Each snippet includes: title, section, content, relevance_score.
        
    Example:
        query="how to measure output voltage on TP2"
        returns: [{"title": "MEAS-006", "content": "Output Voltage Measurement...", ...}]
    """
    # Initialize RAG repository (lazy loading)
    rag = _get_rag_repository()
    
    try:
        rag.initialize()
    except RuntimeError as e:
        return {
            "error": "RAG knowledge base unavailable",
            "message": str(e),
            "results": [],
            "result_count": 0
        }
    
    # Build query with equipment context
    full_query = f"{query} {equipment_model}"
    if category:
        full_query = f"{category}: {full_query}"
    
    results = rag.retrieve(
        query=full_query,
        equipment_model=equipment_model,
        top_k=top_k
    )
    
    # Process results to include Markdown images if available
    processed_results = []
    for r in results:
        data = r.to_dict()
        image_url = data.get("metadata", {}).get("image_url")
        if image_url:
            # Append markdown image to content for inline rendering in Studio
            data["content"] = f"{data['content']}\n\n![Guidance]({image_url})"
        processed_results.append(data)
    
    return {
        "query": query,
        "equipment_model": equipment_model,
        "category": category,
        "results": processed_results,
        "result_count": len(processed_results),
        "rag_available": True
    }


@tool
def get_equipment_configuration(
    equipment_model: str,
    request_type: str
) -> dict:
    """
    Retrieve equipment-specific configuration data.
    
    Args:
        equipment_model: Equipment model identifier (e.g., "cctv-psu-24w-v1")
        request_type: Type of configuration to retrieve:
            - "test_points": All test points with locations
            - "thresholds": Signal thresholds and semantic states  
            - "faults": All fault definitions with signatures
            - "all": Complete equipment configuration
            
    Returns:
        Equipment configuration data from YAML files
        
    Example:
        get_equipment_configuration("cctv-psu-24w-v1", "test_points")
        returns: {"test_points": [{"signal_id": "TP2", "name": "Output Voltage", ...}]}
    """
    try:
        config = _get_equipment_config()(equipment_model)
    except FileNotFoundError:
        return {
            "error": f"Equipment configuration not found for {equipment_model}",
            "available_models": _get_available_models()
        }
    
    if request_type == "test_points":
        test_points = []
        for signal in config.signals.values():
            # Find any image annotations for this test point
            annotations = []
            for img in config.images.values():
                for ann in (img.annotations or []):
                    if ann.get("target") == signal.test_point:
                        annotations.append({
                            "position": ann.get("position", ""),
                            "label": ann.get("label", ""),
                            "image_id": img.image_id,
                            "filename": img.filename
                        })
            test_points.append({
                "signal_id": signal.signal_id,
                "name": signal.name,
                "test_point": signal.test_point,
                "parameter": signal.parameter,
                "unit": signal.unit,
                "measurability": signal.measurability,
                "physical_description": signal.physical_description,
                "image_url": signal.image_url,
                "pro_tips": signal.pro_tips,
                "visual_guide": annotations if annotations else None
            })
        return {"test_points": test_points, "equipment_model": equipment_model}
    
    elif request_type == "thresholds":
        thresholds = {}
        for signal_id, threshold in config.thresholds.items():
            states = {}
            for state_name, state in threshold.states.items():
                states[state_name] = {
                    "min": state.min_value,
                    "max": state.max_value,
                    "description": state.description
                }
            thresholds[signal_id] = {
                "signal_id": threshold.signal_id,
                "states": states
            }
        return {"thresholds": thresholds, "equipment_model": equipment_model}
    
    elif request_type == "faults":
        faults_list = []
        for fault_id, fault in config.faults.items():
            faults_list.append({
                "fault_id": fault.fault_id,
                "name": fault.name,
                "description": fault.description,
                "priority": fault.priority,
                "signatures": fault.signatures,
                "hypotheses": [
                    {
                        "rank": h.rank,
                        "component": h.component,
                        "failure_mode": h.failure_mode,
                        "cause": h.cause,
                        "confidence": h.confidence
                    }
                    for h in fault.hypotheses
                ],
                "recovery": [
                    {
                        "step": r.step,
                        "action": r.action,
                        "target": r.target,
                        "instruction": r.instruction,
                        "verification": r.verification,
                        "safety": r.safety,
                        "difficulty": r.difficulty,
                        "estimated_time": r.estimated_time
                    }
                    for r in fault.recovery
                ]
            })
        # Sort by priority (lower number = higher priority)
        faults_list.sort(key=lambda x: x.get("priority", 999))
        return {"faults": faults_list, "equipment_model": equipment_model}
    
    elif request_type == "images":
        """Return reference images with test point locations."""
        images = []
        for img in config.images.values():
            # Build HTTP URL from filename
            # Images are stored in data/equipment/<equipment_id>-test-points/
            image_url = f"http://localhost:8000/{equipment_model}-test-points/{img.filename}"
            images.append({
                "image_id": img.image_id,
                "filename": img.filename,
                "description": img.description,
                "test_points": img.test_points,
                "image_url": image_url,
                "annotations": [
                    {
                        "target": a.get("target", ""),
                        "position": a.get("position", ""),
                        "label": a.get("label", "")
                    }
                    for a in (img.annotations or [])
                ]
            })
        return {"images": images, "equipment_model": equipment_model}
    
    elif request_type == "all":
        # Return complete config
        images = []
        for img in config.images.values():
            # Build HTTP URL from filename
            image_url = f"http://localhost:8000/{equipment_model}-test-points/{img.filename}"
            images.append({
                "image_id": img.image_id,
                "filename": img.filename,
                "description": img.description,
                "test_points": img.test_points,
                "image_url": image_url,
                "annotations": [
                    {
                        "target": a.get("target", ""),
                        "position": a.get("position", ""),
                        "label": a.get("label", "")
                    }
                    for a in (img.annotations or [])
                ]
            })

        return {
            "equipment_model": equipment_model,
            "metadata": {
                "equipment_id": config.metadata.equipment_id,
                "name": config.metadata.name,
                "category": config.metadata.category,
                "manufacturer": config.metadata.manufacturer,
                "version": config.metadata.version
            },
            "test_points": [
                {
                    "signal_id": s.signal_id,
                    "name": s.name,
                    "test_point": s.test_point,
                    "parameter": s.parameter,
                    "unit": s.unit
                }
                for s in config.signals.values()
            ],
            "images": images
        }
    
    else:
        return {"error": f"Unknown request_type: {request_type}. Valid types: test_points, thresholds, faults, images, all"}


@tool
def get_test_point_guidance(
    equipment_model: str,
    test_point_id: str
) -> dict:
    """
    Get detailed guidance for measuring a specific test point.
    
    This tool retrieves:
    1. Test point location and physical description
    2. Expected values and thresholds from RAG
    3. Image of the test point location (inline for LangGraph Studio)
    
    Args:
        equipment_model: Equipment model identifier (e.g., "cctv-psu-24w-v1")
        test_point_id: Test point identifier (e.g., "TP2", "TP3")
        
    Returns:
        Test point details including location, nominal values, safety warnings,
        and an inline image for visual guidance.
    """
    try:
        config = _get_equipment_config()(equipment_model)
        guidance = config.get_test_point_guidance(test_point_id)
        if "error" in guidance:
            return guidance
        
        # Add extra context for the agent
        guidance["equipment_model"] = equipment_model
        
        # Use image_url from signal (already populated in guidance)
        # The image_url is already in HTTP URL format from YAML
        # Ensure it's returned as empty string if not set
        if "image_url" not in guidance or not guidance["image_url"]:
            guidance["image_url"] = ""
        
        # Remove base64 fields - we now return URL only
        guidance.pop("image_base64", None)
        guidance.pop("mime_type", None)
        
        # Add location description for clarity
        guidance["location_description"] = f"Test point {test_point_id} location - {guidance.get('name', '')}"
        
        return guidance
    except Exception as e:
        return {"error": str(e)}


@tool
def read_multimeter(
    test_point_id: str,
    measurement_type: str = "voltage_dc",
    timeout: float = 15.0
) -> dict:
    """
    Read a measurement from the USB multimeter with automatic noise filtering and polling.
    
    This tool WAITS and POLLS for a stable reading:
    1. Noise filtering: Ignores values below 0.5V (air interference)
    2. Stabilization: Waits for stable readings (std dev <= 5V)
    3. Polling: Continuously polls for up to 15 seconds until stable reading is obtained
    4. Returns explicit status: "success", "timeout", or "error"
    
    Args:
        test_point_id: The test point identifier (e.g., "TP2")
        measurement_type: Type of measurement - "voltage_dc", "voltage_ac", 
                         "resistance", "current_dc", "continuity"
        timeout: Maximum time to wait for stable reading in seconds (default 15s)
        
    Returns:
        Dict with measurement value, unit, and metadata.
        Returns explicit "status" field: "success", "timeout", or "error"
        
    Example:
        read_multimeter(test_point_id="TP2", measurement_type="voltage_dc")
        returns: {"status": "success", "test_point": "TP2", "value": 224.5, "unit": "V", ...}
        
        If timeout:
        returns: {"status": "timeout", "test_point": "TP2", "message": "No stable reading after 15 seconds", ...}
    """
    from src.studio.background_usb_reader import ensure_reader_running, get_background_reader
    
    # Ensure background reader is running
    if not ensure_reader_running():
        available_ports = USBMultimeterClient.list_available_ports()
        return {
            "status": "error",
            "error": "Could not connect to multimeter",
            "available_ports": available_ports,
            "instruction": "Please connect the multimeter via USB",
            "test_point": test_point_id
        }
    
    reader = get_background_reader()
    
    # Map measurement type string to enum
    measurement_type_map = {
        "voltage_dc": "DC_VOLTAGE",
        "voltage_ac": "AC_VOLTAGE",
        "current_dc": "DC_CURRENT",
        "current_ac": "AC_CURRENT",
        "resistance": "RESISTANCE",
        "continuity": "CONTINUITY",
    }
    mtype_enum = measurement_type_map.get(measurement_type.lower(), "DC_VOLTAGE")
    
    # Wait for stable reading with polling
    reading = reader.get_reading_with_stabilization(timeout=timeout, measurement_type=mtype_enum)
    
    if reading:
        reading.test_point_id = test_point_id
        result = reading.to_dict()
        result["measurement_type_requested"] = measurement_type
        result["note"] = "Stable reading - automatically collected from multimeter"
        result["is_stable"] = True
        result["status"] = "success"  # Explicit success status
        return result
    
    # Timeout - no stable reading after polling
    last_valid = reader._reading_stats.get_last_valid_readings(3) if hasattr(reader, '_reading_stats') else []
    
    if last_valid:
        avg = sum(last_valid) / len(last_valid)
        return {
            "status": "timeout_unstable",  # Timeout but had some readings
            "test_point": test_point_id,
            "value": round(avg, 2),
            "unit": "V",
            "measurement_type": mtype_enum,
            "raw_values": last_valid,
            "measurement_type_requested": measurement_type,
            "note": f"Unstable readings around {avg:.1f}V - make sure probes have good contact",
            "is_stable": False,
            "message": "Readings were unstable. Please ensure probes have good contact and try again."
        }
    
    # Complete timeout - no readings at all
    return {
        "status": "timeout",  # Explicit timeout status
        "error": "No reading received",
        "test_point": test_point_id,
        "timeout_seconds": timeout,
        "instruction": "Position your multimeter probes on the test point - I will automatically read the stable value",
        "message": f"I couldn't detect a reading after {timeout} seconds. Are the probes connected?"
    }


@tool
def wait_for_multimeter_reading(
    test_point_id: str,
    timeout: int = 15
) -> dict:
    """
    Poll the multimeter for a stable reading at a specific test point.
    
    This tool actively WAITS for a stable reading by polling the background reader
    every second for up to the specified timeout.
    
    Args:
        test_point_id: The test point identifier (e.g., "TP2")
        timeout: Maximum time to poll in seconds (default 15)
        
    Returns:
        Dict with status ("success" or "timeout") and the reading data if successful.
    """
    from src.studio.background_usb_reader import get_background_reader, ensure_reader_running
    
    if not ensure_reader_running():
        return {
            "status": "error",
            "message": "Multimeter background reader failed to start.",
            "test_point": test_point_id
        }
        
    reader = get_background_reader()
    start_time = time.time()
    
    print(f"[TOOL] Polling for stable reading at {test_point_id} (timeout={timeout}s)...")
    
    while time.time() - start_time < timeout:
        # Check for latest stable reading
        # Note: background_usb_reader.py has get_stable_reading()
        reading = reader.get_stable_reading()
        
        if reading:
            # We found a stable reading!
            reading.test_point_id = test_point_id
            result = reading.to_dict()
            result["status"] = "success"
            result["polling_duration"] = round(time.time() - start_time, 1)
            print(f"[TOOL] Stable reading obtained: {result['value']} {result['unit']}")
            return result
            
        time.sleep(1.0) # Poll every 1 second
        
    # If we reached here, it's a timeout
    print(f"[TOOL] Polling timed out for {test_point_id}")
    return {
        "status": "timeout",
        "test_point": test_point_id,
        "timeout": timeout,
        "message": f"I couldn't detect a stable reading at {test_point_id} after {timeout} seconds."
    }


@tool
def enter_manual_reading(
    test_point_id: str,
    value: float,
    unit: str,
    measurement_type: str = "manual"
) -> dict:
    """
    Enter a measurement reading manually when USB multimeter is not available.
    
    Use this when the engineer cannot use the USB multimeter and needs to
    manually input readings from their own meter.
    
    Args:
        test_point_id: The test point identifier (e.g., "TP2")
        value: The measured value (numeric)
        unit: The unit of measurement (V, A, Ohm, etc.)
        measurement_type: Type of measurement - "voltage_dc", "voltage_ac", 
                         "resistance", "current_dc", "continuity", "manual"
        
    Returns:
        Dict confirming the entered reading with test_point_id
        
    Example:
        enter_manual_reading(test_point_id="TP2", value=12.5, unit="V", measurement_type="voltage_dc")
        returns: {"test_point": "TP2", "value": 12.5, "unit": "V", "status": "recorded"}
    """
    from datetime import datetime
    
    reading = MultimeterReading(
        raw_value=f"{value}{unit}",
        value=value,
        unit=unit,
        measurement_type=measurement_type.upper(),
        timestamp=datetime.utcnow().isoformat(),
        test_point_id=test_point_id
    )
    
    return {
        "test_point": test_point_id,
        "value": value,
        "unit": unit,
        "measurement_type": measurement_type,
        "timestamp": reading.timestamp,
        "status": "recorded",
        "raw": reading.raw_value
    }


def _get_available_models() -> list[str]:
    """Get list of available equipment models."""
    from pathlib import Path
    config_dir = Path("data/equipment")
    if not config_dir.exists():
        return []
    return [f.stem for f in config_dir.glob("*.yaml")]


# Tool list for easy import
TOOLS = [
    query_diagnostic_knowledge,
    get_equipment_configuration,
    get_test_point_guidance,
    read_multimeter,
    wait_for_multimeter_reading,
    enter_manual_reading,
]


def get_tools() -> list:
    """Return the list of tools for the agent."""
    return TOOLS
