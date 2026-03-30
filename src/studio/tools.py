"""
LangChain Tools for Conversational LangGraph Studio Agent

This module defines the tools that the conversational agent uses to:
- Query the diagnostic knowledge base (RAG)
- Retrieve equipment configuration
- Read from USB multimeter
- Accept manual measurements

All guidance MUST come from RAG to prevent hallucination.
"""

from typing import Optional, Any, Dict, List
import time
from langchain_core.tools import tool

# Lazy imports to avoid DLL loading issues on Windows
# Import RAG only when the tool is actually called
_rag_repo = None
_equipment_config = None
_diagnostic_engine = None

def _get_equipment_config():
    """Lazy initialization of equipment config to avoid unnecessary imports."""
    global _equipment_config
    if _equipment_config is None:
        from src.infrastructure.equipment_config import get_equipment_config
        _equipment_config = get_equipment_config
    return _equipment_config


def _build_test_points_dict(config):
    """Internal helper to build test points dictionary from config."""
    test_points = []
    for signal in config.signals.values():
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
    return test_points


def _build_thresholds_dict(config):
    """Internal helper to build thresholds dictionary from config."""
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
    return thresholds


def _build_faults_list(config):
    """Internal helper to build faults list from config."""
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
    faults_list.sort(key=lambda x: x.get("priority", 999))
    return faults_list


def _build_images_list(config, equipment_model):
    """Internal helper to build images list from config."""
    images = []
    for img in config.images.values():
        image_url = f"https://raw.githubusercontent.com/Michael-Gichamu/biomed-troubleshooter/main/data/equipment/{equipment_model}-test-points/{img.filename}"
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
    return images


def _get_rag_repository():
    """Lazy initialization of RAG repository to avoid DLL loading issues."""
    global _rag_repo
    if _rag_repo is None:
        from src.infrastructure.rag_repository import RAGRepository
        _rag_repo = RAGRepository.from_directory("data/chromadb")
    return _rag_repo

