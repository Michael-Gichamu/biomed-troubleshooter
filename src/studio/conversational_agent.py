"""
Conversational LangGraph Studio Diagnostic Agent

This module provides a hypothesis-driven diagnostic workflow for LangGraph Studio.
The agent guides engineers through diagnostic workflows with structured measurement
and evaluation steps.

Workflow Phases:
- RAG_NODE: Fetch diagnostic knowledge from RAG repository
- HYPOTHESES_NODE: Generate fault hypotheses with probabilities
- STEP_NODE: Perform atomic diagnostic step (measure, evaluate)
- REASON_NODE: Update hypotheses based on measurement results
- DECISION_NODE: Route based on hypothesis state (deterministic)
- REPAIR_NODE: Provide repair instructions for confirmed fault
- INTERRUPT_NODE: Pause for user to continue to next test point
- RESUME_NODE: Process user's "Next" response and continue
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Literal, Sequence, Annotated
import uuid
import os
import json
import re

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from src.studio.tools import get_tools


def extract_text_from_content(content) -> str:
    """Extract text from message content, handling both string and list formats.
    
    In LangGraph, message content can be either:
    - A string: "Hello world"
    - A list of content blocks: [{"type": "text", "text": "..."}, ...]
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Extract text from content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
        return " ".join(text_parts)
    return ""


# =============================================================================
# CONVERSATIONAL AGENT STATE
# =============================================================================

@dataclass
class ConversationalAgentState:
    """
    State for hypothesis-driven diagnostic workflow.
    
    This state tracks all information needed for the diagnostic workflow:
    - Equipment model and configuration (fetched ONCE in RAG_NODE)
    - Hypothesis tracking and probability updates
    - Measurements and fault identification
    - Control flags for workflow routing
    """
    # Messaging
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
    
    # Equipment (fetched ONCE at start - in RAG_NODE)
    equipment_model: str = ""
    config_cached: bool = False  # Track if equipment config has been fetched
    equipment_config: dict = field(default_factory=dict)  # Store all config data
    test_points: list = field(default_factory=list)  # List of test point definitions
    expected_values: dict = field(default_factory=dict)  # test_point_id -> {min, max, unit}
    
    # RAG knowledge
    rag_knowledge: list = field(default_factory=list)  # Diagnostic knowledge from RAG
    
    # Hypothesis-driven diagnostic tracking
    hypotheses: list = field(default_factory=list)  # List of possible fault hypotheses
    hypothesis_probabilities: dict = field(default_factory=dict)  # hypothesis -> probability
    eliminated_faults: list = field(default_factory=list)  # Faults eliminated by measurements
    current_hypothesis: str = ""  # Current working hypothesis being tested
    test_point_rankings: list = field(default_factory=list)  # Ranked test points by information value
    diagnostic_reasoning: list = field(default_factory=list)  # Reasoning chain for diagnosis
    
    # Diagnostic workflow (legacy - kept for compatibility)
    diagnostic_plan: list = field(default_factory=list)  # List of test points to check
    current_step: int = 0  # Index into diagnostic_plan
    completed_steps: list = field(default_factory=list)  # Completed step indices
    
    # Measurements
    measurements: list = field(default_factory=list)  # All measurements taken
    suspected_faults: list = field(default_factory=list)  # Faults identified
    confirmed_fault: str = ""  # Final confirmed fault
    
    # Step execution state
    next_test_point: str = ""  # Next TP to measure
    current_test_point: str = ""  # Current TP being measured
    step_result: dict = field(default_factory=dict)  # Holds: measurement, evaluation, reasoning, decision
    
    # Control flags
    waiting_for_next: bool = False  # True when paused at INTERRUPT_NODE
    diagnosis_complete: bool = False  # True when at END
    diagnosis_status: str = ""  # Status message for completion (e.g., "Inconclusive", "Max steps reached")
    
    # Iteration tracking (for safety limits)
    iteration_count: int = 0
    max_steps: int = 9  # Maximum diagnostic steps for hypothesis-driven approach

    # Routing (set by decision_node, read by route_from_decision)
    next_node: str = ""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_message_content(text: str, image_data: Optional[dict] = None) -> str:
    """
    Format message content with inline markdown image rendering.
    """
    if not image_data:
        return text
    
    image_url = image_data.get('image_url')
    if not image_url:
        return text
    
    test_point_info = image_data.get('test_point', '')
    location_desc = image_data.get('location_description', '')
    
    alt_text = test_point_info if test_point_info else "Test Point"
    markdown_image = f"![{alt_text}]({image_url})"
    
    header = ""
    if test_point_info:
        header = f"### {test_point_info}"
        if location_desc:
            header += f" - {location_desc}"
        header += "\n\n"
    
    markdown_content = f"{markdown_image}\n\n{header}{text}"
    return markdown_content


