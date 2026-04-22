"""Shared helpers for graph nodes."""

import re


def _parse_manual_reading(text) -> dict | None:
    """Parse a free-text manual reading entered by the engineer.

    Accepted formats (case-insensitive):
      Numeric:      "280 V DC"  "12.5V"  "0.5 ohm"  "1.2 kohm"
      OL sentinel:  "OL"  "open"  "open circuit"
      Natural lang: "no beep"  "it beeped"  "shorted"  "healthy"  etc.

    Returns a dict {"value": float, "unit": str, "measurement_type": str}
    or None if the text does not look like a measurement (e.g. plain "resume").
    """
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None

    lower = text.lower()

    if text.upper() in ("OL", "OPEN", "OPEN CIRCUIT", "OPEN-CIRCUIT"):
        return {"value": 999_999.0, "unit": "ohm", "measurement_type": "CONTINUITY"}

    _healthy_phrases = (
        "d3 ok",
        "d3 good",
        "diode ok",
        "diode good",
        "d3 healthy",
        "diode healthy",
        "beep forward",
        "forward beep",
        "forward only",
        "conducts forward",
    )
    if any(p in lower for p in _healthy_phrases):
        return {"value": 500.0, "unit": "ohm", "measurement_type": "CONTINUITY"}

    _open_phrases = (
        "no beep",
        "didn't beep",
        "did not beep",
        "not beeping",
        "doesnt beep",
        "does not beep",
        "silent",
        "no continuity",
        "open circuit",
        "good condition",
        "healthy",
        "working",
        "intact",
        "passing",
        "passed",
        "no short",
        "not shorted",
        "mosfet good",
        "mosfet ok",
        "q1 good",
        "q1 ok",
        "fuse good",
        "fuse ok",
        "fuse intact",
    )
    if any(p in lower for p in _open_phrases):
        return {"value": 999_999.0, "unit": "ohm", "measurement_type": "CONTINUITY"}

    _short_phrases = (
        "beeped",
        "it beeped",
        "beeping",
        "continuous beep",
        "beep",
        "shorted",
        "short circuit",
        "short",
        "failed",
        "faulty",
        "bad condition",
        "broken",
        "damaged",
        "mosfet bad",
        "mosfet shorted",
        "q1 bad",
        "q1 shorted",
        "d3 shorted",
        "d3 bad",
        "diode shorted",
    )
    if any(p in lower for p in _short_phrases):
        return {"value": 0.0, "unit": "ohm", "measurement_type": "CONTINUITY"}

    m = re.match(r"^([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*([A-Za-z°Ω%/][A-Za-z°Ω%/ ]*)?\s*$", text)
    if m:
        try:
            value = float(m.group(1))
            unit = (m.group(2) or "").strip()
            return {"value": value, "unit": unit, "measurement_type": "manual"}
        except ValueError:
            pass
    return None
