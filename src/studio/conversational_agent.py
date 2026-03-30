"""
Conversational LangGraph Studio Diagnostic Agent

Hypothesis-driven diagnostic workflow for LangGraph Studio.
Guides engineers through structured fault diagnosis with real multimeter readings.

Workflow:
  START → rag → hypotheses → instruction → step → reason → decision
                                  ↑                              |
                                  ←──── resume ← interrupt ──────┘  (if no fault)
  decision → repair → END
  decision → END  (inconclusive / max steps)

Node roles:
  rag          -- Fetch equipment config and RAG knowledge ONCE at start (parallel calls)
  hypotheses   -- Generate ranked fault hypotheses from symptom + RAG
  instruction  -- Show probe placement for current test point (NO pause)
  step         -- Take stabilised multimeter reading; report result
  reason       -- Update hypothesis probabilities from measurement; advance step counter
  decision     -- Route: repair | interrupt (next step) | END
  interrupt    -- Pause for engineer "Next" confirmation ONLY (no probe info)
  resume       -- Clear waiting flag; pass control back to instruction
  repair       -- Identify root cause + secondary damage; emit combined repair plan; END
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Annotated
import json
import re

from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from src.studio.tools import get_tools  # noqa -- keeps tool registration alive


# =============================================================================
# HELPERS
# =============================================================================

def _text(content) -> str:
    """Extract plain text from either a string or a LangGraph content-block list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


# =============================================================================
# STATE
# =============================================================================

@dataclass
class ConversationalAgentState:
    """
    All state for the hypothesis-driven diagnostic workflow.

    Populated in rag_node ONCE and carried forward.  Nodes return dicts
    with only the keys they change -- LangGraph merges them into state.
    """
    # ── Messaging ────────────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)

    # ── Equipment (set in rag_node, never mutated again) ─────────────────────
    equipment_model: str = ""
    config_cached: bool = False
    equipment_config: dict = field(default_factory=dict)
    # test_points: basic list from "all" config  →  used for LLM prompts
    test_points: list = field(default_factory=list)
    # expected_values: {signal_id: {min, max, unit, description}}
    expected_values: dict = field(default_factory=dict)

    # ── RAG knowledge ────────────────────────────────────────────────────────
    rag_knowledge: list = field(default_factory=list)

    # ── Hypothesis tracking ──────────────────────────────────────────────────
    hypotheses: list = field(default_factory=list)
    hypothesis_probabilities: dict = field(default_factory=dict)
    eliminated_faults: list = field(default_factory=list)
    current_hypothesis: str = ""
    test_point_rankings: list = field(default_factory=list)
    diagnostic_reasoning: list = field(default_factory=list)

    # ── Diagnostic plan (kept for routing logic) ─────────────────────────────
    diagnostic_plan: list = field(default_factory=list)
    current_step: int = 0          # index into test_point_rankings
    completed_steps: list = field(default_factory=list)

    # ── Measurements & faults ────────────────────────────────────────────────
    measurements: list = field(default_factory=list)
    suspected_faults: list = field(default_factory=list)
    confirmed_fault: str = ""

    # ── Step execution state ─────────────────────────────────────────────────
    next_test_point: str = ""
    current_test_point: str = ""
    step_result: dict = field(default_factory=dict)

    # ── Control flags ────────────────────────────────────────────────────────
    waiting_for_next: bool = False
    diagnosis_complete: bool = False
    diagnosis_status: str = ""

    # ── Safety limits ────────────────────────────────────────────────────────
    iteration_count: int = 0
    max_steps: int = 9

    # ── Routing (set by decision_node) ───────────────────────────────────────
    next_node: str = ""


# =============================================================================
# =============================================================================
# RAG CACHE -- singleton for diagnostic knowledge per equipment model
# =============================================================================

# Cache for RAG results per equipment model (loaded once, reused forever)
_rag_cache: dict[str, list] = {}


def _get_cached_rag_knowledge(equipment_model: str, force_refresh: bool = False) -> list:
    """
    Get diagnostic knowledge from RAG, with caching per equipment model.

    Truly non-blocking: uses threading.Thread + join(timeout=5).
    ThreadPoolExecutor.__exit__ calls shutdown(wait=True) which blocks until the
    thread finishes even after a TimeoutError -- that is why initialization was
    still taking 5 minutes.  Thread.join(timeout) returns immediately once the
    timeout expires and does NOT wait for the thread.  The daemon thread keeps
    running in the background so RAG will be ready for later conversations.
    """
    if not force_refresh and equipment_model in _rag_cache:
        return _rag_cache[equipment_model]

    import threading
    from src.studio.tools import query_diagnostic_knowledge

    result_holder: list = [None]

    def _do_query():
        try:
            result_holder[0] = query_diagnostic_knowledge.invoke({
                "query": "diagnostic procedures troubleshooting fault",
                "equipment_model": equipment_model,
                "top_k": 5
            })
        except Exception as exc:
            print(f"[RAG] Query thread error (non-fatal): {exc}")

    t = threading.Thread(target=_do_query, daemon=True, name=f"rag-query-{equipment_model}")
    t.start()
    t.join(timeout=5.0)  # Returns immediately after 5 s -- does NOT block like ThreadPoolExecutor

    if t.is_alive():
        # sentence-transformers still loading -- proceed without RAG now.
        # Not cached so the next conversation will retry.
        print("[RAG] Cold-start timeout -- proceeding without RAG knowledge.")
        return []

    r = result_holder[0]
    results = r.get("results", []) if isinstance(r, dict) else []
    _rag_cache[equipment_model] = results
    return results


# =============================================================================
# NODE: RAG -- fetch config & knowledge ONCE
# =============================================================================

