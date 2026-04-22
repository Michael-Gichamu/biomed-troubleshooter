"""Hypotheses node — rank fault candidates and order test points in one LLM call."""

import json

from langchain_core.messages import AIMessage, HumanMessage

from src.graph.state import ConversationalAgentState, _text


def _extract_confirmed_findings(symptom: str, test_points: list) -> str:
    """Build a CONFIRMED FINDINGS block from the user's symptom text.

    Looks for phrases like 'X is okay', 'X confirmed', 'X replaced', 'blew up', etc.
    Returns a formatted string for injection into the hypotheses_node LLM prompt.
    """
    lines = []
    lower = symptom.lower()

    confirmed_ok: list[str] = []
    already_replaced: list[str] = []
    failure_mode: list[str] = []

    for tp in test_points:
        sid = tp.get("signal_id", "")
        name = tp.get("name", "").lower()
        for kw in [sid.lower(), name]:
            if not kw:
                continue
            if (
                f"{kw} is okay" in lower
                or f"{kw} ok" in lower
                or f"{kw} confirmed" in lower
                or f"{kw} fine" in lower
                or f"{kw} good" in lower
                or f"confirmed {kw}" in lower
            ):
                confirmed_ok.append(f"{sid} ({tp.get('name', '')})")
                break
            if (
                f"replaced {kw}" in lower
                or f"{kw} replaced" in lower
                or f"changed {kw}" in lower
                or f"{kw} changed" in lower
            ):
                already_replaced.append(f"{sid} ({tp.get('name', '')})")
                break

    if "blew up" in lower or "blew again" in lower or "fuse blew" in lower or "fuse blown" in lower:
        failure_mode.append(
            "CATASTROPHIC FAILURE: fuse blew again — indicates active short circuit in primary stage"
        )
    if "no output" in lower or "0v" in lower or "dead" in lower:
        failure_mode.append("Zero output voltage reported")

    if confirmed_ok:
        lines.append(f"CONFIRMED WORKING (do NOT re-test these): {', '.join(confirmed_ok)}")
    if already_replaced:
        lines.append(f"ALREADY REPLACED/TESTED: {', '.join(already_replaced)}")
    for fm in failure_mode:
        lines.append(f"FAILURE MODE INDICATOR: {fm}")

    return "\n".join(lines) if lines else "None extracted"


