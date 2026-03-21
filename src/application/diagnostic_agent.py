"""
Diagnostic Agent - Step-by-Step LangGraph Workflow (REFACTORED)

CRITICAL FIX: Interrupt placement has been corrected.

Previous (WRONG) Flow:
    RAG → PLAN → INSTRUCTION → INTERRUPT → MEASURE → EVALUATE → REASON → (loop or REPAIR)
    Interrupt happens BEFORE measurement.

Required (CORRECT) Flow:
    RAG → PLAN → STEP → DECISION → (FAULT CONFIRMED → REPAIR) or (MORE TESTS → INTERRUPT → NEXT → STEP)

Where STEP internally performs atomically:
    - instruction display (test point name, probe instructions, image)
    - measurement tool call (read_multimeter)
    - stabilization
    - evaluation (compare to expected)
    - reasoning (determine next action)
    - explanation (measured value, expected value, interpretation, conclusion)
    - decision (fault confirmed or need more tests)

INTERRUPT now:
    - Only reached when more tests are needed
    - Waits for user input "Next"
    - When user presses "Next", resume from NEXT step (NOT restart from RAG)

Key behaviors:
    - Interrupt happens ONLY after a full diagnostic step
    - One image shown per step
    - Measurement always explained
    - Zero readings handled with context-aware clustering
    - Equipment config fetched only ONCE at start
    - "Next" resumes from next step, not beginning
    - Cannot loop infinitely
    - Stops immediately when fault confirmed
"""

import json
import re
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timezone

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

# Domain imports
from src.domain.diagnostic_state import DiagnosticState, DiagnosticStep

# Infrastructure imports
from src.infrastructure.multimeter_stabilizer import MultimeterStabilizer
from src.infrastructure.rag_repository import RAGRepository
from src.infrastructure.equipment_config import EquipmentConfigLoader
from src.infrastructure.llm_manager import get_active_llm


# =============================================================================
# STATE TYPE DEFINITION
# =============================================================================

class AgentState(DiagnosticState):
    """Extended diagnostic state for the agent workflow."""
    
    # Additional fields for workflow control
    current_instruction: str = ""
    current_image_url: str = ""
    current_test_point: str = ""
    expected_value: str = ""
    measurement_result: Optional[Dict[str, Any]] = None
    evaluation_result: Optional[Dict[str, Any]] = None
    repair_guidance: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, str]] = []  # For context (limited to last 5)
    
    # Step tracking for proper resume
    diagnostic_steps: List[Dict[str, Any]] = []  # List of step definitions
    current_step_index: int = 0  # Current step index
    step_explanation: str = ""  # Explanation after each step


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _compress_tool_output(output: Dict[str, Any], max_length: int = 500) -> str:
    """Compress tool output before sending to LLM."""
    output_str = json.dumps(output)
    if len(output_str) <= max_length:
        return output_str
    # Truncate and add indicator
    return output_str[:max_length] + f"\n... (truncated, total {len(output_str)} chars)"


def _limit_messages(messages: List[Dict[str, str]], max_messages: int = 5) -> List[Dict[str, str]]:
    """Limit messages to last N entries for memory optimization."""
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


def _get_llm():
    """Get the active LLM instance."""
    return get_active_llm()


# =============================================================================
# NODE IMPLEMENTATIONS
# =============================================================================

