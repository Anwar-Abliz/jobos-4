"""Tests for the ThresholdEvaluator stateful wrapper.

Covers:
- No thresholds → NONE
- Breach → FIRE
- Within bounds → NONE
- Hysteresis persists across calls
- configure_from_bounds
- reset_state
"""
from __future__ import annotations

import pytest

from jobos.engines.threshold_evaluator import ThresholdEvaluator


@pytest.mark.asyncio
class TestThresholdEvaluator:

    async def test_no_thresholds_returns_none(self):
        te = ThresholdEvaluator()
        result = await te.evaluate("j1", {"accuracy": 0.5})
        assert result.action == "NONE"

    async def test_within_bounds_returns_none(self):
        te = ThresholdEvaluator()
        te.configure_threshold("accuracy", lower_bound=0.8, upper_bound=1.0)
        result = await te.evaluate("j1", {"accuracy": 0.9})
        assert result.action == "NONE"

    async def test_below_lower_bound_fires(self):
        te = ThresholdEvaluator()
        te.configure_threshold("accuracy", lower_bound=0.8, upper_bound=1.0)
        result = await te.evaluate("j1", {"accuracy": 0.7})
        assert result.action == "FIRE"
        assert result.triggered_by == "metric_breach"

    async def test_above_upper_bound_fires(self):
        te = ThresholdEvaluator()
        te.configure_threshold("speed", lower_bound=0.0, upper_bound=200.0)
        result = await te.evaluate("j1", {"speed": 210.0})
        assert result.action == "FIRE"

    async def test_hysteresis_persists_across_calls(self):
        te = ThresholdEvaluator(default_hysteresis=0.05)
        te.configure_threshold("accuracy", lower_bound=0.8, upper_bound=1.0)

        # First call: breach
        r1 = await te.evaluate("j1", {"accuracy": 0.7})
        assert r1.action == "FIRE"

        # Second call: still below bound but in hysteresis band — should still fire
        # (value 0.7 is below lower - hysteresis = 0.75)
        r2 = await te.evaluate("j1", {"accuracy": 0.7})
        assert r2.action == "FIRE"

    async def test_configure_from_bounds(self):
        te = ThresholdEvaluator()
        te.configure_from_bounds({
            "accuracy": (0.8, 1.0),
            "speed": (0.0, 200.0),
        })
        thresholds = te.get_thresholds()
        assert "accuracy" in thresholds
        assert "speed" in thresholds
        assert thresholds["accuracy"]["lower"] == 0.8
        assert thresholds["speed"]["upper"] == 200.0

    async def test_reset_state_clears_hysteresis(self):
        te = ThresholdEvaluator()
        te.configure_threshold("accuracy", lower_bound=0.8, upper_bound=1.0)

        # Trigger a breach
        await te.evaluate("j1", {"accuracy": 0.7})

        # Reset state
        te.reset_state("j1")

        # Evaluate again with value within bounds → NONE
        r = await te.evaluate("j1", {"accuracy": 0.9})
        assert r.action == "NONE"

    async def test_context_change_returns_hire(self):
        te = ThresholdEvaluator()
        result = await te.evaluate(
            "j1",
            {"accuracy": 0.9},
            context_delta={"vfe_drift": 0.5},
        )
        assert result.action == "HIRE"
        assert result.triggered_by == "context_change"

    async def test_get_thresholds_returns_copy(self):
        te = ThresholdEvaluator()
        te.configure_threshold("x", lower_bound=0.0, upper_bound=1.0)
        t = te.get_thresholds()
        assert "x" in t
        # Mutating the copy should not affect internal state
        t.pop("x")
        assert "x" in te.get_thresholds()
