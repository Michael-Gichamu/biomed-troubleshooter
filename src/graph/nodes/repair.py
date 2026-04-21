"""Repair node — emit combined repair plan covering root cause and collateral damage."""

from langchain_core.messages import AIMessage

from src.graph.state import ConversationalAgentState


def repair_node(state: ConversationalAgentState):
    """Identify the confirmed (root-cause) fault, scan measurements for secondary
    damage caused by the root fault, then emit a single combined repair plan.

    Secondary damage rule: any measurement marked 'fault' that is NOT the
    confirming measurement may indicate collateral damage (e.g. a blown fuse
    caused by a shorted MOSFET). We include those fault records in the repair
    plan after the root-cause steps.
    """
    from src.infrastructure.llm_manager import invoke_with_retry

    faults             = state.suspected_faults
    current_hypothesis = state.current_hypothesis

    fault_id = ""
    for h in state.hypotheses:
        if h.get("id") == current_hypothesis:
            fault_id = h.get("fault_id", "")
            break

    last_meas = state.measurements[-1] if state.measurements else {}
    last_tp   = last_meas.get("test_point", "?")
    last_val  = last_meas.get("value", "?")
    last_unit = last_meas.get("unit", "")

    fault_record: dict = {}
    if fault_id:
        fault_record = next(
            (f for f in faults if f.get("fault_id") == fault_id),
            {}
        )

    # If no direct match, ask LLM to match measurement → fault.
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

    # Detect secondary damage: prior measurements that evaluated as 'fault' but are
    # not the confirming measurement.
    secondary_fault_records: list[dict] = []
    seen_fault_ids: set[str] = {fault_id}

    for m in state.measurements[:-1]:
        if m.get("evaluation") != "fault":
            continue
        m_tp = m.get("test_point", "")
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

    evidence_rows = []
    for m in state.measurements:
        icon = {"fault": "⚠️", "normal": "✓", "measurement_unavailable": "–"}.get(
            m.get("evaluation", ""), "?"
        )
        val  = m.get("value", "?")
        unit = m.get("unit", "")
        ev   = m.get("evaluation", "").replace("_", " ").title()
        try:
            if m.get("measurement_type", "").upper() == "CONTINUITY" and float(val) >= 999_000:
                val, unit = "OL (open)", ""
        except (ValueError, TypeError):
            pass
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

    hyp_mechanism = next(
        (h.get("description", "") for h in state.hypotheses if h.get("id") == current_hypothesis),
        ""
    )

    sec_names = ", ".join(s.get("name", "?") for s in secondary_fault_records)
    sec_line  = f"\n**Secondary damage detected:** {sec_names}" if secondary_fault_records else ""

    msg_parts = [
        "**[6. Repair Procedure]**\n",
        "## ✅ Diagnosis Complete -- Fault Confirmed\n",
        f"**Root Cause:** {fault_name}",
    ]
    if hyp_mechanism:
        msg_parts.append(f"**Mechanism:** {hyp_mechanism}")
    fault_meas = [m for m in state.measurements if m.get("evaluation") == "fault"]
    if fault_meas:
        confirmed_by_parts = [
            f"{m.get('signal_name', m.get('test_point','?'))} = {m.get('value','?')} {m.get('unit','')}"
            for m in fault_meas
        ]
        confirmed_by_str = "; ".join(confirmed_by_parts)
    else:
        confirmed_by_str = f"{last_tp} = {last_val} {last_unit}"
    msg_parts.append(f"**Confirmed by:** {confirmed_by_str}{sec_line}\n")
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