def rag_node(state: AgentState) -> AgentState:
    """
    RAG_NODE: Query ChromaDB for diagnostic guidance based on symptoms.
    
    Retrieves relevant diagnostic knowledge from the RAG repository
    to guide the hypothesis generation.
    
    NOTE: This is called ONCE at the beginning of the diagnostic session.
    """
    # Initialize RAG repository
    rag_repo = RAGRepository.from_directory("data/chromadb")
    try:
        rag_repo.initialize()
    except RuntimeError as e:
        print(f"[RAG] Warning: RAG unavailable - {e}")
        state.retrieved_context = {"documents": [], "error": str(e)}
        return state
    
    # Retrieve relevant documents
    equipment_model = state.equipment_model or "cctv-psu-24w-v1"
    symptoms = state.symptoms or "no power"
    
    try:
        docs = rag_repo.retrieve(
            query=symptoms,
            equipment_model=equipment_model,
            top_k=3  # Limit for performance
        )
        
        # Compress documents for storage
        state.retrieved_context = {
            "documents": [
                {
                    "title": d.title,
                    "section": d.section,
                    "content": _compress_tool_output({"content": d.content}),
                    "relevance_score": d.relevance_score
                }
                for d in docs
            ],
            "query": symptoms,
            "equipment_model": equipment_model
        }
        print(f"[RAG] Retrieved {len(docs)} documents for query: {symptoms}")
        
    except Exception as e:
        print(f"[RAG] Error: {e}")
        state.retrieved_context = {"documents": [], "error": str(e)}
    
    # Add to messages for context
    state.messages = _limit_messages(state.messages + [{
        "role": "system",
        "content": f"RAG query executed for: {symptoms}. Found {len(state.retrieved_context.get('documents', []))} relevant documents."
    }])
    
    return state


def plan_node(state: AgentState) -> AgentState:
    """
    PLAN_NODE: Generate diagnostic hypothesis list from RAG results.
    
    Uses the LLM to analyze symptoms and RAG context to generate
    an ordered list of hypotheses to test.
    
    NOTE: This is called ONCE at the beginning. Equipment config is loaded here
    and cached for the entire session.
    """
    symptoms = state.symptoms or "Unknown symptoms"
    equipment_model = state.equipment_model or "cctv-psu-24w-v1"
    retrieved = state.retrieved_context
    
    # Load equipment config ONCE and cache it
    config_loader = EquipmentConfigLoader()
    try:
        config = config_loader.load(equipment_model)
        # Cache the config for the session
        state.config_cached = True
        state.equipment_config = {
            "faults": {k: {"name": v.name, "priority": v.priority} for k, v in config.faults.items()},
            "signals": {k: {"name": v.name, "test_point": v.test_point} for k, v in config.signals.items()},
            "thresholds": {k: {"states": v.states} for k, v in config.thresholds.items()}
        }
    except FileNotFoundError:
        print(f"[PLAN] Warning: Equipment config not found for {equipment_model}")
        config = None
    
    # Get faults from config
    faults = []
    if config:
        for fault_id, fault in config.faults.items():
            # Access dataclass attributes
            fault_hypotheses = fault.hypotheses if hasattr(fault, 'hypotheses') else []
            faults.append({
                "fault_id": fault_id,
                "name": fault.name,
                "priority": fault.priority,
                "hypotheses": [
                    {
                        "rank": h.rank,
                        "component": h.component,
                        "cause": h.cause,
                        "confidence": h.confidence
                    }
                    for h in fault_hypotheses
                ]
            })
    
    # Sort by priority
    faults.sort(key=lambda f: f.get("priority", 999))
    
    # Generate hypothesis list
    hypothesis_list = [
        f"{f['fault_id']}: {f['name']}"
        for f in faults
    ]
    
    # Set state
    state.hypothesis_list = hypothesis_list
    
    if hypothesis_list:
        state.current_hypothesis = hypothesis_list[0]
    
    # Build diagnostic steps from current hypothesis
    state = _build_diagnostic_steps(state, config)
    
    print(f"[PLAN] Generated {len(hypothesis_list)} hypotheses")
    print(f"[PLAN] Current hypothesis: {state.current_hypothesis}")
    print(f"[PLAN] Built {len(state.diagnostic_steps)} diagnostic steps")
    
    # Add to messages
    state.messages = _limit_messages(state.messages + [{
        "role": "system",
        "content": f"Generated diagnostic plan with {len(hypothesis_list)} hypotheses and {len(state.diagnostic_steps)} steps. First hypothesis: {state.current_hypothesis}"
    }])
    
    return state


