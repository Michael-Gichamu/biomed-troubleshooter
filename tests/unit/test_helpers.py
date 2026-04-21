"""Unit tests for :func:`src.graph.helpers._parse_manual_reading`.

The parser has 11+ branches (OL sentinel, healthy phrases, open phrases, short
phrases, numeric with/without unit, invalid inputs). Testing every branch keeps
manual-reading regressions out of the diagnostic loop.
"""

import pytest

from src.graph.helpers import _parse_manual_reading


class TestOLAndOpen:
    @pytest.mark.parametrize("txt", ["OL", "open", "OPEN CIRCUIT", "open-circuit"])
    def test_ol_sentinel(self, txt):
        result = _parse_manual_reading(txt)
        assert result == {"value": 999_999.0, "unit": "ohm",
                          "measurement_type": "CONTINUITY"}

    @pytest.mark.parametrize("txt", [
        "no beep", "didn't beep", "did not beep", "silent",
        "mosfet good", "fuse ok", "q1 good", "healthy",
    ])
    def test_open_natural_language(self, txt):
        assert _parse_manual_reading(txt)["value"] == 999_999.0


class TestShortedAndHealthy:
    @pytest.mark.parametrize("txt", [
        "beeped", "it beeped", "shorted", "short circuit",
        "mosfet shorted", "q1 bad", "d3 shorted", "broken",
    ])
    def test_short_phrases(self, txt):
        result = _parse_manual_reading(txt)
        assert result == {"value": 0.0, "unit": "ohm",
                          "measurement_type": "CONTINUITY"}

    @pytest.mark.parametrize("txt", [
        "D3 ok", "diode good", "d3 healthy",
        "beep forward", "forward only", "conducts forward",
    ])
    def test_d3_healthy_maps_to_500_ohm(self, txt):
        # Important: D3-healthy MUST NOT map to 999999 (that is the FAULT
        # sentinel for D3 continuity). 500 ohm is within the healthy band.
        result = _parse_manual_reading(txt)
        assert result == {"value": 500.0, "unit": "ohm",
                          "measurement_type": "CONTINUITY"}


class TestNumeric:
    @pytest.mark.parametrize("txt, value, unit", [
        ("280",       280.0, ""),
        ("280 V DC",  280.0, "V DC"),
        ("12.5V",     12.5,  "V"),
        ("0.5 ohm",   0.5,   "ohm"),
        ("-3.2 mV",   -3.2,  "mV"),
        ("1.2e3",     1200.0, ""),
    ])
    def test_parses_numeric(self, txt, value, unit):
        result = _parse_manual_reading(txt)
        assert result is not None
        assert result["value"] == value
        assert result["unit"] == unit
        assert result["measurement_type"] == "manual"


class TestInvalid:
    @pytest.mark.parametrize("txt", [
        None, "", "   ", "resume", "continue please",
    ])
    def test_returns_none_for_non_measurement(self, txt):
        # "resume" is a common engineer keyword that must NOT be parsed as
        # a reading — otherwise the probe_wait_node would inject a fake value.
        assert _parse_manual_reading(txt) is None

    def test_non_string_returns_none(self):
        assert _parse_manual_reading(42) is None
        assert _parse_manual_reading(["12V"]) is None
