"""Reason node — update hypothesis probabilities from the latest measurement."""

import json

from langchain_core.messages import AIMessage, HumanMessage

from src.graph.nodes.hypotheses import _extract_confirmed_findings
from src.graph.state import ConversationalAgentState, _text


def reason_node(state: ConversationalAgentState):
    """Update hypothesis probabilities from the latest measurement.

    Also increments ``current_step`` so ``interrupt_node`` targets the next
    test point.
    """
    from src.infrastructure.llm_manager import invoke_with_retry

    if not state.measurements:
        return {
            "step_result": {"decision": "error", "reasoning": "No measurements recorded yet"},
            "current_step": state.current_step + 1,
        }

    last = state.measurements[-1]
    tp_id = last.get("test_point", "")
    meas_value = last.get("value", 0)
    meas_unit = last.get("unit", "V")
    evaluation = last.get("evaluation", "normal")
    signal_name = last.get("signal_name", tp_id)

    # Handle unavailable readings: retry once, then abort.
    if evaluation == "measurement_unavailable":
        status_code = last.get("status", "timeout")

        if status_code == "error":
            cause = "The multimeter could not be contacted — USB port not identified."
            fix = (
                "1. Check the USB cable is firmly seated.\n"
                "2. Verify the multimeter is powered on.\n"
                "3. Confirm the correct COM/USB port is selected in settings."
            )
        elif status_code == "timeout_unstable":
            cause = "Readings were unstable — probe contact was unreliable."
            fix = (
                "1. Press probes firmly onto bare metal at the test point.\n"
                "2. Avoid touching adjacent traces.\n"
                "3. Hold probes steady for at least 3 seconds."
            )
        else:
            cause = "No reading was received within the allowed time window."
            fix = (
                "1. Confirm probe tips are making solid contact.\n"
                "2. Re-check the test point location in the image above.\n"
                "3. Ensure the equipment is powered on."
            )

        if state.consecutive_failures == 0:
            return {
                "consecutive_failures": 1,
                "step_result": {
                    "measurement": last,
                    "evaluation": evaluation,
                    "reasoning": f"First failure at {tp_id}: {cause}",
                    "decision": "retry_probe",
                },
                "messages": [
                    AIMessage(
                        content=(
                            "**[5. Results Analysis]**\n\n"
                            f"⚠️ **No reliable reading at {signal_name}**\n\n"
                            f"**Cause:** {cause}\n\n"
                            f"**How to fix:**\n{fix}\n\n"
                            "_Retrying the same test point. Place probes again and press **Resume**._"
                        )
                    )
                ],
            }
        else:
            return {
                "consecutive_failures": 2,
                "diagnosis_complete": True,
                "diagnosis_status": "aborted_no_reading",
                "step_result": {
                    "measurement": last,
                    "evaluation": evaluation,
                    "reasoning": f"Second failure at {tp_id} — aborting.",
                    "decision": "abort_no_reading",
                },
                "messages": [
                    AIMessage(
                        content=(
                            "**[5. Results Analysis]**\n\n"
                            f"🛑 **Diagnosis halted — {signal_name}**\n\n"
                            "A reliable reading could not be obtained after two attempts.\n\n"
                            f"**Cause:** {cause}\n\n"
                            "Without a valid measurement here the diagnostic cannot continue reliably. "
                            "Please resolve the instrument connection issue and restart the session."
                        )
                    )
                ],
            }

    expected = state.expected_values.get(tp_id, {"min": 0, "max": 999_999, "unit": "V"})

    signal_def: dict = {}
    for sig in state.equipment_config.get("signals", []):
        if sig.get("signal_id") == tp_id:
            signal_def = sig
            break

    hyp_lines = "\n".join(
        f"- {h.get('id','')}: {h.get('description','')} "
        f"(P={state.hypothesis_probabilities.get(h.get('id'), 0):.2f})"
        for h in state.hypotheses
    )

    remaining_tp = state.test_point_rankings[state.current_step + 1 :]
    remaining_tp_str = ", ".join(remaining_tp) if remaining_tp else "None"

    dependencies_def = state.equipment_config.get("signal_dependencies", [])
    dependencies_str = (
        "\n".join(
            f"- Upstream: {d.get('upstream')} -> Downstream: {d.get('downstream')}. Relationship: {d.get('relationship')}"
            for d in dependencies_def
        )
        if dependencies_def
        else "None provided"
    )

    symptom = " ".join(
        _text(m.content) for m in state.messages if isinstance(m, HumanMessage)
    ).strip()
    engineer_findings = _extract_confirmed_findings(symptom, state.test_points)

    completed_str = (
        "\n".join(
            f"- {m.get('test_point','?')} ({m.get('signal_name','?')}): {m.get('value','?')} {m.get('unit','')} [{m.get('evaluation','?').upper()}]"
            for m in state.measurements
        )
        or "None"
    )

    prompt = f"""Update hypothesis probabilities based on this measurement.

TEST POINT: {tp_id} ({signal_name})
DIAGNOSTIC MEANING: {signal_def.get("diagnostic_meaning", "Not provided")}
MEASURED:   {meas_value} {meas_unit}
EXPECTED:   {expected.get('min',0)} – {expected.get('max',999_999)} {meas_unit}
RESULT:     {evaluation.upper()}

HYPOTHESES:
{hyp_lines}

ENGINEER'S CONFIRMED FINDINGS (from symptom report — treat as already known facts):
{engineer_findings}

ALL MEASUREMENTS SO FAR (this session):
{completed_str}

SIGNAL TOPOLOGY DEPENDENCIES:
{dependencies_str}

REMAINING TEST PLAN:
{remaining_tp_str}

Rules:
- A FAULT result supports hypotheses that predict failure at this point; contradicts those that do not
- A NORMAL result contradicts hypotheses that require this point to be faulty
- Use the SIGNAL TOPOLOGY DEPENDENCIES to determine logical eliminations. If a downstream point works, all upstream components must be working — eliminate hypotheses blaming upstream.

CONFIRMATION RULE — Q1 and D3 are always measured as a paired unit before confirming:

  When primary_mosfet (Q1) is found SHORTED (0 ohm / beep):
    - Q1 failure is confirmed as a physical fact.
    - Do NOT set confirmed_hypothesis yet.
    - Check ALL MEASUREMENTS SO FAR: has schottky_diode (D3) already been measured this session?
      YES → proceed to confirmation below (both measured).
      NO  → set updated_remaining_test_plan = ["schottky_diode"] only. Prune everything else.
             D3 must be measured next — it determines if D3 caused Q1's failure.

  When schottky_diode (D3) is found SHORTED (~0V forward in both orientations):
    - D3 failure is confirmed as a physical fact.
    - Do NOT set confirmed_hypothesis yet.
    - Check ALL MEASUREMENTS SO FAR: has primary_mosfet (Q1) already been measured this session?
      YES → proceed to confirmation below (both measured).
      NO  → set updated_remaining_test_plan = ["primary_mosfet"] only. Prune everything else.
             Q1 must be measured next — a shorted D3 frequently causes Q1 overstress.

  After BOTH primary_mosfet and schottky_diode have been measured (regardless of outcome):

  Classify the D3 result before applying the table:
    D3 SHORTED: measured value ~0–0.05V in either/both probe orientations = junction shorted
    D3 OPEN:    measured OL / 999999 / no forward voltage in diode mode = diode burned open
    D3 FAULT:   either SHORTED or OPEN — both represent a failed D3, only the failure mode differs
    D3 NORMAL:  Vf 0.15–0.45V forward, OL reverse = healthy Schottky diode

  Apply this decision table:
    Q1 shorted + D3 FAULT (shorted OR open) → confirmed_hypothesis = cascade failure hypothesis.
      Both Q1 and D3 must be replaced. The fuse blew from this cascade.
    Q1 shorted + D3 NORMAL (Vf 0.15–0.45V forward) → confirmed_hypothesis = Q1 failed independently.
      Replace Q1 only. Re-verify D3 before powering on (borderline D3 can pass but fail under load).
    Q1 normal  + D3 FAULT (shorted OR open) → confirmed_hypothesis = D3 failed (no output rectification path).
      Replace D3. Verify Q1 is still healthy after replacement.
    Q1 normal  + D3 NORMAL → do NOT confirm. Continue diagnosis (startup circuit, U3, or bridge).

  PATH 2 — Probability convergence: one hypothesis exceeds 0.85 with no plausible alternative.
  Do NOT confirm a stage-level hypothesis without the specific component identified.

SPECIFIC PRUNING RULES — apply after EVERY measurement, before reordering:
  After primary_mosfet found SHORTED: remove from remaining plan:
    output_capacitor_esr, feedback_ref, feedback_resistor, output_current, output_12v, bridge_output, input_fuse
    Keep ONLY: schottky_diode (if not yet measured in this session).

  After input fuse known blown (engineer report or measurement):
    Remove: bridge_output, output_12v, feedback_ref, output_current
    (live voltage tests with blown fuse return 0V and carry no diagnostic information).

  After bridge_output = 0V (primary input stage failed):
    Remove: primary_mosfet, schottky_diode, output_capacitor_esr, feedback_ref, feedback_resistor, output_12v
    Keep: bridge rectifier diode test, MOV resistance test (if in plan).

  After bridge_output = 280–340V (primary confirmed working), output = 0V:
    Remove: output_capacitor_esr, feedback_ref, feedback_resistor, output_current
    Keep: primary_mosfet, schottky_diode (these are the active fault candidates).

  Always remove any test already confirmed by the engineer's symptom report.

- Probabilities of non-eliminated hypotheses must sum to 1.0
- After removing irrelevant tests, reorder remaining list: most discriminating test for leading hypothesis comes first. Do NOT add test points not in the original list.

Return ONLY valid JSON:
{{
  "reasoning": "one-sentence explanation",
  "probability_updates": {{"HYPOTHESIS_1": 0.8, "HYPOTHESIS_2": 0.0, ...}},
  "eliminated_faults": ["HYPOTHESIS_2"],
  "confirmed_hypothesis": "HYPOTHESIS_1" or null,
  "updated_remaining_test_plan": ["test_point_1", "test_point_2"]
}}"""

    reasoning = ""
    eliminated = list(state.eliminated_faults)
    updated_probs = dict(state.hypothesis_probabilities)
    confirmed_hypothesis = None
    updated_test_plan = list(remaining_tp)

    try:
        response = invoke_with_retry([{"role": "user", "content": prompt}])
        content = response.content if response else "{}"
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            data = json.loads(content[start : end + 1])
            reasoning = data.get("reasoning", "")
            for h_id, prob in data.get("probability_updates", {}).items():
                if h_id in updated_probs:
                    updated_probs[h_id] = float(prob)
            for e in data.get("eliminated_faults", []):
                if e not in eliminated:
                    eliminated.append(e)
            confirmed_hypothesis = data.get("confirmed_hypothesis") or None

            if "updated_remaining_test_plan" in data:
                updated_test_plan = [
                    tp for tp in data["updated_remaining_test_plan"] if tp in remaining_tp
                ]
    except Exception:
        reasoning = "Analysis inconclusive -- carrying forward current probabilities."

    new_rankings = state.test_point_rankings[: state.current_step + 1] + updated_test_plan

    active = {h: p for h, p in updated_probs.items() if h not in eliminated}
    total = sum(active.values())
    if total > 0:
        for h in active:
            updated_probs[h] = active[h] / total

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

    active_remaining = [h for h in state.hypotheses if h.get("id") not in eliminated]
    if confirmed_hypothesis:
        decision = "fault_confirmed"
    elif not active_remaining:
        decision = "all_eliminated"
    else:
        decision = "continue_diagnosis"

    parts = ["**[5. Results Analysis]**\n"]

    if reasoning:
        parts.append(f"{reasoning}\n")

    parts.append("**Fault candidate status:**")
    sorted_h = sorted(
        state.hypotheses, key=lambda h: updated_probs.get(h.get("id", ""), 0), reverse=True
    )
    for h in sorted_h:
        h_id = h.get("id", "")
        desc = h.get("description", h_id)
        if h_id in eliminated:
            parts.append(f"- ~~{desc}~~ -- eliminated")
        else:
            p = updated_probs.get(h_id, 0)
            marker = " ← **most likely**" if h_id == new_current else ""
            parts.append(f"- {desc}: **{p:.0%}**{marker}")

    reasoning_chain = list(state.diagnostic_reasoning)
    reasoning_chain.append(
        f"Step {state.current_step + 1}: {tp_id} = {meas_value} {meas_unit} "
        f"({evaluation}). {reasoning[:80] if reasoning else ''}"
    )

    next_tp = (
        new_rankings[state.current_step + 1] if state.current_step + 1 < len(new_rankings) else None
    )

    return {
        "hypothesis_probabilities": updated_probs,
        "eliminated_faults": eliminated,
        "current_hypothesis": new_current,
        "test_point_rankings": new_rankings,
        "diagnostic_reasoning": reasoning_chain,
        "step_result": {
            "measurement": last,
            "evaluation": evaluation,
            "reasoning": reasoning,
            "decision": decision,
            "next_test_point": next_tp,
        },
        "messages": [AIMessage(content="\n".join(parts))],
        "current_step": state.current_step + 1,
        "consecutive_failures": 0,
    }