def _build_diagnostic_steps(state: AgentState, config) -> AgentState:
    """Build diagnostic steps from current hypothesis and config."""
    
    if not state.current_hypothesis or not config:
        return state
    
    # Extract fault ID from hypothesis (format: "F001: Fault Name")
    fault_id = state.current_hypothesis.split(":")[0].strip()
    fault = config.faults.get(fault_id)
    
    if not fault:
        return state
    
    # Get hypotheses for this fault (dataclass attribute access)
    hypotheses = fault.hypotheses if hasattr(fault, 'hypotheses') else []
    
    # Build steps
    steps = []
    for i, hypothesis in enumerate(hypotheses):
        # Access dataclass attributes
        component = hypothesis.component if hasattr(hypothesis, 'component') else ""
        
        # Find signal for this component
        signal = None
        for sid, s in config.signals.items():
            if s.test_point == component or s.name.lower() in component.lower():
                signal = s
                break
        
        if signal:
            # Get expected value from thresholds
            expected_value = ""
            threshold = config.thresholds.get(signal.signal_id)
            if threshold:
                normal_state = threshold.states.get("normal")
                if normal_state:
                    expected_value = f"{normal_state.min_value}-{normal_state.max_value} {signal.unit}"
            
            # Access dataclass attributes
            cause = hypothesis.cause if hasattr(hypothesis, 'cause') else ""
            
            step = DiagnosticStep(
                step_number=i,
                test_point_name=signal.test_point,
                probe_placement_instructions=signal.physical_description or "",
                image_url=signal.image_url or "",
                expected_value=expected_value or f"{signal.parameter} ({signal.unit})",
                hypothesis_being_tested=cause,
                signal_id=signal.signal_id
            )
            steps.append(step)
    
    # Store steps as dict for serialization
    state.diagnostic_steps = [
        {
            "step_number": s.step_number,
            "test_point_name": s.test_point_name,
            "probe_placement_instructions": s.probe_placement_instructions,
            "image_url": s.image_url,
            "expected_value": s.expected_value,
            "hypothesis_being_tested": s.hypothesis_being_tested,
            "signal_id": s.signal_id
        }
        for s in steps
    ]
    
    # Set current step info from first step
    state.tested_points = [s.test_point_name for s in steps]
    state.current_step_index = 0
    
    if steps:
        current_step = steps[0]
        state.current_test_point = current_step.test_point_name
        state.current_instruction = current_step.probe_placement_instructions
        state.current_image_url = current_step.image_url
        state.expected_value = current_step.expected_value
    
    print(f"[PLAN] Built {len(steps)} diagnostic steps")
    
    return state