def rag_node(state: ConversationalAgentState):
    """
    Fetch everything we need for the whole session in a single pass:
      1. Extract equipment model from the user's message.
      2. Query RAG for diagnostic knowledge snippets.
      3. Fetch complete equipment config (thresholds, faults, images).
      4. Fetch full signal list (physical_description, image_url, pro_tips).
      5. Build expected_values lookup with correct per-signal units.
      6. Emit a brief initialisation AIMessage.
    """
    from src.infrastructure.equipment_config import get_equipment_config

    equipment_model = state.equipment_model

    # ── Detect new thread: exactly one HumanMessage means this is the first turn ──
    human_messages = [m for m in state.messages if isinstance(m, HumanMessage)]
    is_new_thread = len(human_messages) == 1

    # ── Extract equipment model from message history if not already in state ──
    if not equipment_model:
        pattern = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"   # generic slug pattern
        for msg in reversed(state.messages):
            if isinstance(msg, HumanMessage):
                match = re.search(pattern, _text(msg.content), re.IGNORECASE)
                if match:
                    equipment_model = match.group(0).lower()
                    break

    if not equipment_model:
        return {
            "messages": [AIMessage(content=(
                "**[1. Initialization]**\n\n"
                "⚠️ No equipment model detected in your message. "
                "Please mention the model ID (e.g. `cctv-psu-24w-v1`) to begin diagnosis."
            ))]
        }

    # ── Load equipment config from local YAML (fast, no API calls) ─────────────
    # ── and get cached RAG knowledge ──────────────────────────────────────────
    from src.infrastructure.equipment_config import get_equipment_config

    # Get RAG knowledge (cached per equipment model)
    rag_knowledge = _get_cached_rag_knowledge(equipment_model)

    # Load equipment config directly from YAML - much faster than API call
    try:
        config = get_equipment_config(equipment_model)
        
        # Build config_result dict from local YAML data
        config_result = {
            "test_points": [],
            "thresholds": {},
            "faults": [],
            "signals": []
        }
        
        # Get signals from config (signals is a Dict[str, SignalConfig])
        if config.signals:
            config_result["signals"] = [
                {
                    "signal_id": sig.signal_id,
                    "name": sig.name,
                    "test_point": sig.test_point,
                    "parameter": sig.parameter,
                    "unit": sig.unit,
                    "physical_description": sig.physical_description or "",
                    "image_url": sig.image_url or "",
                    "pro_tips": sig.pro_tips or []
                }
                for sig in config.signals.values()
            ]
            config_result["test_points"] = config_result["signals"]
        
        # Get thresholds from config (thresholds is a Dict[str, ThresholdConfig])
        if config.thresholds:
            for signal_id, threshold_data in config.thresholds.items():
                states = {}
                for state_name, state in threshold_data.states.items():
                    states[state_name] = {
                        "min": state.min_value,
                        "max": state.max_value,
                        "description": state.description
                    }
                config_result["thresholds"][signal_id] = {
                    "signal_id": threshold_data.signal_id,
                    "states": states
                }
        
        # Get faults from config (faults is a Dict[str, FaultConfig])
        if config.faults:
            config_result["faults"] = [
                {
                    "fault_id": f.fault_id,
                    "name": f.name,
                    "description": f.description,
                    "priority": f.priority,
                    "signatures": f.signatures,
                    "hypotheses": [
                        {
                            "rank": h.rank,
                            "component": h.component,
                            "failure_mode": h.failure_mode,
                            "cause": h.cause,
                            "confidence": h.confidence
                        }
                        for h in f.hypotheses
                    ],
                    "recovery": [
                        {
                            "step": r.step,
                            "action": r.action,
                            "target": r.target,
                            "instruction": r.instruction,
                            "verification": r.verification,
                            "safety": r.safety,
                            "estimated_time": r.estimated_time,
                            "difficulty": r.difficulty
                        }
                        for r in f.recovery
                    ]
                }
                for f in config.faults.values()
            ]
        
    except FileNotFoundError as e:
        config_result = {"error": str(e), "test_points": [], "thresholds": {}, "faults": [], "signals": []}
    except Exception as e:
        config_result = {"error": str(e), "test_points": [], "thresholds": {}, "faults": [], "signals": []}

    full_signals = config_result.get("signals", [])

    # ── Step 4: Build expected_values with correct per-signal units ───────────
    # Signal units from the rich signal list
    signal_units: dict[str, str] = {
        s.get("signal_id", ""): s.get("unit", "V")
        for s in full_signals
    }

    thresholds: dict = config_result.get("thresholds", {})
    expected_values: dict = {}
    for signal_id, threshold_data in thresholds.items():
        states = threshold_data.get("states", {})
        if "normal" in states:
            normal = states["normal"]
            expected_values[signal_id] = {
                "min": normal.get("min", 0),
                "max": normal.get("max", 999_999),
                "unit": signal_units.get(signal_id, "V"),
                "description": normal.get("description", "")
            }

    # ── Step 5: Extract lists ─────────────────────────────────────────────────
    # test_points: basic list for LLM prompts (signal_id, name, parameter)
    test_points = config_result.get("test_points", [])
    faults = config_result.get("faults", [])

    # ── Step 6: Build init message ────────────────────────────────────────────
    rag_sources = []
    for r in rag_knowledge[:3]:
        if isinstance(r, dict) and r.get("title"):
            rag_sources.append(r["title"])

    greeting = (
        "Hello Engineer, I am DIAG. I'll guide you through a systematic diagnostic process.\n\n"
        if is_new_thread else ""
    )

    rag_line = (
        f"\n*Knowledge sources: {', '.join(rag_sources)}*" if rag_sources else ""
    )

    init_msg = (
        f"**[1. Initialization]**\n\n"
        f"{greeting}"
        f"Equipment **{equipment_model}** loaded -- "
        f"**{len(test_points)}** test points · **{len(faults)}** fault definitions."
        f"{rag_line}"
    )

    return {
        "equipment_model": equipment_model,
        "rag_knowledge": rag_knowledge,
        "equipment_config": config_result,
        "test_points": test_points,
        "expected_values": expected_values,
        "suspected_faults": faults,
        "config_cached": True,
        "messages": [AIMessage(content=init_msg)]
    }


# =============================================================================
# NODE: HYPOTHESES -- rank fault candidates from symptom
# =============================================================================

