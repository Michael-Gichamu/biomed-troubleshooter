"""Step node — take one multimeter measurement and report the result."""

from datetime import datetime

from langchain_core.messages import AIMessage

from src.graph.state import ConversationalAgentState


def step_node(state: ConversationalAgentState):
    """Execute one atomic measurement step.

    The interrupt that ran BEFORE this node already showed the engineer where
    to place their probes. This node's only job is:
      1. Read the multimeter (15 s timeout max).
      2. Evaluate result against expected range.
      3. Emit a concise measurement-result message.
    """
    from src.studio.tools import read_multimeter

    if state.current_step >= len(state.test_point_rankings):
        return {
            "step_result": {"decision": "no_more_tests", "reasoning": "No remaining test points"},
            "messages": [AIMessage(content="No remaining test points. Proceeding to analysis...")],
        }

    test_point_id = state.test_point_rankings[state.current_step]

    signal_def: dict = {}
    for sig in state.equipment_config.get("signals", []):
        if sig.get("signal_id") == test_point_id:
            signal_def = sig
            break

    signal_name = signal_def.get("name", test_point_id)
    measurement_type = signal_def.get("parameter", "voltage_dc")

    expected = state.expected_values.get(test_point_id, {"min": 0, "max": 999_999, "unit": "V"})

    hyp_desc = next(
        (
            h.get("description", "")
            for h in state.hypotheses
            if h.get("id") == state.current_hypothesis
        ),
        "",
    )

    # Manual entry takes priority over USB reader.
    if state.pending_manual_reading:
        m = state.pending_manual_reading
        result = {
            "status": "success",
            "value": m["value"],
            "unit": m.get("unit", expected.get("unit", "")),
            "measurement_type": m.get("measurement_type", "manual"),
            "test_point": test_point_id,
            "message": "Manual reading entered by engineer",
        }
    else:
        try:
            result = read_multimeter.invoke(
                {
                    "equipment_model": state.equipment_model,
                    "test_point": test_point_id,
                    "measurement_type": measurement_type,
                    "max_duration": 15.0,
                }
            )
        except Exception as e:
            result = {
                "status": "error",
                "error": str(e),
                "test_point": test_point_id,
                "value": None,
            }

    meas_value = result.get("value", None)
    meas_unit = result.get("unit", expected.get("unit", "V"))
    status = result.get("status", "unknown")

    # Human-readable display for continuity OL sentinel.
    _raw_meas_type = (result.get("measurement_type") or measurement_type or "").upper()
    _is_continuity = _raw_meas_type == "CONTINUITY"
    try:
        _is_ol = _is_continuity and meas_value is not None and float(meas_value) >= 999_000
    except (ValueError, TypeError):
        _is_ol = False
    display_value = "OL (open — no beep)" if _is_ol else meas_value

    meas_type_display = {
        "DC_VOLTAGE": "V DC",
        "AC_VOLTAGE": "V AC",
        "DC_CURRENT": "A DC",
        "AC_CURRENT": "A AC",
        "RESISTANCE": "Ω",
        "CONTINUITY": "Ω",
        "FREQUENCY": "Hz",
    }.get((result.get("measurement_type") or measurement_type or "").upper(), meas_unit)

    evaluation = "normal"
    if status == "success" and meas_value is not None:
        min_v = expected.get("min")
        max_v = expected.get("max")
        min_v = 0 if min_v is None else float(min_v)
        max_v = 999_999 if max_v is None else float(max_v)
        if not (min_v <= float(meas_value) <= max_v):
            evaluation = "fault"
    elif status in ("timeout", "error", "timeout_unstable"):
        evaluation = "measurement_unavailable"

    step_num = state.current_step + 1
    total_num = len(state.test_point_rankings)

    parts = [f"**[4. Measurement {step_num}/{total_num}]**\n"]

    if hyp_desc:
        parts.append(f"*Testing: {hyp_desc}*\n")

    if evaluation == "fault":
        parts.append(f"### ⚠️ FAULT -- {signal_name}")
        parts.append(
            f"**Measured:** {display_value} {'' if _is_ol else meas_type_display}".rstrip()
        )
        parts.append(f"**Expected:** {expected['min']} -- {expected['max']} {meas_type_display}")
        diag = signal_def.get("diagnostic_meaning", "")
        if diag:
            parts.append(f"**Implication:** {diag}")

    elif evaluation == "measurement_unavailable":
        parts.append(f"### ⚠️ READING UNAVAILABLE -- {signal_name}")
        if meas_value is not None:
            parts.append(
                f"**Best-effort reading:** {display_value} {'' if _is_ol else meas_type_display}".rstrip()
            )
        parts.append(f"**Expected:** {expected['min']} -- {expected['max']} {meas_type_display}")
        reason = result.get("message", "Could not obtain a stable reading.")
        parts.append(f"**Reason:** {reason}")
        parts.append(
            "_Check probe contact and hold steady. "
            "You can also enter a manual reading using the `enter_manual_reading` tool._"
        )

    else:  # normal
        parts.append(f"### ✓ NORMAL -- {signal_name}")
        parts.append(
            f"**Measured:** {display_value} {'' if _is_ol else meas_type_display}".rstrip()
        )
        parts.append(f"**Expected:** {expected['min']} -- {expected['max']} {meas_type_display}")
        diag = signal_def.get("diagnostic_meaning", "")
        if diag:
            parts.append(f"**Implication:** {diag}")

    parts.append("\n*Updating hypothesis probabilities...*")

    record = {
        "test_point": test_point_id,
        "signal_name": signal_name,
        "value": meas_value,
        "unit": meas_unit,
        "status": status,
        "evaluation": evaluation,
        "expected_min": expected.get("min", 0),
        "expected_max": expected.get("max", 999_999),
        "hypothesis_being_tested": state.current_hypothesis,
        "message": result.get("message", result.get("error", "")),
        "timestamp": str(datetime.now()),
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
            "next_test_point": next_tp,
        },
        "measurements": state.measurements + [record],
        "next_test_point": next_tp or "",
        "messages": [AIMessage(content="\n".join(parts))],
        "iteration_count": state.iteration_count + 1,
        "pending_manual_reading": None,  # consumed — clear for next measurement
    }