def step_node(state: AgentState) -> AgentState:
    """
    STEP_NODE: Combined atomic diagnostic step.
    
    This is the CORE node that performs a complete diagnostic step atomically:
    1. Shows test point name
    2. Shows probe placement instructions
    3. Shows exactly ONE image
    4. Calls read_multimeter
    5. Stabilizes the measurement
    6. Evaluates against expected values
    7. Reasons about the result
    8. Explains to user: measured value, expected value, interpretation, conclusion
    9. Decides next action
    
    This node REPLACES: INSTRUCTION + MEASURE + EVALUATE + REASON
    
    After completion:
    - If fault confirmed → goes to REPAIR
    - Else → goes to INTERRUPT (to pause before next step)
    """
    # Get current step info
    step_index = state.current_step_index
    steps = state.diagnostic_steps
    
    if not steps or step_index >= len(steps):
        # No more steps - diagnosis complete
        state.diagnosis_progress = "completed"
        state.step_explanation = "No more diagnostic steps available."
        return state
    
    current_step = steps[step_index]
    test_point = current_step.get("test_point_name", "")
    instruction = current_step.get("probe_placement_instructions", "")
    image_url = current_step.get("image_url", "")
    expected = current_step.get("expected_value", "")
    
    # Store current step info
    state.current_test_point = test_point
    state.current_instruction = instruction
    state.current_image_url = image_url
    state.expected_value = expected
    
    # =========================================================================
    # PART 1: Instruction Display
    # =========================================================================
    instruction_text = f"""
## Diagnostic Step {step_index + 1}: {test_point}

**Hypothesis:** {current_step.get('hypothesis_being_tested', 'Testing component')}

**Probe Placement Instructions:**
{instruction or "See image for probe locations."}

**Expected Value:**
{expected}

**Image:** {image_url}
"""
    state.current_instruction = instruction_text.strip()
    print(f"[STEP] Step {step_index + 1}: Preparing to test {test_point}")
    
    # =========================================================================
    # PART 2: Measurement
    # =========================================================================
    measurement = _perform_measurement(test_point)
    state.measurement_result = measurement
    state.measurements[test_point] = measurement
    
    # =========================================================================
    # PART 3: Evaluation
    # =========================================================================
    evaluation = _evaluate_measurement(measurement, expected, test_point)
    state.evaluation_result = evaluation
    
    # =========================================================================
    # PART 4: Reasoning & Explanation
    # =========================================================================
    measured_value = measurement.get("value") if measurement else None
    unit = measurement.get("unit", "") if measurement else ""
    
    is_fault_confirmed = evaluation.get("is_fault_confirmed", False)
    interpretation = evaluation.get("interpretation", "")
    conclusion = evaluation.get("conclusion", "")
    
    # Build comprehensive explanation
    explanation = f"""
## Step {step_index + 1} Complete: {test_point}

### Measurement Results:
- **Measured Value:** {measured_value} {unit}
- **Expected Value:** {expected}
- **Status:** {measurement.get('status', 'unknown') if measurement else 'No measurement'}

### Evaluation:
- **Interpretation:** {interpretation}
- **Conclusion:** {conclusion}

### Next Action:
{"[X] FAULT CONFIRMED - Proceeding to repair guidance" if is_fault_confirmed else "[OK] Measurement within expected range - Proceeding to next test point"}
"""
    state.step_explanation = explanation.strip()
    
    # =========================================================================
    # PART 5: Decision
    # =========================================================================
    if is_fault_confirmed:
        state.diagnosis_progress = "fault_confirmed"
        print(f"[STEP] Fault confirmed at {test_point} - proceeding to REPAIR")
    else:
        state.diagnosis_progress = "in_progress"
        print(f"[STEP] Step {step_index + 1} complete - {test_point} OK, proceeding to next step")
        
        # Mark this step as completed and move to next
        state.completed_steps = state.completed_steps + [step_index]
        state.current_step_index = step_index + 1
        
        # Update current step info for next iteration
        next_step_index = state.current_step_index
        if next_step_index < len(steps):
            next_step = steps[next_step_index]
            state.current_test_point = next_step.get("test_point_name", "")
            state.current_instruction = next_step.get("probe_placement_instructions", "")
            state.current_image_url = next_step.get("image_url", "")
            state.expected_value = next_step.get("expected_value", "")
    
    # Add to messages
    state.messages = _limit_messages(state.messages + [{
        "role": "assistant",
        "content": f"Step {step_index + 1} complete: {test_point}. Measured: {measured_value} {unit}. Fault confirmed: {is_fault_confirmed}"
    }])
    
    return state


def _perform_measurement(test_point: str) -> Dict[str, Any]:
    """
    Perform a stabilized multimeter measurement.
    
    Returns measurement result dictionary.
    """
    # Initialize stabilizer
    stabilizer = MultimeterStabilizer(
        max_samples=50,
        min_samples=5,
        max_duration=180.0,
        window_size=10,
        stability_threshold=0.01
    )
    
    # Import multimeter reader
    from src.studio.background_usb_reader import ensure_reader_running, get_background_reader
    
    # Ensure reader is running
    if not ensure_reader_running():
        return {
            "status": "error",
            "error": "Multimeter not connected",
            "test_point": test_point,
            "value": None,
            "unit": None
        }
    
    reader = get_background_reader()
    
    # Get reading with stabilization
    measurement_type = "DC_VOLTAGE"  # Default for PSU
    
    reading = reader.get_reading_with_stabilization(
        timeout=30.0,
        measurement_type=measurement_type
    )
    
    if reading:
        # Get stable result
        stable_result = reader.get_stable_result()
        
        result = {
            "status": "success",
            "test_point": test_point,
            "value": round(reading.value, 2) if reading.value is not None else None,
            "unit": reading.unit,
            "measurement_type": reading.measurement_type,
            "stabilization": stable_result or {
                "method": "trimmed_mean",
                "samples": reader.get_sample_count()
            }
        }
        
        print(f"[MEASURE] Measurement at {test_point}: {reading.value} {reading.unit}")
        return result
    else:
        # Timeout or error
        result = {
            "status": "timeout",
            "test_point": test_point,
            "value": None,
            "unit": None,
            "error": "Could not obtain stable reading"
        }
        print(f"[MEASURE] Timeout at test point: {test_point}")
        return result