def hypotheses_node(state: ConversationalAgentState):
    """
    Single LLM call that produces BOTH the ranked fault hypotheses AND the
    ordered test-point list.  Two-in-one to avoid the double-LLM latency
    that was causing 90–180 s delays.
    """
    from src.infrastructure.llm_manager import invoke_with_retry

    equipment_model = state.equipment_model
    test_points    = state.test_points
    rag_knowledge  = state.rag_knowledge
    faults         = state.suspected_faults

    # ── Collect symptom from all human messages ───────────────────────────────
    symptom = " ".join(
        _text(m.content)
        for m in state.messages
        if isinstance(m, HumanMessage)
    ).strip()

    # ── Format context strings for the prompt ────────────────────────────────
    tp_str = "\n".join(
        f"- {tp.get('signal_id','?')}: {tp.get('name','')} ({tp.get('parameter','')})"
        for tp in test_points[:15]
    ) or "No test points defined"

    faults_str = "\n".join(
        f"- {f.get('fault_id','')}: {f.get('name','')} -- {f.get('description','')[:150]}"
        for f in faults[:10]
    ) or "No fault definitions available"

    rag_str = "\n".join(
        f"- {k.get('content','')[:200]}"
        for k in rag_knowledge[:3]
        if isinstance(k, dict)
    ) or "No diagnostic knowledge available"

    # ── Combined prompt: one call, one JSON response ──────────────────────────
    prompt = f"""You are a diagnostic expert. Analyse the symptom and produce a JSON response.

EQUIPMENT: {equipment_model}
SYMPTOM: {symptom}

AVAILABLE TEST POINTS:
{tp_str}

KNOWN FAULTS:
{faults_str}

DIAGNOSTIC KNOWLEDGE:
{rag_str}

TASK:
1. Generate 3–5 fault hypotheses ranked by probability.
2. Rank ALL available test points by diagnostic value for distinguishing these hypotheses.

Rules:
- Each hypothesis: unique id (HYPOTHESIS_1 …), fault_id if applicable, description, probability 0.0–1.0
- Probabilities must sum to 1.0
- For a dead/low output with AC input confirmed, always put DC-bus measurement first in rankings
- Use signal_id values EXACTLY as listed above

Output ONLY a valid JSON object, nothing else:
{{
  "hypotheses": [
    {{"id": "HYPOTHESIS_1", "fault_id": "F001", "description": "...", "probability": 0.5}},
    ...
  ],
  "test_point_rankings": ["signal_id_1", "signal_id_2", ...]
}}"""

    # ── LLM call ──────────────────────────────────────────────────────────────
    hypotheses: list = []
    hypothesis_probabilities: dict = {}
    test_point_rankings: list = []

    try:
        response = invoke_with_retry([{"role": "user", "content": prompt}])
        content = response.content if response else "{}"

        start = content.find('{')
        end   = content.rfind('}')
        if start != -1 and end > start:
            data = json.loads(content[start:end + 1])
            hypotheses = data.get("hypotheses", [])
            for h in hypotheses:
                hypothesis_probabilities[h.get("id", "")] = float(h.get("probability", 0.1))
            test_point_rankings = data.get("test_point_rankings", [])
    except Exception:
        # Fallback: uniform probability across known faults
        for i, fault in enumerate(faults[:5]):
            h = {
                "id": f"HYPOTHESIS_{i + 1}",
                "fault_id": fault.get("fault_id", ""),
                "description": fault.get("description", fault.get("name", ""))[:120],
                "probability": 1.0 / max(min(len(faults), 5), 1)
            }
            hypotheses.append(h)
            hypothesis_probabilities[h["id"]] = h["probability"]

    # ── Sanitise output ───────────────────────────────────────────────────────
    hypotheses = [h for h in hypotheses if h.get("id")]

    # Normalise probabilities
    total = sum(hypothesis_probabilities.values())
    if total > 0:
        hypothesis_probabilities = {k: v / total for k, v in hypothesis_probabilities.items()}

    # Filter rankings to valid signal_ids
    valid_ids = {tp.get("signal_id", "") for tp in test_points}
    test_point_rankings = [s for s in test_point_rankings if s and s in valid_ids]
    if not test_point_rankings:
        test_point_rankings = [tp.get("signal_id", "") for tp in test_points if tp.get("signal_id")]

    # Set highest-probability hypothesis as current
    current_hypothesis = ""
    if hypotheses:
        current_hypothesis = max(
            hypotheses,
            key=lambda h: hypothesis_probabilities.get(h["id"], 0)
        ).get("id", "")

    diagnostic_plan = test_point_rankings[:state.max_steps]

    # ── Build assessment message ───────────────────────────────────────────────
    sorted_h = sorted(
        hypotheses,
        key=lambda h: hypothesis_probabilities.get(h["id"], 0),
        reverse=True
    )

    lines = [
        "**[3. Preliminary Assessment]**\n",
        f"Symptom: *{symptom}*\n",
        "**Fault candidates by probability:**\n"
    ]
    for h in sorted_h:
        prob = hypothesis_probabilities.get(h["id"], 0)
        lines.append(f"- **{h.get('description', h['id'])}** -- {prob:.0%}")

    lines.append(
        "\n---\n"
        "_Test sequence calculated. "
        f"Starting with {len(test_point_rankings)} measurements -- "
        "showing first probe placement now..._"
    )

    return {
        "hypotheses": hypotheses,
        "hypothesis_probabilities": hypothesis_probabilities,
        "eliminated_faults": [],
        "current_hypothesis": current_hypothesis,
        "test_point_rankings": test_point_rankings,
        "diagnostic_reasoning": [f"Initial hypotheses: {len(hypotheses)} candidates"],
        "diagnostic_plan": diagnostic_plan,
        "current_step": 0,
        "messages": [AIMessage(content="\n".join(lines))]
    }


# =============================================================================
# NODE: STEP -- take the measurement, report the result
# =============================================================================

