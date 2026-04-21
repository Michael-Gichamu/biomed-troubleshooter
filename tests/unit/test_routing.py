"""Unit tests for :mod:`src.graph.routing`.

These functions are pure: given a state dataclass they return a string
label. They are the single deterministic authority over control flow out
of ``decision`` and ``resume`` nodes — regressions here would silently
misroute sessions.
"""

import pytest

from src.graph.routing import route_from_decision, route_from_resume
from src.graph.state import ConversationalAgentState


@pytest.fixture
def state():
    return ConversationalAgentState()


class TestRouteFromDecision:
    def test_default_when_unset_is_interrupt(self, state):
        assert route_from_decision(state) == "interrupt"

    @pytest.mark.parametrize("next_node, expected", [
        ("repair",      "repair"),
        ("end",         "end"),
        ("instruction", "instruction"),
        ("interrupt",   "interrupt"),
        ("anything_else", "interrupt"),   # fallthrough → interrupt
    ])
    def test_explicit_targets(self, state, next_node, expected):
        state.next_node = next_node
        assert route_from_decision(state) == expected


class TestRouteFromResume:
    def test_goes_to_instruction_when_steps_remain(self, state):
        state.current_step = 0
        state.max_steps = 9
        state.test_point_rankings = ["a", "b", "c"]
        assert route_from_resume(state) == "instruction"

    def test_ends_when_max_steps_reached(self, state):
        state.current_step = 9
        state.max_steps = 9
        state.test_point_rankings = ["a"] * 20
        assert route_from_resume(state) == "end"

    def test_ends_when_rankings_exhausted(self, state):
        state.current_step = 3
        state.max_steps = 9
        state.test_point_rankings = ["a", "b", "c"]  # current_step == len
        assert route_from_resume(state) == "end"