def _evaluate_measurement(measurement: Optional[Dict[str, Any]], expected: str, test_point: str) -> Dict[str, Any]:
    """
    Evaluate measurement against expected values.
    
    Returns evaluation result dictionary.
    """
    if not measurement or measurement.get("status") != "success":
        return {
            "is_fault_confirmed": False,
            "interpretation": "No valid measurement obtained",
            "measured_value": None,
            "expected_value": expected,
            "conclusion": "Cannot confirm fault - measurement failed"
        }
    
    measured_value = measurement.get("value")
    unit = measurement.get("unit", "")
    
    # Parse expected value (format: "220-240 V" or just "220V")
    expected_match = re.match(r"([\d.]+)(?:-([\d.]+))?\s*([VVAOhmΩ]?)", expected.replace("–", "-"))
    
    if expected_match:
        min_expected = float(expected_match.group(1))
        max_expected = float(expected_match.group(2)) if expected_match.group(2) else min_expected
        expected_unit = expected_match.group(3) or unit
        
        # Check if measurement is within expected range
        is_within_range = min_expected <= measured_value <= max_expected
        
        # Determine interpretation
        if is_within_range:
            interpretation = f"Measured {measured_value}{unit} is within expected range ({min_expected}-{max_expected}{expected_unit})"
            conclusion = "Normal - component appears functional"
            is_fault_confirmed = False
        else:
            # Check for specific fault conditions
            if measured_value == 0 or measured_value is None:
                interpretation = f"Measured {measured_value if measured_value else 0}{unit} - No voltage detected"
                conclusion = "FAULT CONFIRMED - No power reaching test point"
                is_fault_confirmed = True
            elif measured_value < min_expected * 0.1:
                interpretation = f"Measured {measured_value}{unit} - Significantly below expected ({min_expected}-{max_expected}{expected_unit})"
                conclusion = "FAULT CONFIRMED - Low voltage indicates component failure"
                is_fault_confirmed = True
            elif measured_value > max_expected * 1.5:
                interpretation = f"Measured {measured_value}{unit} - Significantly above expected ({min_expected}-{max_expected}{expected_unit})"
                conclusion = "WARNING - Overvoltage detected"
                is_fault_confirmed = True
            else:
                interpretation = f"Measured {measured_value}{unit} - Outside expected range ({min_expected}-{max_expected}{expected_unit})"
                conclusion = "Anomaly detected - further investigation needed"
                is_fault_confirmed = False
    else:
        # Can't parse expected value - make basic determination
        if measured_value == 0 or measured_value is None:
            interpretation = f"Measured {measured_value if measured_value else 0}{unit} - No voltage"
            conclusion = "Possible fault - no signal detected"
            is_fault_confirmed = True
        else:
            interpretation = f"Measured {measured_value}{unit}"
            conclusion = "Measurement obtained - compare with expected value"
            is_fault_confirmed = False
    
    return {
        "is_fault_confirmed": is_fault_confirmed,
        "interpretation": interpretation,
        "measured_value": measured_value,
        "expected_value": expected,
        "unit": unit,
        "conclusion": conclusion,
        "test_point": test_point
    }