def step_node(state: ConversationalAgentState):
    """
    Execute one atomic measurement step.

    The interrupt that ran BEFORE this node already showed the engineer where
    to place their probes.  This node's only job is:
      1. Read the multimeter (15 s timeout max).
      2. Evaluate result against expected range.
      3. Emit a concise measurement-result message.
    """
    from src.studio.tools import read_multimeter

    # ── Guard: no more test points ────────────────────────────────────────────
    if state.current_step >= len(state.test_point_rankings):
        return {
            "step_result": {"decision": "no_more_tests", "reasoning": "No remaining test points"},
            "messages": [AIMessage(content="No remaining test points. Proceeding to analysis...")]
        }

    test_point_id = state.test_point_rankings[state.current_step]

    # ── Resolve signal definition ─────────────────────────────────────────────
    signal_def: dict = {}
    for sig in state.equipment_config.get("signals", []):
        if sig.get("signal_id") == test_point_id:
            signal_def = sig
            break

    signal_name      = signal_def.get("name", test_point_id)
    measurement_type = signal_def.get("parameter", "voltage_dc")

    # ── Expected range ────────────────────────────────────────────────────────
    expected = state.expected_values.get(test_point_id, {"min": 0, "max": 999_999, "unit": "V"})

    # ── Current hypothesis context ────────────────────────────────────────────
    hyp_desc = next(
        (h.get("description", "") for h in state.hypotheses
         if h.get("id") == state.current_hypothesis),
        ""
    )

    # ── Take measurement (180 s max window for engineer to place probes) ────
    try:
        result = read_multimeter.invoke({
            "equipment_model": state.equipment_model,
            "test_point": test_point_id,
            "measurement_type": measurement_type,
            "max_duration": 180.0
        })
    except Exception as e:
        result = {"status": "error", "error": str(e), "test_point": test_point_id, "value": None}

    meas_value  = result.get("value", None)
    meas_unit   = result.get("unit", expected.get("unit", "V"))
    status      = result.get("status", "unknown")

    # ── Build unit label that includes AC/DC qualifier ─────────────────────────
    meas_type_display = {
        "DC_VOLTAGE":  "V DC",
        "AC_VOLTAGE":  "V AC",
        "DC_CURRENT":  "A DC",
        "AC_CURRENT":  "A AC",
        "RESISTANCE":  "Ω",
        "CONTINUITY":  "Ω",
        "FREQUENCY":   "Hz",
    }.get((result.get("measurement_type") or measurement_type or "").upper(), meas_unit)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    evaluation = "normal"
    if status == "success" and meas_value is not None:
        min_v, max_v = expected.get("min", 0), expected.get("max", 999_999)
        if not (min_v <= meas_value <= max_v):
            evaluation = "fault"
    elif status in ("timeout", "error", "timeout_unstable"):
        evaluation = "measurement_unavailable"

    # ── Format parameter label ────────────────────────────────────────────────
    param_label = ""
    if measurement_type:
        param_label = f" ({measurement_type.replace('_', ' ').title()})"

    # ── Build result message ──────────────────────────────────────────────────
    step_num  = state.current_step + 1
    total_num = len(state.test_point_rankings)

    parts = [f"**[4. Measurement {step_num}/{total_num}]**\n"]

    if hyp_desc:
        parts.append(f"*Testing: {hyp_desc}*\n")

    if evaluation == "fault":
        parts.append(f"### ⚠️ FAULT -- {signal_name}")
        parts.append(f"**Measured:** {meas_value} {meas_type_display}")
        parts.append(f"**Expected:** {expected['min']} -- {expected['max']} {meas_type_display}")
        diag = signal_def.get("diagnostic_meaning", "")
        if diag:
            parts.append(f"**Implication:** {diag}")

    elif evaluation == "measurement_unavailable":
        parts.append(f"### ⚠️ READING UNAVAILABLE -- {signal_name}")
        if meas_value is not None:
            parts.append(f"**Best-effort reading:** {meas_value} {meas_type_display}")
        parts.append(f"**Expected:** {expected['min']} -- {expected['max']} {meas_type_display}")
        reason = result.get("message", "Could not obtain a stable reading.")
        parts.append(f"**Reason:** {reason}")
        parts.append(
            "_Check probe contact and hold steady. "
            "You can also enter a manual reading using the `enter_manual_reading` tool._"
        )

    else:  # normal
        parts.append(f"### ✓ NORMAL -- {signal_name}")
        parts.append(f"**Measured:** {meas_value} {meas_type_display}")
        parts.append(f"**Expected:** {expected['min']} -- {expected['max']} {meas_type_display}")
        diag = signal_def.get("diagnostic_meaning", "")
        if diag:
            parts.append(f"**Implication:** {diag}")

    parts.append("\n*Updating hypothesis probabilities...*")

    # ── Measurement record ────────────────────────────────────────────────────
    record = {
        "test_point":  test_point_id,
        "signal_name": signal_name,
        "value":       meas_value,
        "unit":        meas_unit,
        "status":      status,
        "evaluation":  evaluation,
        "expected_min": expected.get("min", 0),
        "expected_max": expected.get("max", 999_999),
        "hypothesis_being_tested": state.current_hypothesis,
        "timestamp": str(datetime.now())
    }

    next_tp = (
        state.test_point_rankings[state.current_step + 1]
        if state.current_step + 1 < len(state.test_point_rankings)
        else None
    )

    return {
        "current_test_point": test_point_id,
        "step_result": {
            "measurement": record,
            "evaluation": evaluation,
            "reasoning": "",
            "decision": "pending_reasoning",
            "next_test_point": next_tp
        },
        "measurements":     state.measurements + [record],
        "next_test_point":  next_tp or "",
        "messages":         [AIMessage(content="\n".join(parts))],
        "iteration_count":  state.iteration_count + 1
    }


# =============================================================================
# NODE: REASON -- update hypothesis probabilities
# =============================================================================