def clean_messages_for_llm(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Strip large base64 data URIs from message history to prevent token limits.
    """
    import re
    base64_re = re.compile(r'!\[.*?\]\(data:.*?;base64,.*?\)')
    
    cleaned = []
    for msg in messages:
        new_msg = msg.copy()
        
        if isinstance(new_msg.content, str):
            new_msg.content = base64_re.sub("[IMAGE DATA STRIPPED FOR STABILITY]", new_msg.content)
        elif isinstance(new_msg.content, list):
            new_content = []
            for block in new_msg.content:
                if isinstance(block, dict) and block.get("type") == "image_url":
                    new_content.append({"type": "text", "text": "[IMAGE ATTACHMENT STRIPPED FROM CONTEXT]"})
                else:
                    new_content.append(block)
            new_msg.content = new_content
            
        if isinstance(new_msg, ToolMessage):
            try:
                data = json.loads(new_msg.content)
                if isinstance(data, dict):
                    new_msg.content = json.dumps(data)
            except:
                pass
        cleaned.append(new_msg)
    return cleaned


# =============================================================================
# NODE DEFINITIONS
# =============================================================================

# =============================================================================
# RAG_NODE - Fetch diagnostic knowledge and equipment config ONCE
# =============================================================================

def rag_node(state: ConversationalAgentState):
    """
    RAG_NODE: Fetch diagnostic knowledge from RAG repository.
    
    This is called ONCE at the start of the diagnostic workflow:
    1. Query RAG for diagnostic procedures for the equipment model
    2. Fetch equipment configuration (test points, expected values, faults)
    3. Store all data in state for later use
    
    CRITICAL: Equipment config is fetched here ONCE and stored in state.
    It should NEVER be fetched again in later nodes.
    """
    from src.studio.tools import query_diagnostic_knowledge, get_equipment_configuration
    
    # First check if equipment_model is already in state
    equipment_model = state.equipment_model
    
    # If not in state, try to extract from message history
    if not equipment_model:
        pattern = r"cctv-psu-[a-z0-9-]+"
        
        # Iterate through messages in reverse (newest first) to find equipment model
        for message in reversed(state.messages):
            # Only check human (user) messages
            if isinstance(message, HumanMessage):
                text_content = extract_text_from_content(message.content)
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    equipment_model = match.group(0).lower()
                    break
    
    # If still not found, return error
    if not equipment_model:
        return {
            "messages": [AIMessage(content="Error: No equipment model provided. Please specify the equipment model to begin diagnosis.")]
        }
    
    # Step 1: Query RAG for diagnostic knowledge
    try:
        rag_result = query_diagnostic_knowledge.invoke({
            "query": "diagnostic procedures troubleshooting",
            "equipment_model": equipment_model,
            "top_k": 5
        })
        rag_knowledge = rag_result.get("results", []) if isinstance(rag_result, dict) else []
    except Exception as e:
        rag_knowledge = [{"error": str(e)}]
    
    # Step 2: Fetch equipment configuration ONCE (CRITICAL - never fetch again)
    try:
        config_result = get_equipment_configuration.invoke({
            "equipment_model": equipment_model,
            "request_type": "all"
        })
    except Exception as e:
        config_result = {"error": str(e), "test_points": [], "thresholds": {}, "faults": []}
    
    # Extract test points
    test_points = config_result.get("test_points", []) if isinstance(config_result, dict) else []
    
    # Extract expected values from thresholds
    thresholds = config_result.get("thresholds", {}) if isinstance(config_result, dict) else {}
    expected_values = {}
    for signal_id, threshold_data in thresholds.items():
        states = threshold_data.get("states", {})
        if "normal" in states:
            normal_state = states["normal"]
            expected_values[signal_id] = {
                "min": normal_state.get("min", 0),
                "max": normal_state.get("max", 999999),
                "unit": "V",  # Default unit
                "description": normal_state.get("description", "")
            }
    
    # Extract faults for later use
    faults = config_result.get("faults", []) if isinstance(config_result, dict) else []
    
    # Store everything in state — equipment_model MUST be returned so downstream nodes have it
    return {
        "equipment_model": equipment_model,
        "rag_knowledge": rag_knowledge,
        "equipment_config": config_result if isinstance(config_result, dict) else {},
        "test_points": test_points,
        "expected_values": expected_values,
        "suspected_faults": faults,
        "config_cached": True,
        "messages": [AIMessage(content=f"Diagnostic knowledge loaded for **{equipment_model}**. Found {len(test_points)} test points and {len(faults)} potential faults.")]
    }


# =============================================================================
# HYPOTHESES_NODE - Generate fault hypotheses using RAG and LLM
# =============================================================================

def hypotheses_node(state: ConversationalAgentState):
    """
    HYPOTHESES_NODE: Generate hypothesis-driven diagnostic approach.
    
    Instead of a static diagnostic plan, this node:
    1. Takes symptom from user input
    2. Queries RAG for possible fault hypotheses
    3. Generates initial hypotheses with probabilities
    4. Selects best first test based on information value
    
    Output: hypotheses list, hypothesis_probabilities, first test point, test_point_rankings
    """
    from src.infrastructure.llm_manager import invoke_with_retry
    
    # Build context for LLM
    equipment_model = state.equipment_model
    test_points = state.test_points
    rag_knowledge = state.rag_knowledge
    faults = state.suspected_faults
    
    # Get user's problem description (symptom) from messages
    symptom_description = ""
    for msg in state.messages:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            symptom_description += content + " "
    
    # Format test points for LLM
    test_points_str = "\n".join([
        f"- {tp.get('signal_id', tp.get('test_point', 'unknown'))}: {tp.get('name', '')} ({tp.get('parameter', '')})"
        for tp in test_points[:15]
    ])
    
    # Format faults for LLM
    faults_str = "\n".join([
        f"- {f.get('fault_id', '')}: {f.get('name', '')} - {f.get('description', '')[:150]}"
        for f in faults[:10]
    ]) if faults else "No fault definitions available"
    
    # Format RAG knowledge
    rag_str = "\n".join([
        f"- {k.get('content', '')[:200]}"
        for k in rag_knowledge[:3]
    ]) if rag_knowledge else "No diagnostic knowledge available"
    
    # Create hypothesis generation prompt
    hypothesis_prompt = f"""You are a diagnostic hypothesis generator. Based on the symptom, generate fault hypotheses.

EQUIPMENT: {equipment_model}
USER'S SYMPTOM: {symptom_description}

AVAILABLE TEST POINTS:
{test_points_str}

KNOWN FAULTS:
{faults_str}

DIAGNOSTIC KNOWLEDGE:
{rag_str}

Generate 3-5 most likely fault hypotheses based on the symptom.
For each hypothesis, provide:
1. A unique hypothesis ID (e.g., HYPOTHESIS_1, HYPOTHESIS_2)
2. Fault ID from the known faults (if applicable)
3. Brief description of what this fault would cause
4. Initial probability (0.0-1.0) based on how well it matches the symptom

Output as JSON array:
[
  {{"id": "HYPOTHESIS_1", "fault_id": "F001", "description": "...", "probability": 0.4}},
  {{"id": "HYPOTHESIS_2", "fault_id": null, "description": "...", "probability": 0.3}}
]

Only output the JSON array, nothing else."""
    
    # Call LLM for hypothesis generation
    hypotheses = []
    hypothesis_probabilities = {}
    
    try:
        response = invoke_with_retry([{"role": "user", "content": hypothesis_prompt}])
        content = response.content if response else "[]"
        
        # Parse JSON array from response
        import re
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            hypotheses = json.loads(json_match.group(0))
            for h in hypotheses:
                hypothesis_probabilities[h.get('id', '')] = h.get('probability', 0.1)
    except Exception as e:
        # Fallback: create generic hypotheses from faults
        for i, fault in enumerate(faults[:5]):
            h = {
                "id": f"HYPOTHESIS_{i+1}",
                "fault_id": fault.get('fault_id', ''),
                "description": fault.get('description', '')[:100],
                "probability": 1.0 / min(len(faults), 5)
            }
            hypotheses.append(h)
            hypothesis_probabilities[h['id']] = h['probability']
    
    # Filter out empty hypotheses
    hypotheses = [h for h in hypotheses if h.get('id')]
    
    # Normalize probabilities to sum to 1
    total_prob = sum(hypothesis_probabilities.values())
    if total_prob > 0:
        for h_id in hypothesis_probabilities:
            hypothesis_probabilities[h_id] /= total_prob
    
    # Select best first test based on information value — using actual signal_ids
    ranking_prompt = f"""You are a diagnostic expert. Rank these test points by information value for this symptom.

EQUIPMENT: {equipment_model}
SYMPTOM: {symptom_description}

AVAILABLE TEST POINTS (use the signal_id exactly as shown):
{test_points_str}

HYPOTHESES TO DISTINGUISH:
{chr(10).join([h.get('description', '') for h in hypotheses])}

Rules:
- Output ONLY the signal_ids from the list above, exactly as written
- Order from highest to lowest diagnostic value
- The first test should eliminate the most hypotheses with one measurement
- For a dead output with AC confirmed, measuring the DC bus first is always highest value

Output as a JSON array of signal_ids:
["signal_id_1", "signal_id_2", "signal_id_3", ...]

Only output the JSON array, nothing else."""
    
    test_point_rankings = []
    try:
        response = invoke_with_retry([{"role": "user", "content": ranking_prompt}])
        content = response.content if response else "[]"

        start = content.find('[')
        end = content.rfind(']')
        if start != -1 and end != -1:
            test_point_rankings = json.loads(content[start:end+1])
    except:
        # Fallback: use all test points in order — signal_ids not TP notation
        test_point_rankings = [tp.get('signal_id', '') for tp in test_points if tp.get('signal_id')]

    # Filter to only valid signal_ids that actually exist in test_points
    valid_signal_ids = {tp.get('signal_id', '') for tp in test_points}
    test_point_rankings = [tp for tp in test_point_rankings if tp and tp in valid_signal_ids]

    # If still empty after filtering, fall back to all signal_ids in order
    if not test_point_rankings:
        test_point_rankings = [tp.get('signal_id', '') for tp in test_points if tp.get('signal_id')]

    # Set current hypothesis to the highest probability one
    current_hypothesis = ""
    if hypotheses:
        current_hypothesis = max(hypotheses, key=lambda h: hypothesis_probabilities.get(h['id'], 0)).get('id', '')

    # Create diagnostic_plan for backward compatibility
    diagnostic_plan = test_point_rankings[:state.max_steps]

    # Get first test point details for probe instructions
    first_signal_id = test_point_rankings[0] if test_point_rankings else ""
    first_signal = {}
    for sig in state.equipment_config.get("signals", []):
        if sig.get("signal_id") == first_signal_id:
            first_signal = sig
            break

    # Build expert-quality hypothesis message
    sorted_hypotheses = sorted(hypotheses, key=lambda h: hypothesis_probabilities.get(h['id'], 0), reverse=True)

    hypothesis_message = "## Diagnostic Assessment\n\n"
    hypothesis_message += f"Based on the symptom — **{symptom_description.strip()}** — here are the most likely fault candidates:\n\n"

    for h in sorted_hypotheses:
        prob = hypothesis_probabilities.get(h['id'], 0)
        hypothesis_message += f"- **{h.get('description', '')}** ({prob:.0%} probability)\n"

    hypothesis_message += f"\n---\n\n"
    hypothesis_message += f"### First Test: {first_signal.get('name', first_signal_id)}\n\n"

    # Inline image — shown before probe placement text so engineer sees the location first
    first_image_url = first_signal.get("image_url", "")
    if first_image_url:
        hypothesis_message += f"![{first_signal.get('name', first_signal_id)}]({first_image_url})\n\n"

    if first_signal.get('safety_warning'):
        hypothesis_message += f"⚠️ **SAFETY:** {first_signal['safety_warning']}\n\n"

    if first_signal.get('physical_description'):
        hypothesis_message += f"**Where to find it:** {first_signal['physical_description']}\n\n"

    if first_signal.get('probe_placement'):
        hypothesis_message += f"**How to measure:**\n{first_signal['probe_placement']}\n\n"

    hypothesis_message += "**Press NEXT when your probes are in position.**"

    return {
        "hypotheses": hypotheses,
        "hypothesis_probabilities": hypothesis_probabilities,
        "eliminated_faults": [],
        "current_hypothesis": current_hypothesis,
        "test_point_rankings": test_point_rankings,
        "diagnostic_reasoning": [f"Initial hypotheses generated: {len(hypotheses)} fault candidates"],
        "diagnostic_plan": diagnostic_plan,
        "current_step": 0,
        "messages": [AIMessage(content=hypothesis_message)]
    }


# =============================================================================
# STEP_NODE - Atomic diagnostic step with hypothesis guidance
# =============================================================================

def step_node(state: ConversationalAgentState):
    """
    STEP_NODE: Performs the ENTIRE diagnostic step atomically with hypothesis guidance:
    
    1. Show current hypothesis being tested
    2. Show test point name and location
    3. Show probe placement instructions
    4. Show test point image
    5. Call read_multimeter
    6. Wait for stabilization (handled by read_multimeter)
    7. Evaluate measured value vs expected range
    8. Route to REASON node for hypothesis update
    
    Returns: measurement, evaluation, decision (pending REASON update)
    """
    from src.studio.tools import get_test_point_guidance, read_multimeter
    from src.infrastructure.llm_manager import invoke_with_retry
    
    # Get current test point from test_point_rankings (hypothesis-driven)
    if state.current_step >= len(state.test_point_rankings):
        return {
            "step_result": {
                "decision": "no_more_tests",
                "reasoning": "No more test points available to check"
            },
            "messages": [AIMessage(content="No more test points available. Proceeding to reasoning...")]
        }
    
    test_point_id = state.test_point_rankings[state.current_step]
    
    # Get expected values for this test point
    expected = state.expected_values.get(test_point_id, {"min": 0, "max": 999, "unit": "V"})
    
    # Get signal definition for measurement type (DC/AC, resistance, etc.)
    signal_def = {}
    for sig in state.equipment_config.get("signals", []):
        if sig.get("signal_id") == test_point_id:
            signal_def = sig
            break
    
    # Get current hypothesis info
    current_hyp_desc = ""
    for h in state.hypotheses:
        if h.get('id') == state.current_hypothesis:
            current_hyp_desc = h.get('description', '')
            break
    
    # Step 1-4: Get guidance (shows location, image, probe placement)
    try:
        guidance = get_test_point_guidance.invoke({
            "equipment_model": state.equipment_model,
            "test_point_id": test_point_id
        })
    except Exception as e:
        guidance = {"error": str(e), "name": test_point_id, "test_point": test_point_id}
    
    # Step 5: Take measurement
    # Get measurement type from signal definition
    measurement_type = signal_def.get("parameter", "voltage_dc")
    try:
        measurement_result = read_multimeter.invoke({
            "equipment_model": state.equipment_model,
            "test_point": test_point_id,
            "measurement_type": measurement_type
        })
    except Exception as e:
        measurement_result = {"status": "error", "error": str(e), "test_point": test_point_id}
    
    # Extract measurement value
    measurement_value = measurement_result.get("value", 0)
    measurement_unit = measurement_result.get("unit", expected.get("unit", "V"))
    status = measurement_result.get("status", "unknown")
    
    # Step 6: Evaluate against expected range
    is_fault = False
    evaluation = "normal"
    
    if status == "success":
        min_val = expected.get("min", 0)
        max_val = expected.get("max", 999999)
        if not (min_val <= measurement_value <= max_val):
            is_fault = True
            evaluation = "fault"
    
    # Step 7-8: Build expert-quality measurement report
    signal_name = signal_def.get("name", test_point_id)
    
    # Get parameter type for display (e.g., "voltage_dc" -> "DC Voltage")
    param = signal_def.get("parameter", "")
    param_display = ""
    if param:
        # Format parameter for display
        param_formatted = param.replace("_", " ").title()
        param_display = f" ({param_formatted})"

    explanation = f"## Measurement Result — {signal_name}\n\n"

    # Add hypothesis context
    if state.current_hypothesis and current_hyp_desc:
        explanation += f"*Testing whether: {current_hyp_desc}*\n\n"

    # Add image if available
    guidance_image = guidance.get("image_url", "")
    if guidance_image:
        explanation += f"![{test_point_id}]({guidance_image})\n\n"

    # Clear measurement with fault/normal call-out
    if evaluation == "fault":
        explanation += f"### ⚠️ FAULT READING\n"
        explanation += f"**{signal_name}:** {measurement_value} {measurement_unit}{param_display}\n"
        explanation += f"**Expected:** {expected.get('min', 0)} – {expected.get('max', 999999)} {measurement_unit}\n\n"
        # Add diagnostic interpretation from signal definition
        diag_meaning = signal_def.get("diagnostic_meaning", "")
        if diag_meaning:
            explanation += f"**What this tells us:** {diag_meaning}\n"
    else:
        explanation += f"### ✓ READING NORMAL\n"
        explanation += f"**{signal_name}:** {measurement_value} {measurement_unit}{param_display}\n"
        explanation += f"**Expected:** {expected.get('min', 0)} – {expected.get('max', 999999)} {measurement_unit}\n\n"
        diag_meaning = signal_def.get("diagnostic_meaning", "")
        if diag_meaning:
            explanation += f"**What this tells us:** {diag_meaning}\n"

    explanation += "\n*Updating hypothesis probabilities...*"
    
    # Prepare measurement record
    measurement_record = {
        "test_point": test_point_id,
        "value": measurement_value,
        "unit": measurement_unit,
        "status": status,
        "evaluation": evaluation,
        "expected_min": expected.get("min", 0),
        "expected_max": expected.get("max", 999999),
        "hypothesis_being_tested": state.current_hypothesis,
        "timestamp": str(datetime.now())
    }
    
    return {
        "current_test_point": test_point_id,
        "step_result": {
            "measurement": measurement_record,
            "evaluation": evaluation,
            "reasoning": "",  # Will be filled by REASON node
            "decision": "pending_reasoning",  # Will be updated by REASON node
            "next_test_point": state.test_point_rankings[state.current_step + 1] if state.current_step + 1 < len(state.test_point_rankings) else None
        },
        "measurements": state.measurements + [measurement_record],
        "next_test_point": state.test_point_rankings[state.current_step + 1] if state.current_step + 1 < len(state.test_point_rankings) else "",
        "messages": [AIMessage(content=explanation)],
        "iteration_count": state.iteration_count + 1
    }


# =============================================================================
# REASON_NODE - Update hypotheses based on measurement result
# =============================================================================

def reason_node(state: ConversationalAgentState):
    """
    REASON_NODE: Evaluate measurement result against hypotheses and update probabilities.
    
    This node:
    1. Evaluates measurement result against expected values
    2. Updates hypothesis probabilities based on result
    3. Eliminates faults that are disproven by measurements
    4. Checks if any hypothesis is confirmed (>90% probability)
    5. Selects next best test if diagnosis continues
    
    Returns: updated hypotheses, probabilities, decision
    """
    from src.infrastructure.llm_manager import invoke_with_retry
    
    # Get last measurement
    if not state.measurements:
        return {
            "step_result": {
                "decision": "error",
                "reasoning": "No measurements available"
            }
        }
    
    last_measurement = state.measurements[-1]
    test_point_id = last_measurement.get("test_point", "")
    measurement_value = last_measurement.get("value", 0)
    measurement_unit = last_measurement.get("unit", "V")
    evaluation = last_measurement.get("evaluation", "normal")
    
    # Get expected values
    expected = state.expected_values.get(test_point_id, {"min": 0, "max": 999, "unit": "V"})
    
    # Get current hypothesis details
    current_hyp = None
    for h in state.hypotheses:
        if h.get('id') == state.current_hypothesis:
            current_hyp = h
            break
    
    # Build prompt for hypothesis update
    hypotheses_str = "\n".join([
        f"- {h.get('id', '')}: {h.get('description', '')} (current P={state.hypothesis_probabilities.get(h.get('id'), 0):.2f})"
        for h in state.hypotheses
    ])
    
    eval_prompt = f"""Evaluate the measurement result against the hypotheses and update probabilities.

TEST POINT: {test_point_id}
MEASUREMENT: {measurement_value} {measurement_unit}
EXPECTED: {expected.get('min', 0)} - {expected.get('max', 999999)} {measurement_unit}
EVALUATION: {evaluation}

CURRENT HYPOTHESES:
{hypotheses_str}

Based on this measurement result:
1. Which hypotheses does this result SUPPORT? (increase probability)
2. Which hypotheses does this result CONTRADICT? (decrease probability to 0)
3. Is any hypothesis now CONFIRMED (>90% probability)?

Output JSON with:
{{
  "reasoning": "Brief analysis of what this measurement tells us",
  "probability_updates": {{"HYPOTHESIS_1": 0.3, "HYPOTHESIS_2": 0.0, ...}},
  "eliminated_faults": ["HYPOTHESIS_2", ...],
  "confirmed_hypothesis": "HYPOTHESIS_1" or null,
  "new_current_hypothesis": "HYPOTHESIS_3" or null
}}

Only output JSON, nothing else."""
    
    # Call LLM for reasoning — use rfind to correctly extract full JSON object
    reasoning = ""
    eliminated_faults = list(state.eliminated_faults)
    confirmed_hypothesis = None
    # Work on a copy — never mutate state in place in LangGraph
    updated_hypothesis_probabilities = dict(state.hypothesis_probabilities)

    try:
        response = invoke_with_retry([{"role": "user", "content": eval_prompt}])
        content = response.content if response else "{}"

        # Correct extraction: find outermost { } pair
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            result = json.loads(content[start:end+1])
            reasoning = result.get('reasoning', '')

            # Update probabilities on the copy
            prob_updates = result.get('probability_updates', {})
            for h_id, new_prob in prob_updates.items():
                if h_id in updated_hypothesis_probabilities:
                    updated_hypothesis_probabilities[h_id] = float(new_prob)

            # Track eliminated faults
            new_eliminated = result.get('eliminated_faults', [])
            for e in new_eliminated:
                if e not in eliminated_faults:
                    eliminated_faults.append(e)

            # Check for confirmed hypothesis
            confirmed_hypothesis = result.get('confirmed_hypothesis') or None
    except Exception as e:
        reasoning = f"Analysis inconclusive — proceeding with current hypotheses."
    
    # Normalize probabilities to sum to 1 (excluding eliminated)
    active_probs = {h_id: prob for h_id, prob in updated_hypothesis_probabilities.items() 
                   if h_id not in eliminated_faults}
    total_active = sum(active_probs.values())
    if total_active > 0:
        for h_id in active_probs:
            updated_hypothesis_probabilities[h_id] = active_probs[h_id] / total_active
    
    # Select new current hypothesis if needed
    new_current_hypothesis = state.current_hypothesis
    if confirmed_hypothesis:
        new_current_hypothesis = confirmed_hypothesis
    elif not new_current_hypothesis or new_current_hypothesis in eliminated_faults:
        # Select highest probability non-eliminated hypothesis
        best_h = None
        best_prob = -1
        for h in state.hypotheses:
            h_id = h.get('id', '')
            if h_id not in eliminated_faults:
                prob = updated_hypothesis_probabilities.get(h_id, 0)
                if prob > best_prob:
                    best_prob = prob
                    best_h = h_id
        new_current_hypothesis = best_h or ""
    
    # Determine decision based on results
    decision = "continue_diagnosis"
    if confirmed_hypothesis:
        decision = "fault_confirmed"
    elif not new_current_hypothesis or len([h for h in state.hypotheses if h.get('id') not in eliminated_faults]) == 0:
        decision = "all_eliminated"
    
    # Build expert-quality analysis output
    explanation = "## Analysis\n\n"

    if reasoning:
        explanation += f"{reasoning}\n\n"

    # Show hypothesis status concisely
    explanation += "**Fault candidate status:**\n"
    sorted_hyps = sorted(state.hypotheses, key=lambda h: updated_hypothesis_probabilities.get(h.get('id'), 0), reverse=True)
    for h in sorted_hyps:
        h_id = h.get('id', '')
        if h_id in eliminated_faults:
            explanation += f"- ~~{h.get('description', h_id)}~~ — **eliminated**\n"
        else:
            prob = updated_hypothesis_probabilities.get(h_id, 0)
            marker = " ← most likely" if h_id == new_current_hypothesis else ""
            explanation += f"- {h.get('description', h_id)}: **{prob:.0%}**{marker}\n"
    
    # Update diagnostic reasoning chain
    diagnostic_reasoning = list(state.diagnostic_reasoning)
    diagnostic_reasoning.append(f"Step {state.current_step + 1}: Tested {test_point_id}, result={evaluation}. {reasoning[:100] if reasoning else ''}")
    
    return {
        "hypothesis_probabilities": updated_hypothesis_probabilities,
        "eliminated_faults": eliminated_faults,
        "current_hypothesis": new_current_hypothesis,
        "diagnostic_reasoning": diagnostic_reasoning,
        "step_result": {
            "measurement": last_measurement,
            "evaluation": evaluation,
            "reasoning": reasoning,
            "decision": decision,
            "next_test_point": state.test_point_rankings[state.current_step + 1] if state.current_step + 1 < len(state.test_point_rankings) else None
        },
        "messages": [AIMessage(content=explanation)]
    }


# =============================================================================
# DECISION_NODE - Hypothesis-driven routing with proper termination
# =============================================================================

def decision_node(state: ConversationalAgentState):
    """
    DECISION_NODE: Routes based on hypothesis-driven termination conditions.
    
    Checks conditions in order:
    1. IF confirmed_fault is not None → GO TO REPAIR
    2. ELSE IF step_result.decision == "fault_confirmed" → GO TO REPAIR
    3. ELSE IF all hypotheses eliminated → Diagnosis = Inconclusive, STOP
    4. ELSE IF current_step >= max_steps → Diagnosis = Max steps reached, STOP
    5. ELSE IF no remaining useful tests → Diagnosis = Insufficient data, STOP
    6. ELSE → Continue diagnosis loop (GO TO INTERRUPT)
    """
    # Check if fault already confirmed
    if state.confirmed_fault:
        return {"next_node": "repair"}
    
    decision = state.step_result.get("decision", "continue_diagnosis")
    
    # 1. Fault confirmed from reasoning
    if decision == "fault_confirmed":
        return {"next_node": "repair"}
    
    # 2. All hypotheses eliminated
    active_hypotheses = [h for h in state.hypotheses if h.get('id') not in state.eliminated_faults]
    if len(active_hypotheses) == 0:
        return {
            "next_node": "end",
            "diagnosis_status": "inconclusive",
            "diagnosis_complete": True,
            "messages": [AIMessage(content="## Diagnosis Complete - Inconclusive\n\nAll hypotheses have been eliminated by measurements. Unable to determine the fault.")]
        }
    
    # 3. Max steps reached
    if state.current_step >= state.max_steps:
        return {
            "next_node": "end",
            "diagnosis_status": "max_steps_reached",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=f"## Diagnosis Complete - Max Steps Reached\n\nAfter {state.max_steps} diagnostic steps, no conclusive fault was identified.")]
        }
    
    # 4. No more test points available (check NEXT step, since current was just executed)
    if state.current_step + 1 >= len(state.test_point_rankings):
        return {
            "next_node": "end",
            "diagnosis_status": "insufficient_data",
            "diagnosis_complete": True,
            "messages": [AIMessage(content="## Diagnosis Complete - Insufficient Data\n\nNo more test points available to continue diagnosis.")]
        }
    
    # 5. Continue diagnosis
    return {"next_node": "interrupt"}


# =============================================================================
# REPAIR_NODE - Provide repair instructions
# =============================================================================

def repair_node(state: ConversationalAgentState):
    """
    REPAIR_NODE: Based on confirmed fault, get repair instructions.
    
    This node is triggered when:
    - A fault is confirmed (from hypothesis reasoning)
    - OR only one possible hypothesis remains
    
    1. Identify the fault based on current hypothesis
    2. Get repair instructions from equipment config
    3. Add to messages
    4. Set diagnosis_complete = True
    5. Route to END
    """
    from src.infrastructure.llm_manager import invoke_with_retry
    
    # Get fault information from config
    faults = state.suspected_faults
    
    # Get current hypothesis
    current_hypothesis = state.current_hypothesis
    
    # Find fault associated with current hypothesis
    fault_id = ""
    fault_name = "Unknown Fault"
    for h in state.hypotheses:
        if h.get('id') == current_hypothesis:
            fault_id = h.get('fault_id', '')
            break
    
    # Get last measurement
    last_measurement = state.measurements[-1] if state.measurements else {}
    test_point = last_measurement.get("test_point", "")
    value = last_measurement.get("value", 0)
    
    # Find matching fault
    repair_instructions = "No specific repair instructions found."
    
    if faults:
        # If we have a fault_id from hypothesis, use it
        if fault_id:
            for fault in faults:
                if fault.get("fault_id", "") == fault_id:
                    fault_name = fault.get('name', 'Unknown')
                    recovery = fault.get('recovery', [])
                    if recovery:
                        repair_steps = "\n".join([
                            f"{i+1}. {r.get('step', '')}: {r.get('instruction', '')}"
                            for i, r in enumerate(recovery)
                        ])
                        repair_instructions = f"### Repair Procedure for {fault_name}\n\n{repair_steps}"
                    break
        else:
            # Use LLM to match measurement to fault
            faults_str = "\n".join([
                f"- {f.get('fault_id', '')}: {f.get('name', '')}\n  {f.get('description', '')}\n  Recovery: {f.get('recovery', [])}"
                for f in faults[:5]
            ])
            
            match_prompt = f"""Based on the measurement at {test_point} = {value}, which fault best matches?

FAULTS:
{faults_str}

Output ONLY the fault ID that best matches, nothing else."""
            
            try:
                response = invoke_with_retry([{"role": "user", "content": match_prompt}])
                matched_fault_id = response.content.strip() if response else ""
            except:
                matched_fault_id = ""
            
            # Find the matched fault
            for fault in faults:
                if fault.get("fault_id", "") == matched_fault_id:
                    fault_name = fault.get("name", "Unknown")
                    recovery = fault.get("recovery", [])
                    if recovery:
                        repair_steps = "\n".join([
                            f"{i+1}. {r.get('step', '')}: {r.get('instruction', '')}"
                            for i, r in enumerate(recovery)
                        ])
                        repair_instructions = f"### Repair Procedure for {fault_name}\n\n{repair_steps}"
                    break
    
    # Final message — expert quality repair guidance
    final_message = "## Diagnosis Complete — Fault Confirmed\n\n"
    final_message += f"**Confirmed fault:** {fault_name}\n"
    if current_hypothesis:
        # Find the hypothesis description
        for h in state.hypotheses:
            if h.get('id') == current_hypothesis:
                final_message += f"**Mechanism:** {h.get('description', '')}\n"
                break
    final_message += f"**Confirmed by measurement at:** {test_point} = {value}\n\n"
    final_message += "---\n\n"
    final_message += repair_instructions
    final_message += "\n\n---\n**Verify the repair by measuring the 12V output at J1 or the output terminal block. Expected: 11.4–12.6V DC.**"
    
    return {
        "confirmed_fault": fault_name,
        "diagnosis_complete": True,
        "messages": [AIMessage(content=final_message)]
    }


# =============================================================================
# INTERRUPT_NODE - Pause for user to continue
# =============================================================================

def interrupt_node(state: ConversationalAgentState):
    """
    INTERRUPT_NODE: Pause and show the engineer exactly what to do next.

    Shows probe placement instructions for the NEXT test point BEFORE the measurement
    is taken, so the engineer can position their probes correctly.
    Then pauses until they press NEXT.
    """
    step_num = state.current_step + 1  # current_step is incremented by resume_node AFTER this
    total_steps = len(state.test_point_rankings)

    # Determine which test point comes NEXT (after resume increments current_step)
    next_step_index = state.current_step + 1
    next_signal_id = ""
    if next_step_index < len(state.test_point_rankings):
        next_signal_id = state.test_point_rankings[next_step_index]

    # Look up the next signal's probe placement instructions from equipment config
    next_signal = {}
    if next_signal_id:
        for sig in state.equipment_config.get("signals", []):
            if sig.get("signal_id") == next_signal_id:
                next_signal = sig
                break

    # Build the instruction message
    instruction_parts = []

    if next_signal:
        instruction_parts.append(f"## Next Measurement — {next_signal.get('name', next_signal_id)}")

        # Inline image — shown first so engineer sees the physical location before reading the text
        next_image_url = next_signal.get("image_url", "")
        if next_image_url:
            instruction_parts.append(f"![{next_signal.get('name', next_signal_id)}]({next_image_url})")

        if next_signal.get('safety_warning'):
            instruction_parts.append(f"⚠️ **SAFETY FIRST:** {next_signal['safety_warning']}")

        if next_signal.get('physical_description'):
            instruction_parts.append(f"**Where to find it:**\n{next_signal['physical_description']}")

        if next_signal.get('probe_placement'):
            instruction_parts.append(f"**How to measure:**\n{next_signal['probe_placement']}")

        if next_signal.get('expected_behavior'):
            instruction_parts.append(f"**Expected reading:** {next_signal['expected_behavior']}")

        instruction_parts.append("**Press NEXT when your probes are in position and stable.**")
    else:
        # No more tests — this is the last interrupt before completion
        instruction_parts.append("## All measurements complete.")
        instruction_parts.append("**Press NEXT to see the diagnosis summary.**")

    instruction_text = "\n\n".join(instruction_parts)

    # Mark waiting state
    state.waiting_for_next = True

    # Use interrupt to pause and wait for human
    interrupt({
        "instruction": instruction_text,
        "current_step": state.current_step,
        "total_steps": total_steps,
        "next_test_point": next_signal_id,
        "current_hypothesis": state.current_hypothesis
    })

    return {
        "waiting_for_next": True
    }


# =============================================================================
# RESUME_NODE - Process user's "Next" response
# =============================================================================

def resume_node(state: ConversationalAgentState):
    """
    RESUME_NODE: Process user's "Next" response.
    
    Increment current_step and route back to STEP_NODE.
    """
    return {
        "current_step": state.current_step + 1,
        "waiting_for_next": False
    }


# =============================================================================
# CONDITIONAL EDGES
# =============================================================================

def route_from_decision(state: ConversationalAgentState) -> str:
    """Route based on decision_node output (reads state.next_node set by decision_node)."""
    next_node = state.next_node or "interrupt"

    if next_node == "repair":
        return "repair"
    elif next_node == "end":
        return "end"
    elif next_node == "interrupt":
        return "interrupt"
    else:
        return "interrupt"


def route_from_interrupt(state: ConversationalAgentState) -> str:
    """Route after interrupt - always go to step_node for next test."""
    # Check if we've exceeded max steps
    if state.current_step >= state.max_steps:
        return "end"
    
    # Check if there are any remaining test points
    if state.current_step >= len(state.test_point_rankings):
        return "end"
    
    return "step"


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_conversational_graph():
    """Build the hypothesis-driven diagnostic workflow graph."""
    builder = StateGraph(ConversationalAgentState)
    
    # Add all nodes
    builder.add_node("rag", rag_node)
    builder.add_node("hypotheses", hypotheses_node)
    builder.add_node("step", step_node)
    builder.add_node("reason", reason_node)
    builder.add_node("decision", decision_node)
    builder.add_node("repair", repair_node)
    builder.add_node("interrupt", interrupt_node)
    builder.add_node("resume", resume_node)
    
    # Start at RAG_NODE
    builder.add_edge(START, "rag")
    
    # RAG → HYPOTHESES: After fetching knowledge and config, generate hypotheses
    builder.add_edge("rag", "hypotheses")
    
    # HYPOTHESES → STEP: After generating hypotheses, go to first step
    builder.add_edge("hypotheses", "step")
    
    # STEP → REASON: After each step, evaluate result against hypotheses
    builder.add_edge("step", "reason")
    
    # REASON → DECISION: After updating hypotheses, make routing decision
    builder.add_edge("reason", "decision")
    
    # DECISION → REPAIR, END, or INTERRUPT (deterministic routing)
    builder.add_conditional_edges(
        "decision",
        route_from_decision,
        {
            "repair": "repair",
            "interrupt": "interrupt",
            "end": END
        }
    )
    
    # INTERRUPT → RESUME: Wait for user input
    builder.add_edge("interrupt", "resume")
    
    # RESUME → STEP: After user confirms, go to next step
    builder.add_conditional_edges(
        "resume",
        route_from_interrupt,
        {
            "step": "step",
            "end": END
        }
    )
    
    # REPAIR → END: Final state
    builder.add_edge("repair", END)
    
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


# =============================================================================
# GRAPH FACTORY FOR LANGGRAPH STUDIO
# =============================================================================

def graph():
    """
    Return the compiled conversational graph for LangGraph Studio.
    """
    return create_conversational_graph()


# =============================================================================
# TEST / ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    from datetime import datetime
    print("Creating hypothesis-driven diagnostic graph...")
    g = create_conversational_graph()
    print("Success!")
    print("\nWorkflow: START → RAG → HYPOTHESES → STEP → REASON → DECISION → (REPAIR | INTERRUPT → RESUME → STEP)")
    print("Hypothesis-driven routing with proper termination conditions.")