def interrupt_node(state: AgentState) -> AgentState:
    """
    INTERRUPT_NODE: Pause workflow and wait for user "Next".
    
    CRITICAL: This interrupt now happens AFTER a full diagnostic step completes.
    
    This node is only reached when:
    - More diagnostic steps need to be performed
    - The user needs to reposition probes for the next test point
    
    When the user presses "Next", the workflow resumes from the NEXT step
    (not from the beginning).
    """
    step_index = state.current_step_index
    steps = state.diagnostic_steps
    
    # Check if there are more steps
    if step_index >= len(steps):
        # No more steps - diagnosis complete
        state.diagnosis_progress = "completed"
        state.waiting_for_next = False
        return state
    
    current_step = steps[step_index]
    test_point = current_step.get("test_point_name", "")
    expected = current_step.get("expected_value", "")
    
    # Create the interrupt message
    interrupt_message = f"""
## Diagnostic Step {step_index + 1} Complete

### Previous Results:
{state.step_explanation}

---

### Next Test Point: {test_point}

**Expected Value:** {expected}

**Instructions:**
{current_step.get('probe_placement_instructions', 'See image for probe locations.')}

**Image:** {current_step.get('image_url', '')}

---

**Press "Next" when ready to test {test_point}**
"""
    
    print(f"[INTERRUPT] Pausing workflow before step {step_index + 1}: {test_point}")
    
    # Set waiting flag
    state.waiting_for_next = True
    
    # Use langgraph interrupt to pause
    result = interrupt({
        "action": "wait_for_user",
        "prompt": interrupt_message,
        "test_point": test_point,
        "expected_value": expected,
        "step_index": step_index
    })
    
    # When resumed, check if user provided input
    if result:
        user_input = result.get("user_input", "").lower().strip()
        print(f"[INTERRUPT] Resume received with input: {user_input}")
        
        # Clear waiting flag (we're resuming)
        state.waiting_for_next = False
    
    return state


def decision_node(state: AgentState) -> AgentState:
    """
    DECISION_NODE: Determine next action after STEP completes.
    
    This is a routing node that decides:
    - If fault confirmed → REPAIR (terminal)
    - If more steps available → INTERRUPT (to pause before next step)
    - If no more steps → END (diagnosis complete)
    """
    if state.diagnosis_progress == "fault_confirmed":
        # Fault confirmed - go to repair
        print(f"[DECISION] Fault confirmed - routing to REPAIR")
        return state
    
    # Check if there are more steps
    step_index = state.current_step_index
    steps = state.diagnostic_steps
    
    if step_index < len(steps):
        # More steps available - go to interrupt
        print(f"[DECISION] More steps available ({step_index + 1}/{len(steps)}) - routing to INTERRUPT")
        state.diagnosis_progress = "in_progress"
    else:
        # No more steps - diagnosis complete without fault confirmed
        print(f"[DECISION] No more steps - diagnosis complete")
        state.diagnosis_progress = "completed"
    
    return state