def reason_node(state: ConversationalAgentState):
    """
    Update hypothesis probabilities from the latest measurement.
    Also increments current_step so interrupt_node targets the next test point.
    """
    from src.infrastructure.llm_manager import invoke_with_retry

    if not state.measurements:
        return {
            "step_result": {"decision": "error", "reasoning": "No measurements recorded yet"},
            "current_step": state.current_step + 1
        }

    last = state.measurements[-1]
    tp_id        = last.get("test_point", "")
    meas_value   = last.get("value", 0)
    meas_unit    = last.get("unit", "V")
    evaluation   = last.get("evaluation", "normal")
    signal_name  = last.get("signal_name", tp_id)

    # ── Skip update for unavailable readings ──────────────────────────────────
    if evaluation == "measurement_unavailable":
        return {
            "step_result": {
                "measurement": last,
                "evaluation":  evaluation,
                "reasoning":   "Measurement unavailable -- hypothesis probabilities unchanged.",
                "decision":    "continue_diagnosis",
                "next_test_point": (
                    state.test_point_rankings[state.current_step + 1]
                    if state.current_step + 1 < len(state.test_point_rankings)
                    else None
                )
            },
            "messages": [AIMessage(content=(
                "**[5. Results Analysis]**\n\n"
                f"⚠️ No reliable reading at **{signal_name}** -- "
                "hypothesis probabilities unchanged. Continuing to next test point."
            ))],
            "current_step": state.current_step + 1
        }

    expected = state.expected_values.get(tp_id, {"min": 0, "max": 999_999, "unit": "V"})

    hyp_lines = "\n".join(
        f"- {h.get('id','')}: {h.get('description','')} "
        f"(P={state.hypothesis_probabilities.get(h.get('id'), 0):.2f})"
        for h in state.hypotheses
    )

    prompt = f"""Update hypothesis probabilities based on this measurement.

TEST POINT: {tp_id} ({signal_name})
MEASURED:   {meas_value} {meas_unit}
EXPECTED:   {expected.get('min',0)} – {expected.get('max',999_999)} {meas_unit}
RESULT:     {evaluation.upper()}

HYPOTHESES:
{hyp_lines}

Rules:
- A FAULT result supports hypotheses that predict failure at this point; contradicts those that do not
- A NORMAL result contradicts hypotheses that require this point to be faulty
- Set probability to 0 only when a hypothesis is definitively disproved
- A hypothesis is CONFIRMED when its probability exceeds 0.90 and no other active hypothesis is plausible
- Probabilities of non-eliminated hypotheses must sum to 1.0

Return ONLY valid JSON:
{{
  "reasoning": "one-sentence explanation",
  "probability_updates": {{"HYPOTHESIS_1": 0.8, "HYPOTHESIS_2": 0.0, ...}},
  "eliminated_faults": ["HYPOTHESIS_2"],
  "confirmed_hypothesis": "HYPOTHESIS_1" or null
}}"""

    # ── LLM call ──────────────────────────────────────────────────────────────
    reasoning            = ""
    eliminated           = list(state.eliminated_faults)
    updated_probs        = dict(state.hypothesis_probabilities)
    confirmed_hypothesis = None

    try:
        response = invoke_with_retry([{"role": "user", "content": prompt}])
        content  = response.content if response else "{}"
        start    = content.find('{')
        end      = content.rfind('}')
        if start != -1 and end > start:
            data = json.loads(content[start:end + 1])
            reasoning = data.get("reasoning", "")
            for h_id, prob in data.get("probability_updates", {}).items():
                if h_id in updated_probs:
                    updated_probs[h_id] = float(prob)
            for e in data.get("eliminated_faults", []):
                if e not in eliminated:
                    eliminated.append(e)
            confirmed_hypothesis = data.get("confirmed_hypothesis") or None
    except Exception:
        reasoning = "Analysis inconclusive -- carrying forward current probabilities."

    # ── Normalise active probabilities ────────────────────────────────────────
    active = {h: p for h, p in updated_probs.items() if h not in eliminated}
    total  = sum(active.values())
    if total > 0:
        for h in active:
            updated_probs[h] = active[h] / total

    # ── Select current hypothesis ─────────────────────────────────────────────
    new_current = state.current_hypothesis
    if confirmed_hypothesis:
        new_current = confirmed_hypothesis
    elif not new_current or new_current in eliminated:
        best, best_p = "", -1.0
        for h in state.hypotheses:
            h_id = h.get("id", "")
            if h_id not in eliminated:
                p = updated_probs.get(h_id, 0)
                if p > best_p:
                    best_p, best = p, h_id
        new_current = best

    # ── Routing decision ──────────────────────────────────────────────────────
    active_remaining = [h for h in state.hypotheses if h.get("id") not in eliminated]
    if confirmed_hypothesis:
        decision = "fault_confirmed"
    elif not active_remaining:
        decision = "all_eliminated"
    else:
        decision = "continue_diagnosis"

    # ── Build analysis message ────────────────────────────────────────────────
    parts = ["**[5. Results Analysis]**\n"]

    if reasoning:
        parts.append(f"{reasoning}\n")

    parts.append("**Fault candidate status:**")
    sorted_h = sorted(
        state.hypotheses,
        key=lambda h: updated_probs.get(h.get("id",""), 0),
        reverse=True
    )
    for h in sorted_h:
        h_id = h.get("id", "")
        desc = h.get("description", h_id)
        if h_id in eliminated:
            parts.append(f"- ~~{desc}~~ -- eliminated")
        else:
            p      = updated_probs.get(h_id, 0)
            marker = " ← **most likely**" if h_id == new_current else ""
            parts.append(f"- {desc}: **{p:.0%}**{marker}")

    # ── Update reasoning chain ────────────────────────────────────────────────
    reasoning_chain = list(state.diagnostic_reasoning)
    reasoning_chain.append(
        f"Step {state.current_step + 1}: {tp_id} = {meas_value} {meas_unit} "
        f"({evaluation}). {reasoning[:80] if reasoning else ''}"
    )

    next_tp = (
        state.test_point_rankings[state.current_step + 1]
        if state.current_step + 1 < len(state.test_point_rankings)
        else None
    )

    return {
        "hypothesis_probabilities": updated_probs,
        "eliminated_faults":        eliminated,
        "current_hypothesis":       new_current,
        "diagnostic_reasoning":     reasoning_chain,
        "step_result": {
            "measurement":    last,
            "evaluation":     evaluation,
            "reasoning":      reasoning,
            "decision":       decision,
            "next_test_point": next_tp
        },
        "messages":     [AIMessage(content="\n".join(parts))],
        "current_step": state.current_step + 1
    }


