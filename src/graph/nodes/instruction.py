"""Instruction node — emit probe-placement instructions for the current test point."""

from langchain_core.messages import AIMessage

from src.graph.state import ConversationalAgentState


def instruction_node(state: ConversationalAgentState):
    """Emit the probe-placement instructions for the CURRENT test point as a
    plain AIMessage. Does NOT call interrupt() — execution continues
    immediately into step_node.

    state.current_step already points at the test to perform (set to 0 by
    hypotheses_node on the first pass; incremented by reason_node on every
    subsequent pass).
    """
    total_steps = len(state.test_point_rankings)

    current_signal_id = ""
    if state.current_step < len(state.test_point_rankings):
        current_signal_id = state.test_point_rankings[state.current_step]

    current_signal: dict = {}
    if current_signal_id:
        for sig in state.equipment_config.get("signals", []):
            if sig.get("signal_id") == current_signal_id:
                current_signal = sig
                break

    parts: list[str] = []

    if current_signal:
        step_num    = state.current_step + 1
        signal_name = current_signal.get("name", current_signal_id)

        parts.append(f"## 🔬 Measurement {step_num} of {total_steps} -- {signal_name}")

        image_url = current_signal.get("image_url", "")
        if image_url:
            parts.append(f"![{signal_name}]({image_url})")

        phys = current_signal.get("physical_description", "")
        if phys:
            parts.append(f"**📍 Where to find it:**\n{phys}")
            parts.append(f"_Ref: {state.equipment_model}.yaml_")

        tips = current_signal.get("pro_tips", [])
        if tips:
            tip_lines = "\n".join(f"- {t}" for t in tips)
            parts.append(f"**💡 Pro tips:**\n{tip_lines}")

        safety = current_signal.get("safety_warning", "")
        if safety:
            parts.append(f"**⚠️ Safety:**\n{safety}")

        probe_placement = current_signal.get("probe_placement", "")
        if probe_placement:
            parts.append(f"**🔧 Probe placement & meter setting:**\n{probe_placement.strip()}")

        disp_exp = current_signal.get("display_expected", "")
        exp = state.expected_values.get(current_signal_id, {})
        if disp_exp:
            parts.append(f"**Expected reading:** {disp_exp}")
        elif exp:
            parts.append(
                f"**Expected reading:** {exp['min']} – {exp['max']} {exp.get('unit','V')}"
            )

        hyp_desc = next(
            (h.get("description", "") for h in state.hypotheses
             if h.get("id") == state.current_hypothesis),
            ""
        )
        if hyp_desc:
            parts.append(f"*Testing hypothesis: {hyp_desc}*")

        param = current_signal.get("parameter", "")
        if param == "continuity":
            if current_signal_id == "schottky_diode":
                manual_hint = ("- _Type your result (`D3 ok` · `shorted` · `open`) "
                               "and press **Enter** to enter it manually._")
            else:
                manual_hint = ("- _Type your result (e.g. `no beep`, `beeped`, `OL`) "
                               "and press **Enter** to enter it manually._")
        else:
            manual_hint = ("- _Type your reading (e.g. `280 V DC` · `12.5 V` · `0.5 ohm` · `OL`) "
                           "and press **Enter** to enter it manually._")

        parts.append(
            "\n_Follow the instructions above, then:_\n"
            "- _Press **Resume** to auto-read from USB multimeter, **or**_\n"
            f"{manual_hint}"
        )

    else:
        parts.append("## All measurements complete -- proceeding to analysis.")

    return {"messages": [AIMessage(content="\n\n".join(parts))]}