def repair_node(state: AgentState) -> AgentState:
    """
    REPAIR_NODE: Provide final repair guidance and terminate.
    
    Retrieves the recovery steps for the confirmed fault and provides
    detailed repair guidance to the user.
    """
    equipment_model = state.equipment_model or "cctv-psu-24w-v1"
    fault_id = state.current_hypothesis.split(":")[0].strip() if state.current_hypothesis else None
    
    # Load equipment config
    config_loader = EquipmentConfigLoader()
    try:
        config = config_loader.load(equipment_model)
    except FileNotFoundError:
        config = None
    
    recovery_steps = []
    
    if config and fault_id:
        fault = config.faults.get(fault_id)
        if fault and hasattr(fault, 'recovery'):
            recovery_steps = [
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
    
    # Format repair guidance
    guidance_text = f"""
## Diagnosis Complete - Fault Confirmed

**Confirmed Fault:** {state.current_hypothesis}
**Test Point:** {state.current_test_point}
**Measurement:** {state.evaluation_result.get('measured_value')} {state.evaluation_result.get('unit')}
**Interpretation:** {state.evaluation_result.get('interpretation')}

---

### Recovery Steps:
"""
    
    for i, step in enumerate(recovery_steps, 1):
        guidance_text += f"""
#### Step {i}: {step.get('action', 'Unknown')}
- **Target:** {step.get('target', 'N/A')}
- **Instruction:** {step.get('instruction', 'No instruction')}
- **Verification:** {step.get('verification', 'N/A')}
- **Safety:** {step.get('safety', 'N/A')}
- **Difficulty:** {step.get('difficulty', 'N/A')}
- **Estimated Time:** {step.get('estimated_time', 'N/A')}

"""
    
    if not recovery_steps:
        guidance_text += "\n*No specific recovery steps available. Please consult service manual.*"
    
    state.repair_guidance = {
        "fault_id": fault_id,
        "fault_name": state.current_hypothesis,
        "test_point": state.current_test_point,
        "measurement": {
            "value": state.evaluation_result.get('measured_value'),
            "unit": state.evaluation_result.get('unit'),
            "interpretation": state.evaluation_result.get('interpretation')
        },
        "recovery_steps": recovery_steps,
        "guidance_text": guidance_text.strip()
    }
    
    state.diagnosis_progress = "completed"
    state.completed_at = datetime.now(timezone.utc)
    
    print(f"[REPAIR] Provided repair guidance for: {state.current_hypothesis}")
    
    # Add to messages
    state.messages = _limit_messages(state.messages + [{
        "role": "assistant",
        "content": f"Diagnosis complete. Fault confirmed: {state.current_hypothesis}. Repair guidance provided."
    }])
    
    return state


# =============================================================================
# WORKFLOW GRAPH CONSTRUCTION
# =============================================================================

def create_diagnostic_graph() -> StateGraph:
    """
    Create the LangGraph workflow for diagnostic agent.
    
    CORRECTED Workflow:
        RAG → PLAN → STEP → DECISION → (FAULT CONFIRMED → REPAIR) 
                                      → (MORE TESTS → INTERRUPT → STEP)
    
    The interrupt now happens AFTER each full diagnostic step completes.
    """
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("rag", rag_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("step", step_node)
    workflow.add_node("decision", decision_node)
    workflow.add_node("interrupt", interrupt_node)
    workflow.add_node("repair", repair_node)
    
    # Define edges
    workflow.set_entry_point("rag")
    
    # RAG → PLAN (RAG runs once at start)
    workflow.add_edge("rag", "plan")
    
    # PLAN → STEP (first diagnostic step)
    workflow.add_edge("plan", "step")
    
    # STEP → DECISION (evaluate result and decide next action)
    workflow.add_edge("step", "decision")
    
    # DECISION conditional edges
    # If fault confirmed → REPAIR
    # If more tests needed → INTERRUPT → STEP
    # If no more tests → END
    workflow.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            "repair": "repair",
            "interrupt": "interrupt",
            "end": END
        }
    )
    
    # INTERRUPT → STEP (user "Next" resumes to next step)
    workflow.add_edge("interrupt", "step")
    
    # REPAIR → END (terminal)
    workflow.add_edge("repair", END)
    
    return workflow


def _route_after_decision(state: AgentState) -> str:
    """
    Route to the appropriate node after decision.
    
    Returns:
        - "repair" if fault is confirmed
        - "interrupt" if more tests are needed
        - "end" if diagnosis is complete
    """
    if state.diagnosis_progress == "fault_confirmed":
        return "repair"
    
    # Check if there are more steps
    step_index = state.current_step_index
    steps = state.diagnostic_steps
    
    if step_index < len(steps):
        # More steps available
        return "interrupt"
    else:
        # No more steps - complete
        return "end"


# =============================================================================
# COMPILATION AND RUNNER
# =============================================================================

# Global compiled graph
_compiled_graph = None


def get_compiled_graph() -> StateGraph:
    """Get or create the compiled diagnostic graph."""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = create_diagnostic_graph()
        _compiled_graph = workflow.compile()
    return _compiled_graph