# =============================================================================
# NODE: DECISION -- deterministic routing
# =============================================================================

def decision_node(state: ConversationalAgentState):
    """
    Evaluate termination conditions in order and set state.next_node.

    1. confirmed_fault already set → repair
    2. step_result.decision == "fault_confirmed" → repair
    3. All hypotheses eliminated → END (inconclusive)
    4. current_step ≥ max_steps → END (max reached)
    5. current_step ≥ len(rankings) → END (no more tests)
    6. Otherwise → interrupt (continue loop)
    """
    if state.confirmed_fault:
        return {"next_node": "repair"}

    decision = state.step_result.get("decision", "continue_diagnosis")

    if decision == "fault_confirmed":
        return {"next_node": "repair"}

    active = [h for h in state.hypotheses if h.get("id") not in state.eliminated_faults]
    if not active:
        return {
            "next_node": "end",
            "diagnosis_status": "inconclusive",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=(
                "## Diagnosis Complete -- Inconclusive\n\n"
                "All fault hypotheses have been eliminated by measurements. "
                "The fault may lie outside the modelled failure modes. "
                "Consider a visual inspection or component-level tests."
            ))]
        }

    if state.current_step >= state.max_steps:
        return {
            "next_node": "end",
            "diagnosis_status": "max_steps_reached",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=(
                f"## Diagnosis Complete -- Step Limit Reached\n\n"
                f"Completed {state.max_steps} diagnostic steps without a conclusive result. "
                f"Most likely candidate: **{_top_hypothesis_desc(state)}**."
            ))]
        }

    if state.current_step >= len(state.test_point_rankings):
        return {
            "next_node": "end",
            "diagnosis_status": "no_more_tests",
            "diagnosis_complete": True,
            "messages": [AIMessage(content=(
                "## Diagnosis Complete -- All Tests Exhausted\n\n"
                "No further test points available. "
                f"Most likely candidate: **{_top_hypothesis_desc(state)}**."
            ))]
        }

    return {"next_node": "interrupt"}


def _top_hypothesis_desc(state: ConversationalAgentState) -> str:
    """Return the description of the highest-probability non-eliminated hypothesis."""
    best_desc, best_prob = "Unknown", -1.0
    for h in state.hypotheses:
        h_id = h.get("id", "")
        if h_id not in state.eliminated_faults:
            p = state.hypothesis_probabilities.get(h_id, 0)
            if p > best_prob:
                best_prob, best_desc = p, h.get("description", h_id)
    return best_desc


# =============================================================================
# NODE: REPAIR -- emit repair procedure
# =============================================================================