def _get_diagnostic_engine():
    """Lazy initialization of diagnostic engine."""
    global _diagnostic_engine
    if _diagnostic_engine is None:
        from src.domain.models import DiagnosticEngine
        _diagnostic_engine = DiagnosticEngine
    return _diagnostic_engine


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
        return {"test_points": _build_test_points_dict(config), "equipment_model": equipment_model}
    
    elif request_type == "thresholds":
        return {"thresholds": _build_thresholds_dict(config), "equipment_model": equipment_model}
    
    elif request_type == "faults":
        return {"faults": _build_faults_list(config), "equipment_model": equipment_model}
    
    elif request_type == "images":
        return {"images": _build_images_list(config, equipment_model), "equipment_model": equipment_model}
    
    elif request_type == "all":
        return {
            "equipment_model": equipment_model,
            "metadata": {
                "equipment_id": config.metadata.equipment_id,
                "name": config.metadata.name,
                "category": config.metadata.category,
                "manufacturer": config.metadata.manufacturer,
                "version": config.metadata.version,
                "created": getattr(config.metadata, "created", None)
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
            "thresholds": _build_thresholds_dict(config),
            "faults": _build_faults_list(config),
            "images": _build_images_list(config, equipment_model)
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
    test_point: str,
    measurement_type: str = "voltage_dc",
    max_duration: float = 15.0,
    equipment_model: str = "cctv-psu-24w-v1"
) -> dict:
    """
    Read stabilized measurement from multimeter at the specified test point.
    
    Uses the background reader's RobustStabilizer for noise filtering and stable reading extraction.
    
    Args:
        test_point: The test point identifier (e.g., "TP2", "output_rail")
        measurement_type: Type of measurement - "voltage_dc", "voltage_ac", 
                         "resistance", "current_dc", "continuity"
        max_duration: Maximum time to wait for stable reading in seconds (default 180s)
        equipment_model: Equipment model identifier (default: cctv-psu-24w-v1)
        
    Returns:
        Dict with measurement value, confidence, stability status, and guidance.
        - "status": "success" (stable reading obtained), "timeout" (no stable reading), or "error"
        - "value": The stabilized measurement value
        - "confidence": "HIGH", "MEDIUM", or "LOW"
        - "stability_status": "stable", "stabilizing", or "unstable"
        - "samples_used": Number of samples used for stabilization
        - "guidance": Contains test point info, image URL, and instructions
        
    Example:
        read_multimeter(test_point="TP2", measurement_type="voltage_dc")
        returns: {
            "status": "success", 
            "test_point": "TP2", 
            "value": 24.0, 
            "unit": "V",
            "confidence": "HIGH",
            "stability_status": "stable",
            "samples_used": 15,
            "guidance": {...}
        }
    """
    from src.studio.background_usb_reader import ensure_reader_running, get_background_reader

    # =========================================================================
    # PHASE 1: Get test point guidance (automatically, no user confirmation)
    # =========================================================================

    try:
        guidance_result = get_test_point_guidance.invoke({
            "equipment_model": equipment_model,
            "test_point_id": test_point
        })
    except Exception as e:
        guidance_result = {
            "error": f"Failed to get guidance: {str(e)}",
            "test_point": test_point
        }

    # =========================================================================
    # PHASE 2: Autonomous stabilization via background reader
    # =========================================================================

    # Ensure background reader is running
    if not ensure_reader_running():
        try:
            from src.infrastructure.usb_multimeter import USBMultimeterClient
            available_ports = USBMultimeterClient.list_available_ports()
        except Exception:
            available_ports = []

        return {
            "status": "error",
            "error": "Could not connect to multimeter",
            "available_ports": available_ports,
            "instruction": "Please connect the multimeter via USB",
            "test_point": test_point,
            "guidance": guidance_result,
            "message": "Multimeter not connected. Please connect and try again."
        }

    reader = get_background_reader()

    # Map measurement type string to the RobustStabilizer enum
    measurement_type_map = {
        "voltage_dc": "DC_VOLTAGE",
        "voltage_ac": "AC_VOLTAGE",
        "current_dc": "DC_CURRENT",
        "current_ac": "AC_CURRENT",
        "resistance": "RESISTANCE",
        "continuity": "CONTINUITY",
    }
    mtype_enum = measurement_type_map.get(measurement_type.lower(), "DC_VOLTAGE")

    # Single call — the RobustStabilizer in the background reader handles all
    # MAD-based stabilization, cluster detection, and dwell-time enforcement.
    # Returns early as soon as a stable cluster is detected (typically 10-15s),
    # or at max_duration timeout if readings never stabilize.
    reading = reader.get_reading_with_stabilization(
        timeout=max_duration,
        measurement_type=mtype_enum
    )

    if reading and reading.value is not None:
        # Check if we got a genuinely stable result from the stabilizer
        stable_result = reader.get_stable_result()

        if stable_result:
            return {
                "value": round(stable_result["value"], 2),
                "unit": reading.unit,
                "status": "success",
                "test_point": test_point,
                "measurement_type": reading.measurement_type,
                "measurement_type_requested": measurement_type,
                "confidence": "HIGH",
                "stability_status": "stable",
                "samples_used": stable_result.get("samples", 0),
                "guidance": guidance_result,
                "message": f"Stable reading obtained using {stable_result.get('samples', 0)} samples"
            }

        # Reading returned but stabilizer didn't formally declare stable
        # (timeout with partial data — return best-effort)
        return {
            "status": "timeout_unstable",
            "test_point": test_point,
            "measurement_type": reading.measurement_type,
            "measurement_type_requested": measurement_type,
            "guidance": guidance_result,
            "value": round(reading.value, 2),
            "unit": reading.unit,
            "confidence": "LOW",
            "stability_status": "unstable",
            "samples_used": reader.get_sample_count(),
            "note": "Readings were unstable - probes may need repositioning",
            "message": "The readings kept fluctuating. Please ensure probes have good contact "
                      "and hold them steady."
        }

    # Complete timeout - no readings obtained
    return {
        "status": "timeout",
        "test_point": test_point,
        "measurement_type": mtype_enum,
        "measurement_type_requested": measurement_type,
        "max_duration_seconds": max_duration,
        "guidance": guidance_result,
        "samples_collected": reader.get_sample_count(),
        "message": "No reading available",
        "error": "No reading available - please check probe connections"
    }


@tool
def get_diagnostic_step(
    current_state: Dict[str, Any],
    equipment_model: str = "cctv-psu-24w-v1"
) -> dict:
    """
    Get the current diagnostic step for the step-by-step diagnostic flow.
    
    Returns the current step information including test point, probe placement
    instructions, image URL, and expected value.
    
    Args:
        current_state: Current diagnostic state including:
            - current_step: Current step index
            - current_hypothesis: Current hypothesis being tested
            - equipment_config: Cached equipment configuration
        equipment_model: Equipment model identifier (default: cctv-psu-24w-v1)
        
    Returns:
        Dict with current diagnostic step containing:
        - test_point_name: Test point identifier
        - probe_placement_instructions: How to place probes
        - image_url: GitHub raw URL for reference image
        - expected_value: Expected measurement value/range
        - hypothesis_being_tested: Which hypothesis this step tests
        - step_number: Current step index
        
    Example:
        get_diagnostic_step(current_state={"current_step": 0, "current_hypothesis": "F1: Output Failure"})
        returns: {
            "test_point_name": "TP2",
            "probe_placement_instructions": "Place red probe on TP2, black on ground",
            "image_url": "https://raw.githubusercontent.com/.../main.png",
            "expected_value": "24V DC",
            "hypothesis_being_tested": "Output capacitor failure",
            "step_number": 0
        }
    """
    from src.domain.models import DiagnosticEngine, DiagnosticState
    
    try:
        # Reconstruct engine from state
        state = DiagnosticState.from_dict(current_state)
        
        # Load config if not in state
        if not state.equipment_config:
            config_loader = _get_equipment_config()(equipment_model)
            from src.domain.models import DiagnosticEngine
            engine = DiagnosticEngine(
                equipment_config_loader=config_loader,
                state=state
            )
            engine.load_equipment_config(equipment_model)
        else:
            from src.domain.models import DiagnosticEngine
            engine = DiagnosticEngine(state=state)
        
        # Get current step
        step = engine.get_current_step()
        
        if step is None:
            return {
                "status": "no_more_steps",
                "message": "No more diagnostic steps available",
                "test_point_name": None,
                "probe_placement_instructions": None,
                "image_url": None,
                "expected_value": None,
                "hypothesis_being_tested": None,
                "step_number": None
            }
        
        # Build response with image URL
        image_url = step.image_url
        if image_url and not image_url.startswith("http"):
            # Convert local path to GitHub raw URL
            image_url = f"https://raw.githubusercontent.com/Michael-Gichamu/biomed-troubleshooter/main/data/equipment/{equipment_model}-test-points/{image_url}"
        
        return {
            "status": "success",
            "test_point_name": step.test_point_name,
            "probe_placement_instructions": step.probe_placement_instructions,
            "image_url": image_url,
            "expected_value": step.expected_value,
            "hypothesis_being_tested": step.hypothesis_being_tested,
            "step_number": step.step_number,
            "signal_id": step.signal_id,
            "message": f"Step {step.step_number + 1}: Measure {step.test_point_name}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to get diagnostic step"
        }


@tool
def record_measurement(
    test_point: str,
    measurement_result: Dict[str, Any],
    current_state: Dict[str, Any],
    equipment_model: str = "cctv-psu-24w-v1"
) -> dict:
    """
    Record a measurement result to the diagnostic state.
    
    Records the measurement and advances the diagnostic workflow.
    
    Args:
        test_point: Test point identifier (e.g., "TP2")
        measurement_result: Measurement result dictionary containing:
            - value: Measured numeric value
            - unit: Unit of measurement (V, A, Ohm)
            - confidence: Confidence level (HIGH, MEDIUM, LOW)
            - stability_status: stable, stabilizing, or unstable
        current_state: Current diagnostic state dictionary
        equipment_model: Equipment model identifier (default: cctv-psu-24w-v1)
        
    Returns:
        Dict confirming recording with:
        - status: "recorded" or "error"
        - test_point: The test point recorded
        - measurement: The recorded measurement
        - next_step: Information about next diagnostic step
        
    Example:
        record_measurement(
            test_point="TP2",
            measurement_result={"value": 24.0, "unit": "V", "confidence": "HIGH"},
            current_state={"current_step": 0}
        )
        returns: {"status": "recorded", "test_point": "TP2", "measurement": {...}}
    """
    from src.domain.models import DiagnosticEngine, DiagnosticState
    
    try:
        # Reconstruct engine from state
        state = DiagnosticState.from_dict(current_state)
        
        # Load config if not in state
        if not state.equipment_config:
            config_loader = _get_equipment_config()(equipment_model)
            engine = DiagnosticEngine(
                equipment_config_loader=config_loader,
                state=state
            )
            engine.load_equipment_config(equipment_model)
        else:
            engine = DiagnosticEngine(state=state)
        
        # Record the measurement
        engine.record_measurement(test_point, measurement_result)
        
        return {
            "status": "recorded",
            "test_point": test_point,
            "measurement": measurement_result,
            "message": f"Measurement recorded for {test_point}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to record measurement: {str(e)}"
        }


@tool
def evaluate_measurement(
    measurement_result: Dict[str, Any],
    expected_value: str,
    current_state: Dict[str, Any],
    equipment_model: str = "cctv-psu-24w-v1"
) -> dict:
    """
    Evaluate if a measurement is normal or abnormal compared to expected value.
    
    Always explains: measured value, expected value, interpretation, and conclusion.
    
    Args:
        measurement_result: Measurement result dictionary containing:
            - value: Measured numeric value
            - unit: Unit of measurement
            - confidence: Confidence level
        expected_value: Expected value/range as string (e.g., "24V DC", "12-24V")
        current_state: Current diagnostic state dictionary
        equipment_model: Equipment model identifier (default: cctv-psu-24w-v1)
        
    Returns:
        Dict with evaluation containing:
        - measured_value: The actual measured value
        - expected_value: The expected value
        - interpretation: "normal" or "abnormal"
        - conclusion: Detailed explanation
        - is_within_threshold: Boolean
        
    Example:
        evaluate_measurement(
            measurement_result={"value": 24.0, "unit": "V"},
            expected_value="24V DC",
            current_state={}
        )
        returns: {
            "measured_value": 24.0,
            "expected_value": "24V DC",
            "interpretation": "normal",
            "conclusion": "Output voltage is within expected range",
            "is_within_threshold": True
        }
    """
    from src.domain.models import DiagnosticEngine, DiagnosticState
    
    try:
        # Get measured value
        measured_value = measurement_result.get("value")
        unit = measurement_result.get("unit", "")
        
        if measured_value is None:
            return {
                "measured_value": None,
                "expected_value": expected_value,
                "interpretation": "unknown",
                "conclusion": "No measurement value provided",
                "is_within_threshold": False,
                "message": "Cannot evaluate without a measurement value"
            }
        
        # Parse expected value to determine range
        # Simple parsing for common formats like "24V DC", "12-24V", "5V +/- 10%"
        expected_str = expected_value.lower().strip()
        
        # Try to extract numeric expected value
        import re
        numbers = re.findall(r'\d+\.?\d*', expected_str)
        
        is_normal = False
        interpretation = "abnormal"
        
        if numbers:
            expected_num = float(numbers[0])
            
            # Check for range format (e.g., "12-24V")
            if '-' in expected_str and len(numbers) >= 2:
                min_val = float(numbers[0])
                max_val = float(numbers[1])
                is_normal = min_val <= measured_value <= max_val
            else:
                # Single value - use +/- 10% tolerance
                tolerance = expected_num * 0.10
                is_normal = (expected_num - tolerance) <= measured_value <= (expected_num + tolerance)
        
        if is_normal:
            interpretation = "normal"
            conclusion = f"Measured {measured_value}{unit} is within expected range ({expected_value})"
        else:
            interpretation = "abnormal"
            conclusion = f"Measured {measured_value}{unit} is outside expected range ({expected_value})"
        
        return {
            "measured_value": measured_value,
            "unit": unit,
            "expected_value": expected_value,
            "interpretation": interpretation,
            "conclusion": conclusion,
            "is_within_threshold": is_normal,
            "message": conclusion
        }
        
    except Exception as e:
        return {
            "measured_value": measurement_result.get("value"),
            "expected_value": expected_value,
            "interpretation": "error",
            "conclusion": f"Evaluation failed: {str(e)}",
            "is_within_threshold": False,
            "error": str(e)
        }


@tool
def check_fault_confirmed(
    current_measurements: Dict[str, Any],
    hypothesis: str,
    current_state: Dict[str, Any],
    equipment_model: str = "cctv-psu-24w-v1"
) -> dict:
    """
    Check if the fault hypothesis is confirmed based on current measurements.
    
    If fault is confirmed, includes repair guidance.
    
    Args:
        current_measurements: Dictionary of measurements keyed by test point
        hypothesis: Current hypothesis being tested (e.g., "F1: Output Failure")
        current_state: Current diagnostic state dictionary
        equipment_model: Equipment model identifier (default: cctv-psu-24w-v1)
        
    Returns:
        Dict containing:
        - is_confirmed: Boolean indicating if fault is confirmed
        - fault_id: Fault identifier if confirmed
        - repair_guidance: List of repair steps if confirmed
        - conclusion: Explanation of the decision
        
    Example:
        check_fault_confirmed(
            current_measurements={"TP2": {"value": 0.0, "unit": "V"}},
            hypothesis="F1: Output Failure",
            current_state={}
        )
        returns: {
            "is_confirmed": True,
            "fault_id": "F1",
            "repair_guidance": [...],
            "conclusion": "Zero output confirmed - fault confirmed"
        }
    """
    from src.domain.models import DiagnosticEngine, DiagnosticState
    
    try:
        # Reconstruct engine from state
        state = DiagnosticState.from_dict(current_state)
        
        # Load config if not in state
        if not state.equipment_config:
            config_loader = _get_equipment_config()(equipment_model)
            engine = DiagnosticEngine(
                equipment_config_loader=config_loader,
                state=state
            )
            engine.load_equipment_config(equipment_model)
        else:
            engine = DiagnosticEngine(state=state)
        
        # Set current hypothesis
        engine._state.current_hypothesis = hypothesis
        
        # Evaluate step result
        # Use the first measurement for evaluation
        if current_measurements:
            first_test_point = list(current_measurements.keys())[0]
            measurement = current_measurements[first_test_point]
            evaluation = engine.evaluate_step_result(measurement)
        else:
            evaluation = {"status": "no_measurements"}
        
        # Check if fault is confirmed
        if evaluation.get("status") == "fault_confirmed":
            # Get repair guidance
            repair = engine.get_repair_guidance()
            
            return {
                "is_confirmed": True,
                "fault_id": evaluation.get("fault_id"),
                "fault_name": evaluation.get("fault_name"),
                "repair_guidance": repair.get("recovery_steps", []),
                "conclusion": evaluation.get("message", "Fault confirmed based on measurements"),
                "diagnosis_summary": repair.get("diagnosis_summary", {})
            }
        else:
            # Not confirmed - continue diagnostics
            return {
                "is_confirmed": False,
                "fault_id": None,
                "repair_guidance": None,
                "conclusion": "Fault not confirmed - continue with next diagnostic step",
                "next_action": "Proceed to next measurement step",
                "evaluation_status": evaluation.get("status")
            }
            
    except Exception as e:
        return {
            "is_confirmed": False,
            "error": str(e),
            "conclusion": f"Failed to check fault confirmation: {str(e)}"
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


# =============================================================================
# MODULE-LEVEL PRE-WARM
# =============================================================================
# sentence-transformers (all-MiniLM-L6-v2) triggers a full PyTorch cold-start
# the first time it is imported.  On Windows this can take 2-5 minutes and
# blocks the entire first graph invocation.
#
# We start the initialisation in a daemon thread at module import time so that
# by the time the first conversation reaches rag_node, the model is already
# loaded and the query completes in milliseconds.
#
# The background USB reader is also started here so the multimeter is ready
# before the first interrupt/step cycle.

import threading as _threading

def _prewarm_rag() -> None:
    """Load ChromaDB + sentence-transformers model in the background."""
    try:
        repo = _get_rag_repository()
        repo.initialize()
        print("[PREWARM] RAG repository + sentence-transformers ready.")
    except Exception as exc:
        # Non-fatal: rag_node will attempt lazy init and return a graceful error
        print(f"[PREWARM] RAG pre-warm failed (non-fatal): {exc}")


def _prewarm_usb_reader() -> None:
    """Start the background USB multimeter reader early."""
    try:
        from src.studio.background_usb_reader import ensure_reader_running
        result = ensure_reader_running()
        print(f"[PREWARM] Background USB reader started: {result}")
    except Exception as exc:
        print(f"[PREWARM] USB reader pre-warm failed (non-fatal): {exc}")


def _prewarm_llm() -> None:
    """Pre-initialise the LLMManager singleton (loads API keys, creates Groq client)."""
    try:
        from src.infrastructure.llm_manager import LLMManager
        LLMManager()  # Trigger singleton __init__
        print("[PREWARM] LLMManager ready.")
    except Exception as exc:
        print(f"[PREWARM] LLM pre-warm failed (non-fatal): {exc}")


def _prewarm_embeddings() -> None:
    """Load SentenceTransformer embedding model at server startup.

    chromadb_client._get_embedding_function() caches the model in a module-level
    global so this call is idempotent.  By loading it here (at tools.py import
    time) the model is in memory before the first diagnostic session starts,
    so rag_node's 5s thread timeout is sufficient for a full RAG query.
    """
    try:
        from src.infrastructure.chromadb_client import _get_embedding_function
        _get_embedding_function()  # forces SentenceTransformer('all-MiniLM-L6-v2') to load
        print("[PREWARM] Embedding model ready.")
    except Exception as exc:
        print(f"[PREWARM] Embedding pre-warm failed (non-fatal): {exc}")


# Fire all pre-warms concurrently; daemon=True so they don't block process exit
_threading.Thread(target=_prewarm_rag,        daemon=True, name="prewarm-rag").start()
_threading.Thread(target=_prewarm_usb_reader, daemon=True, name="prewarm-usb").start()
_threading.Thread(target=_prewarm_llm,        daemon=True, name="prewarm-llm").start()
_threading.Thread(target=_prewarm_embeddings, daemon=True, name="prewarm-embeddings").start()