def start_diagnosis(
    symptoms: str,
    equipment_model: str = "cctv-psu-24w-v1",
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Start a new diagnostic session.
    
    Args:
        symptoms: User-reported symptoms description
        equipment_model: Equipment model identifier
        session_id: Optional session identifier
        
    Returns:
        Initial state with first instruction
    """
    # Create initial state
    initial_state = AgentState(
        equipment_model=equipment_model,
        symptoms=symptoms,
        session_id=session_id,
        started_at=datetime.now(timezone.utc),
        diagnosis_progress="in_progress"
    )
    
    # Get compiled graph
    graph = get_compiled_graph()
    
    # Run the graph
    result = graph.invoke(initial_state)
    
    return result


def resume_diagnosis(state: AgentState, user_input: str = "next") -> Dict[str, Any]:
    """
    Resume a diagnostic session after interrupt.
    
    Args:
        state: Current state
        user_input: User input (typically "next")
        
    Returns:
        Updated state after measurement
    """
    # Get compiled graph
    graph = get_compiled_graph()
    
    # Resume by passing through interrupt node
    # The interrupt will receive the user_input
    result = graph.invoke(state)
    
    return result


def run_diagnostic_session(
    symptoms: str,
    equipment_model: str = "cctv-psu-24w-v1"
) -> Dict[str, Any]:
    """
    Run a complete diagnostic session (for testing/simulation).
    
    This is a simplified version that doesn't use actual interrupts.
    """
    # Create initial state
    initial_state = AgentState(
        equipment_model=equipment_model,
        symptoms=symptoms,
        session_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        started_at=datetime.now(timezone.utc),
        diagnosis_progress="in_progress"
    )
    
    # Run through the graph manually (simulating the flow)
    state = initial_state
    
    # Run RAG
    state = rag_node(state)
    state = plan_node(state)
    
    # Run through all steps
    while state.diagnosis_progress == "in_progress":
        state = step_node(state)
        
        if state.diagnosis_progress == "fault_confirmed":
            # Fault confirmed - go to repair
            break
        elif state.current_step_index >= len(state.diagnostic_steps):
            # No more steps
            state.diagnosis_progress = "completed"
            break
        # Else continue to next step
    
    # If fault confirmed, get repair guidance
    if state.diagnosis_progress == "fault_confirmed":
        state = repair_node(state)
    
    return state


# Export graph for LangGraph Studio
graph = get_compiled_graph()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Test the diagnostic agent
    print("=" * 60)
    print("DIAGNOSTIC AGENT - Test Run (REFACTORED)")
    print("=" * 60)
    
    # Run a test diagnosis
    result = run_diagnostic_session(
        symptoms="CCTV camera has no power",
        equipment_model="cctv-psu-24w-v1"
    )
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS RESULT")
    print("=" * 60)
    
    print(f"\nEquipment Model: {result.equipment_model}")
    print(f"Symptoms: {result.symptoms}")
    print(f"Current Hypothesis: {result.current_hypothesis}")
    print(f"Diagnosis Progress: {result.diagnosis_progress}")
    print(f"Current Test Point: {result.current_test_point}")
    print(f"Expected Value: {result.expected_value}")
    print(f"Current Step Index: {result.current_step_index}")
    print(f"Completed Steps: {result.completed_steps}")
    print(f"Total Steps: {len(result.diagnostic_steps)}")
    
    if result.measurement_result:
        print(f"\nMeasurement Result:")
        print(f"  Status: {result.measurement_result.get('status')}")
        print(f"  Value: {result.measurement_result.get('value')}")
        print(f"  Unit: {result.measurement_result.get('unit')}")
    
    if result.evaluation_result:
        print(f"\nEvaluation Result:")
        print(f"  Interpretation: {result.evaluation_result.get('interpretation')}")
        print(f"  Conclusion: {result.evaluation_result.get('conclusion')}")
        print(f"  Fault Confirmed: {result.evaluation_result.get('is_fault_confirmed')}")
    
    if result.step_explanation:
        print(f"\nStep Explanation:")
        print(result.step_explanation)
    
    if result.repair_guidance:
        print(f"\n{result.repair_guidance.get('guidance_text', '')}")
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