def repair_node(state: ConversationalAgentState):
    """
    Identify the confirmed (root-cause) fault, scan measurements for secondary
    damage caused by the root fault, then emit a single combined repair plan.

    Secondary damage rule: any measurement marked 'fault' that is NOT the
    confirming measurement may indicate collateral damage (e.g. a blown fuse
    caused by a shorted MOSFET).  We include those fault records in the repair
    plan after the root-cause steps.
    """
    from src.infrastructure.llm_manager import invoke_with_retry

    faults             = state.suspected_faults
    current_hypothesis = state.current_hypothesis

    # ── Find fault_id for root-cause hypothesis ───────────────────────────────
    fault_id = ""
    for h in state.hypotheses:
        if h.get("id") == current_hypothesis:
            fault_id = h.get("fault_id", "")
            break

    last_meas = state.measurements[-1] if state.measurements else {}
    last_tp   = last_meas.get("test_point", "?")
    last_val  = last_meas.get("value", "?")
    last_unit = last_meas.get("unit", "")

    # ── Find root-cause fault record ──────────────────────────────────────────
    fault_record: dict = {}
    if fault_id:
        fault_record = next(
            (f for f in faults if f.get("fault_id") == fault_id),
            {}
        )

    # ── If no direct match, ask LLM to match measurement → fault ─────────────
    if not fault_record and faults:
        faults_summary = "\n".join(
            f"- {f.get('fault_id','')}: {f.get('name','')}"
            for f in faults[:8]
        )
        try:
            response = invoke_with_retry([{"role": "user", "content": (
                f"Measurement: {last_tp} = {last_val} {last_unit}\n"
                f"Faults:\n{faults_summary}\n"
                "Reply with ONLY the fault_id that best matches, nothing else."
            )}])
            matched_id = (response.content or "").strip()
            fault_record = next(
                (f for f in faults if f.get("fault_id") == matched_id),
                {}
            )
        except Exception:
            pass

    fault_name = fault_record.get("name", "Unspecified Fault")

    # ── Detect secondary damage ───────────────────────────────────────────────
    # Any prior measurement that evaluated as 'fault' (but is not the confirming
    # measurement) is a candidate for collateral damage.
    secondary_fault_records: list[dict] = []
    seen_fault_ids: set[str] = {fault_id}

    for m in state.measurements[:-1]:   # exclude last (confirming) measurement
        if m.get("evaluation") != "fault":
            continue
        m_tp = m.get("test_point", "")
        # Ask LLM to map this abnormal measurement to a fault_id
        if faults:
            faults_summary = "\n".join(
                f"- {f.get('fault_id','')}: {f.get('name','')}"
                for f in faults[:8]
            )
            try:
                response = invoke_with_retry([{"role": "user", "content": (
                    f"Measurement: {m_tp} = {m.get('value','?')} {m.get('unit','')}\n"
                    f"Faults:\n{faults_summary}\n"
                    "Reply with ONLY the fault_id that best matches, or NONE if none fits."
                )}])
                sec_id = (response.content or "").strip()
                if sec_id and sec_id != "NONE" and sec_id not in seen_fault_ids:
                    sec_record = next(
                        (f for f in faults if f.get("fault_id") == sec_id), {}
                    )
                    if sec_record:
                        secondary_fault_records.append(sec_record)
                        seen_fault_ids.add(sec_id)
            except Exception:
                pass

    # ── Build repair steps ────────────────────────────────────────────────────
    def _format_recovery(record: dict, label_prefix: str = "") -> list[str]:
        lines: list[str] = []
        for r in record.get("recovery", []):
            step_label   = r.get("action", f"Step {r.get('step', '')}") or f"Step {r.get('step', '')}"
            instruction  = r.get("instruction", "")
            verification = r.get("verification", "")
            safety       = r.get("safety", "")
            est_time     = r.get("estimated_time", "")
            lines.append(f"**{label_prefix}{step_label}**")
            lines.append(f"> {instruction}")
            if safety:
                lines.append(f"  ⚠️ *Safety: {safety}*")
            if verification:
                lines.append(f"  ✓ *Verify: {verification}*")
            if est_time:
                lines.append(f"  ⏱ *Estimated: {est_time}*")
            lines.append("")
        return lines

    repair_lines: list[str] = []

    if fault_record.get("recovery"):
        repair_lines += _format_recovery(fault_record)
    else:
        repair_lines.append("_No repair procedure found in config for root cause. Consult service manual._")

    if secondary_fault_records:
        repair_lines.append("---")
        repair_lines.append("### 🔗 Secondary / Collateral Damage\n")
        repair_lines.append(
            "_The root cause likely caused the following additional failures. "
            "Repair these AFTER fixing the root cause:_\n"
        )
        for sec in secondary_fault_records:
            repair_lines.append(f"**{sec.get('name', 'Unknown')}**")
            if sec.get("recovery"):
                repair_lines += _format_recovery(sec, label_prefix="  ")
            else:
                repair_lines.append("  _Consult service manual for this component._")
                repair_lines.append("")

    repair_block = "\n".join(repair_lines) if repair_lines else "_No repair procedure available._"

    # ── Evidence summary ──────────────────────────────────────────────────────
    evidence_rows = []
    for m in state.measurements:
        icon = {"fault": "⚠️", "normal": "✓", "measurement_unavailable": "–"}.get(
            m.get("evaluation", ""), "?"
        )
        val  = m.get("value", "?")
        unit = m.get("unit", "")
        ev   = m.get("evaluation", "").replace("_", " ").title()
        evidence_rows.append(
            f"| {m.get('signal_name', m.get('test_point','?'))} "
            f"| {val} {unit} | {icon} {ev} |"
        )

    evidence_table = (
        "| Test Point | Reading | Result |\n"
        "|------------|---------|--------|\n"
        + "\n".join(evidence_rows)
        if evidence_rows else "_No measurements recorded._"
    )

    # ── Dynamic post-repair verification ─────────────────────────────────────
    output_signal = None
    for sig in state.equipment_config.get("signals", []):
        sid   = sig.get("signal_id", "").lower()
        name  = sig.get("name", "").lower()
        param = sig.get("parameter", "").lower()
        if ("output" in sid or "output" in name) and "voltage" in param:
            output_signal = sig
            break

    if output_signal:
        osid    = output_signal.get("signal_id", "")
        oname   = output_signal.get("name", "output")
        oexpect = state.expected_values.get(osid, {})
        verify_msg = (
            f"**Post-repair verification:** Measure **{oname}**. "
            f"Expected: {oexpect['min']}–{oexpect['max']} {oexpect.get('unit','V')} DC."
            if oexpect else
            f"**Post-repair verification:** Confirm **{oname}** is within normal operating range."
        )
    else:
        verify_msg = (
            "**Post-repair verification:** Confirm all output voltages are within specified range."
        )

    # ── Hypothesis mechanism ──────────────────────────────────────────────────
    hyp_mechanism = next(
        (h.get("description", "") for h in state.hypotheses if h.get("id") == current_hypothesis),
        ""
    )

    # ── Final message ─────────────────────────────────────────────────────────
    sec_names = ", ".join(s.get("name", "?") for s in secondary_fault_records)
    sec_line  = f"\n**Secondary damage detected:** {sec_names}" if secondary_fault_records else ""

    msg_parts = [
        "**[6. Repair Procedure]**\n",
        "## ✅ Diagnosis Complete -- Fault Confirmed\n",
        f"**Root Cause:** {fault_name}",
    ]
    if hyp_mechanism:
        msg_parts.append(f"**Mechanism:** {hyp_mechanism}")
    msg_parts.append(f"**Confirmed by:** {last_tp} = {last_val} {last_unit}{sec_line}\n")
    msg_parts.append("### Evidence Summary\n")
    msg_parts.append(evidence_table)
    msg_parts.append(f"\n### Repair Steps -- *{fault_name}*")
    if secondary_fault_records:
        sec_list = ", ".join(s.get("name","?") for s in secondary_fault_records)
        msg_parts.append(f"_Includes secondary damage: {sec_list}_")
    msg_parts.append(f"_Source: {state.equipment_model}-diagnostics_\n")
    msg_parts.append(repair_block)
    msg_parts.append("---")
    msg_parts.append(verify_msg)

    return {
        "confirmed_fault":    fault_name,
        "diagnosis_complete": True,
        "messages":           [AIMessage(content="\n".join(msg_parts))]
    }


# =============================================================================
# NODE: INSTRUCTION -- show probe placement for current test point (NO pause)
# =============================================================================

