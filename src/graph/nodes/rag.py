"""RAG node — fetches equipment config and RAG knowledge once at session start."""

import re

from langchain_core.messages import AIMessage, HumanMessage

from src.graph.rag_cache import _get_cached_rag_knowledge
from src.graph.state import ConversationalAgentState, _text


def rag_node(state: ConversationalAgentState):
    """Fetch everything we need for the whole session in a single pass.

    1. Extract equipment model from the user's message.
    2. Query RAG for diagnostic knowledge snippets.
    3. Fetch complete equipment config (thresholds, faults, images).
    4. Fetch full signal list (physical_description, image_url, pro_tips).
    5. Build expected_values lookup with correct per-signal units.
    6. Emit a brief initialisation AIMessage.
    """
    from src.infrastructure.equipment_config import get_equipment_config

    equipment_model = state.equipment_model

    # Detect new thread: exactly one HumanMessage means this is the first turn.
    human_messages = [m for m in state.messages if isinstance(m, HumanMessage)]
    is_new_thread = len(human_messages) == 1

    # Extract equipment model from message history if not already in state.
    if not equipment_model:
        pattern = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"  # generic slug pattern
        for msg in reversed(state.messages):
            if isinstance(msg, HumanMessage):
                match = re.search(pattern, _text(msg.content), re.IGNORECASE)
                if match:
                    equipment_model = match.group(0).lower()
                    break

    if not equipment_model:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "**[1. Initialization]**\n\n"
                        "⚠️ No equipment model detected in your message. "
                        "Please mention the model ID (e.g. `cctv-psu-24w-v1`) to begin diagnosis."
                    )
                )
            ]
        }

    # Get RAG knowledge (cached per equipment model).
    rag_knowledge = _get_cached_rag_knowledge(equipment_model)

    # Load equipment config directly from YAML — much faster than an API call.
    try:
        config = get_equipment_config(equipment_model)

        config_result = {"test_points": [], "thresholds": {}, "faults": [], "signals": []}

        # Get signals from config (signals is a Dict[str, SignalConfig]).
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
                    "pro_tips": sig.pro_tips or [],
                    "probe_placement": sig.probe_placement or "",
                }
                for sig in config.signals.values()
            ]
            config_result["test_points"] = config_result["signals"]

        # Get signal dependencies.
        if hasattr(config, "signal_dependencies") and config.signal_dependencies:
            config_result["signal_dependencies"] = [
                {"upstream": d.upstream, "downstream": d.downstream, "relationship": d.relationship}
                for d in config.signal_dependencies
            ]

        # Get thresholds from config (thresholds is a Dict[str, ThresholdConfig]).
        if config.thresholds:
            for signal_id, threshold_data in config.thresholds.items():
                states = {}
                for state_name, state in threshold_data.states.items():
                    states[state_name] = {
                        "min": state.min_value,
                        "max": state.max_value,
                        "description": state.description,
                    }
                config_result["thresholds"][signal_id] = {
                    "signal_id": threshold_data.signal_id,
                    "states": states,
                }

        # Get faults from config (faults is a Dict[str, FaultConfig]).
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
                            "confidence": h.confidence,
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
                            "difficulty": r.difficulty,
                        }
                        for r in f.recovery
                    ],
                }
                for f in config.faults.values()
            ]

    except FileNotFoundError as e:
        # Unknown equipment model — tell the user and let the graph short-circuit
        # at the conditional edge after rag. Empty ``equipment_config`` signals
        # "do not proceed into hypothesis generation".
        return {
            "equipment_model": equipment_model,
            "equipment_config": {
                "error": str(e),
                "test_points": [],
                "thresholds": {},
                "faults": [],
                "signals": [],
            },
            "messages": [
                AIMessage(
                    content=(
                        f"**[1. Initialization]**\n\n"
                        f"⚠️ Equipment model **{equipment_model}** was not found "
                        f"in the catalogue. Double-check the model ID and try again."
                    )
                )
            ],
        }
    except Exception as e:
        return {
            "equipment_model": equipment_model,
            "equipment_config": {
                "error": str(e),
                "test_points": [],
                "thresholds": {},
                "faults": [],
                "signals": [],
            },
            "messages": [
                AIMessage(
                    content=(
                        f"**[1. Initialization]**\n\n"
                        f"⚠️ Failed to load configuration for **{equipment_model}**: "
                        f"`{e}`. Please check the equipment catalogue."
                    )
                )
            ],
        }

    full_signals = config_result.get("signals", [])

    # Build expected_values with correct per-signal units.
    signal_units: dict[str, str] = {
        s.get("signal_id", ""): s.get("unit", "V") for s in full_signals
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
                "description": normal.get("description", ""),
            }

    test_points = config_result.get("test_points", [])
    faults = config_result.get("faults", [])

    rag_sources = []
    for r in rag_knowledge[:3]:
        if isinstance(r, dict) and r.get("title"):
            rag_sources.append(r["title"])

    greeting = (
        "Hello Engineer, I am DIAG. I'll guide you through a systematic diagnostic process.\n\n"
        if is_new_thread
        else ""
    )

    rag_line = f"\n*Knowledge sources: {', '.join(rag_sources)}*" if rag_sources else ""

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
        "messages": [AIMessage(content=init_msg)],
    }