def hypotheses_node(state: ConversationalAgentState):
    """Single LLM call that produces BOTH the ranked fault hypotheses AND the
    ordered test-point list. Two-in-one to avoid the double-LLM latency that
    was causing 90–180 s delays.
    """
    from src.infrastructure.llm_manager import invoke_with_retry

    equipment_model = state.equipment_model
    test_points = state.test_points
    rag_knowledge = state.rag_knowledge
    faults = state.suspected_faults

    symptom = " ".join(
        _text(m.content) for m in state.messages if isinstance(m, HumanMessage)
    ).strip()

    tp_str = (
        "\n".join(
            f"- {tp.get('signal_id','?')}: {tp.get('name','')} ({tp.get('parameter','')})"
            for tp in test_points[:15]
        )
        or "No test points defined"
    )

    faults_str = (
        "\n".join(
            f"- {f.get('fault_id','')}: {f.get('name','')} -- {f.get('description','')[:150]}"
            for f in faults[:10]
        )
        or "No fault definitions available"
    )

    rag_str = (
        "\n".join(
            f"- {k.get('content','')[:200]}" for k in rag_knowledge[:3] if isinstance(k, dict)
        )
        or "No diagnostic knowledge available"
    )

    confirmed_findings = _extract_confirmed_findings(symptom, test_points)

    prompt = f"""You are a senior electronics diagnostic expert. Analyse the symptom and produce a JSON response.

EQUIPMENT: {equipment_model}
SYMPTOM: {symptom}

CONFIRMED FINDINGS (extracted from engineer's report):
{confirmed_findings}

AVAILABLE TEST POINTS:
{tp_str}

KNOWN FAULTS:
{faults_str}

DIAGNOSTIC KNOWLEDGE:
{rag_str}

TASK:
1. Generate 3–5 fault hypotheses ranked by probability.
2. Rank ALL available test points by diagnostic value for distinguishing these hypotheses.

STEP 1 — HYPOTHESIS FILTERING (apply before assigning any probabilities):
Cross-reference every KNOWN FAULT against the CONFIRMED FINDINGS.
If a fault's symptom_pattern or signature requires a component to be in a failed state
that the engineer has CONFIRMED IS WORKING, that fault is impossible in this session — exclude it entirely.
Examples:
- input_fuse CONFIRMED WORKING → exclude any fault requiring input_fuse=blown (e.g. fuse_cascade_failure)
- ac_input CONFIRMED WORKING → exclude any fault requiring ac_input=missing
- bridge_output CONFIRMED NORMAL → exclude input_stage_failure entirely
Only hypotheses consistent with ALL confirmed findings may appear in the output.

STEP 2 — PROBABILITY RANKING:
Rank surviving hypotheses by probability given the symptom and confirmed findings.
Each hypothesis: unique id (HYPOTHESIS_1 …), fault_id if applicable, description, probability 0.0–1.0.
Probabilities must sum to 1.0.

STEP 3 — TEST SEQUENCE (reason by diagnostic topology, not by component failure frequency):
The first test must be the FAULT BOUNDARY MEASUREMENT for the current confirmed state —
the single test whose result, regardless of outcome, eliminates the most hypotheses.

Apply the following topology reasoning:
- CASE A — Fuse blown or blew again after replacement (CATASTROPHIC FAILURE / active short):
  Power-off resistance tests come first. Q1 drain-source short is the most common cause.
  Sequence: primary_mosfet → schottky_diode → bridge diodes.
  Do NOT place any live voltage test before a confirmed short is ruled out.

- CASE B — AC input and fuse BOTH confirmed working, output = 0V, DC bus state unknown:
  bridge_output is the fault boundary. It determines in ONE measurement whether the failure
  is upstream (bridge rectifier, MOV, C1) or downstream (Q1, startup circuit, D3, secondary).
  Place bridge_output FIRST. After bridge_output result, the remaining sequence follows naturally.

- CASE C — DC bus already confirmed normal (280–340V), output = 0V:
  Fault is in the switching or secondary stage. Place primary_mosfet first (most common failure
  in this sub-tree), then schottky_diode, then startup circuit checks.

- CASE D — All other scenarios: place the test whose two possible outcomes (fault / normal)
  produce the greatest change in probability distribution across the active hypotheses.

CONFIRMED WORKING signals must NOT appear in test_point_rankings.
Use signal_id values EXACTLY as listed above.

Output ONLY a valid JSON object, nothing else:
{{
  "hypotheses": [
    {{"id": "HYPOTHESIS_1", "fault_id": "F001", "description": "...", "probability": 0.5}},
    ...
  ],
  "test_point_rankings": ["signal_id_1", "signal_id_2", ...]
}}"""

    hypotheses: list = []
    hypothesis_probabilities: dict = {}
    test_point_rankings: list = []

    try:
        response = invoke_with_retry([{"role": "user", "content": prompt}])
        content = response.content if response else "{}"

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            data = json.loads(content[start : end + 1])
            hypotheses = data.get("hypotheses", [])
            for h in hypotheses:
                hypothesis_probabilities[h.get("id", "")] = float(h.get("probability", 0.1))
            test_point_rankings = data.get("test_point_rankings", [])
    except Exception:
        for i, fault in enumerate(faults[:5]):
            h = {
                "id": f"HYPOTHESIS_{i + 1}",
                "fault_id": fault.get("fault_id", ""),
                "description": fault.get("description", fault.get("name", ""))[:120],
                "probability": 1.0 / max(min(len(faults), 5), 1),
            }
            hypotheses.append(h)
            hypothesis_probabilities[h["id"]] = h["probability"]

    hypotheses = [h for h in hypotheses if h.get("id")]

    total = sum(hypothesis_probabilities.values())
    if total > 0:
        hypothesis_probabilities = {k: v / total for k, v in hypothesis_probabilities.items()}

    valid_ids = {tp.get("signal_id", "") for tp in test_points}
    test_point_rankings = [s for s in test_point_rankings if s and s in valid_ids]
    if not test_point_rankings:
        test_point_rankings = [tp.get("signal_id", "") for tp in test_points if tp.get("signal_id")]

    current_hypothesis = ""
    if hypotheses:
        current_hypothesis = max(
            hypotheses, key=lambda h: hypothesis_probabilities.get(h["id"], 0)
        ).get("id", "")

    diagnostic_plan = test_point_rankings[: state.max_steps]

    sorted_h = sorted(
        hypotheses, key=lambda h: hypothesis_probabilities.get(h["id"], 0), reverse=True
    )

    lines = [
        "**[3. Preliminary Assessment]**\n",
        f"Symptom: *{symptom}*\n",
        "**Fault candidates by probability:**\n",
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
        "messages": [AIMessage(content="\n".join(lines))],
    }