def instruction_node(state: ConversationalAgentState):
    """
    Emit the probe-placement instructions for the CURRENT test point as a
    plain AIMessage.  Does NOT call interrupt() -- execution continues
    immediately into step_node.

    state.current_step already points at the test to perform (set to 0 by
    hypotheses_node on the first pass; incremented by reason_node on every
    subsequent pass).
    """
    total_steps = len(state.test_point_rankings)

    # ── Resolve test point ────────────────────────────────────────────────────
    current_signal_id = ""
    if state.current_step < len(state.test_point_rankings):
        current_signal_id = state.test_point_rankings[state.current_step]

    current_signal: dict = {}
    if current_signal_id:
        for sig in state.equipment_config.get("signals", []):
            if sig.get("signal_id") == current_signal_id:
                current_signal = sig
                break

    # ── Build instruction markdown ────────────────────────────────────────────
    parts: list[str] = []

    if current_signal:
        step_num    = state.current_step + 1
        signal_name = current_signal.get("name", current_signal_id)

        parts.append(f"## 🔬 Measurement {step_num} of {total_steps} -- {signal_name}")

        # Image first
        image_url = current_signal.get("image_url", "")
        if image_url:
            parts.append(f"![{signal_name}]({image_url})")

        # Physical location
        phys = current_signal.get("physical_description", "")
        if phys:
            parts.append(f"**📍 Where to find it:**\n{phys}")
            parts.append(f"_Ref: {state.equipment_model}.yaml_")

        # Pro tips
        tips = current_signal.get("pro_tips", [])
        if tips:
            tip_lines = "\n".join(f"- {t}" for t in tips)
            parts.append(f"**💡 Pro tips:**\n{tip_lines}")

        # Expected reading
        exp = state.expected_values.get(current_signal_id, {})
        if exp:
            parts.append(
                f"**Expected reading:** {exp['min']} – {exp['max']} {exp.get('unit','V')}"
            )

        # Current hypothesis context
        hyp_desc = next(
            (h.get("description", "") for h in state.hypotheses
             if h.get("id") == state.current_hypothesis),
            ""
        )
        if hyp_desc:
            parts.append(f"*Testing hypothesis: {hyp_desc}*")

        parts.append("\n_Place probes at the test point above, then press **Resume** when ready to measure._")

    else:
        parts.append("## All measurements complete -- proceeding to analysis.")

    return {"messages": [AIMessage(content="\n\n".join(parts))]}


# =============================================================================
# NODE: PROBE_WAIT -- pause AFTER probe instructions; BEFORE measurement fires
# =============================================================================

def probe_wait_node(state: ConversationalAgentState) -> dict:
    """
    Pause after probe placement instructions are shown so the engineer can
    read the instructions and place the probes before the measurement starts.

    instruction_node already emitted all the probe details and the image.
    This node calls interrupt() so LangGraph Studio renders that message and
    shows the Resume button.  When the engineer presses Resume, probe_wait_node
    returns {} and step_node fires immediately on the already-placed probes.
    """
    interrupt("probes_ready")
    return {}


# =============================================================================
# NODE: INTERRUPT -- pause ONLY; no probe info (fires after full step cycle)
# =============================================================================

def interrupt_node(state: ConversationalAgentState):
    """
    Pause execution after a complete measurement cycle so the engineer can
    review the result before continuing.

    The probe instructions for the NEXT test point will be shown by
    instruction_node after the engineer presses resume -- not here.
    """
    interrupt(
        "**Measurement cycle complete.**\n\n"
        "Review the result above, then type anything and press **Enter** "
        "to continue to the next test point."
    )
    return {"waiting_for_next": True}


# =============================================================================
# NODE: RESUME -- clear waiting flag
# =============================================================================

def resume_node(state: ConversationalAgentState):
    """
    Clear the waiting flag.  current_step is NOT changed here -- it was
    already incremented by reason_node.  step_node reads current_step
    as-is and measures test_point_rankings[current_step].
    """
    return {"waiting_for_next": False}


# =============================================================================
# CONDITIONAL EDGES
# =============================================================================

def route_from_decision(state: ConversationalAgentState) -> str:
    next_node = state.next_node or "interrupt"
    if next_node == "repair":
        return "repair"
    if next_node == "end":
        return "end"
    return "interrupt"


def route_from_resume(state: ConversationalAgentState) -> str:
    """Route after resume: go to instruction (which leads to step) or end."""
    if state.current_step >= state.max_steps:
        return "end"
    if state.current_step >= len(state.test_point_rankings):
        return "end"
    return "instruction"


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_conversational_graph():
    """
    Build and compile the hypothesis-driven diagnostic workflow.

    Flow:
      START → rag → hypotheses → instruction → step → reason → decision
                                      ↑                              |
                                      ←────── resume ← interrupt ────┘  (if no fault)
      decision → repair → END
      decision → END  (inconclusive / max steps / exhausted)
    """
    builder = StateGraph(ConversationalAgentState)

    builder.add_node("rag",         rag_node)
    builder.add_node("hypotheses",  hypotheses_node)
    builder.add_node("instruction", instruction_node)
    builder.add_node("step",        step_node)
    builder.add_node("reason",      reason_node)
    builder.add_node("decision",    decision_node)
    builder.add_node("repair",      repair_node)
    builder.add_node("interrupt",   interrupt_node)
    builder.add_node("resume",      resume_node)
    builder.add_node("probe_wait",  probe_wait_node)

    builder.add_edge(START,        "rag")
    builder.add_edge("rag",        "hypotheses")

    # After hypotheses: instruction shows probe placement, then pause for engineer
    builder.add_edge("hypotheses",  "instruction")
    builder.add_edge("instruction", "probe_wait")   # pause here -- engineer places probes
    builder.add_edge("probe_wait",  "step")         # fires immediately on Resume
    builder.add_edge("step",       "reason")
    builder.add_edge("reason",     "decision")

    builder.add_conditional_edges(
        "decision",
        route_from_decision,
        {"repair": "repair", "interrupt": "interrupt", "end": END}
    )

    # interrupt pauses; resume routes to instruction (shows next probe placement)
    builder.add_edge("interrupt", "resume")

    builder.add_conditional_edges(
        "resume",
        route_from_resume,
        {"instruction": "instruction", "end": END}
    )

    builder.add_edge("repair", END)

    return builder.compile(checkpointer=MemorySaver())


# =============================================================================
# GRAPH FACTORY FOR LANGGRAPH STUDIO
# =============================================================================

def graph():
    """Return the compiled graph for LangGraph Studio."""
    return create_conversational_graph()


# =============================================================================
# ENTRY POINT (quick smoke test)
# =============================================================================

if __name__ == "__main__":
    print("Building hypothesis-driven diagnostic graph...")
    g = create_conversational_graph()
    print("Graph compiled successfully.")
    print(
        "\nFlow: START → rag → hypotheses → instruction → step "
        "→ reason → decision → (repair|interrupt→resume→instruction|END)"
    )