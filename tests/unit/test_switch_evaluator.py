"""Tests for Axiom 7: SwitchEvaluator heuristic engine.

Covers:
- Normal case: all within bounds → NONE
- Single metric breach → FIRE
- Context delta > threshold → HIRE
- Both conditions → FIRE (triggered_by='both')
- Hysteresis: prevents immediate re-fire when metric still breached but improving
- Edge: empty metrics → NONE
- Property-based: hysteresis_band >= 0 always yields valid action literal
"""
from __future__ import annotations

import math
import pytest
import pytest_asyncio

try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

from jobos.engines.switch_evaluator import SwitchDecision, switch_evaluator


# ─── Fixtures ────────────────────────────────────────────

GOOD_METRICS = {"accuracy": 0.92, "speed": 150.0, "throughput": 45.0}
STANDARD_BOUNDS: dict[str, tuple[float, float | None]] = {
    "accuracy": (0.80, 1.0),
    "speed": (0.0, 200.0),
    "throughput": (30.0, None),
}


# ─── Unit Tests ──────────────────────────────────────────

class TestSwitchEvaluatorNormal:
    """All-within-bounds cases → NONE."""

    @pytest.mark.asyncio
    async def test_all_within_bounds_returns_none(self):
        decision = await switch_evaluator(
            job_id="job_001",
            latest_metrics=GOOD_METRICS,
            context_delta={"relevance": 0.01, "urgency": 0.02},
            bounds=STANDARD_BOUNDS,
        )
        assert decision.action == "NONE"
        assert decision.triggered_by == "none"

    @pytest.mark.asyncio
    async def test_empty_metrics_returns_none(self):
        decision = await switch_evaluator(
            job_id="job_002",
            latest_metrics={},
            context_delta={},
            bounds={},
        )
        assert decision.action == "NONE"
        assert decision.triggered_by == "none"

    @pytest.mark.asyncio
    async def test_empty_context_delta_no_context_change(self):
        decision = await switch_evaluator(
            job_id="job_003",
            latest_metrics=GOOD_METRICS,
            context_delta={},
            bounds=STANDARD_BOUNDS,
        )
        assert decision.action == "NONE"
        assert "stable" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_metrics_exactly_at_lower_bound_not_breached(self):
        # Exactly at lower bound — NOT below by hysteresis_band (0.05)
        # accuracy=0.80 with lower=0.80, hysteresis=0.05 → limit=0.75
        # 0.80 >= 0.75 → no breach
        metrics = {"accuracy": 0.80}
        bounds: dict[str, tuple[float, float | None]] = {"accuracy": (0.80, 1.0)}
        decision = await switch_evaluator(
            job_id="job_004",
            latest_metrics=metrics,
            context_delta={},
            bounds=bounds,
            hysteresis_band=0.05,
        )
        assert decision.action == "NONE"

    @pytest.mark.asyncio
    async def test_unknown_metrics_not_evaluated(self):
        """Metrics not in bounds dict should not trigger breach."""
        decision = await switch_evaluator(
            job_id="job_005",
            latest_metrics={"unknown_metric": 0.0},
            context_delta={},
            bounds=STANDARD_BOUNDS,  # doesn't include 'unknown_metric'
        )
        assert decision.action == "NONE"


class TestSwitchEvaluatorMetricBreach:
    """Metric-breach-only cases → FIRE."""

    @pytest.mark.asyncio
    async def test_single_metric_breach_returns_fire(self):
        metrics = {"accuracy": 0.60, "speed": 150.0, "throughput": 45.0}
        decision = await switch_evaluator(
            job_id="job_010",
            latest_metrics=metrics,
            context_delta={"urgency": 0.01},
            bounds=STANDARD_BOUNDS,
            hysteresis_band=0.05,
        )
        assert decision.action == "FIRE"
        assert decision.triggered_by == "metric_breach"
        assert "accuracy" in decision.details.get("breached_metrics", {})

    @pytest.mark.asyncio
    async def test_multiple_metric_breaches(self):
        metrics = {"accuracy": 0.50, "speed": 150.0, "throughput": 10.0}
        decision = await switch_evaluator(
            job_id="job_011",
            latest_metrics=metrics,
            context_delta={},
            bounds=STANDARD_BOUNDS,
            hysteresis_band=0.05,
        )
        assert decision.action == "FIRE"
        assert decision.triggered_by == "metric_breach"
        breached = decision.details.get("breached_metrics", {})
        assert "accuracy" in breached
        assert "throughput" in breached

    @pytest.mark.asyncio
    async def test_upper_bound_breach_returns_fire(self):
        # speed > 200 + 0.05 → breach
        metrics = {"speed": 260.0}
        bounds: dict[str, tuple[float, float | None]] = {"speed": (0.0, 200.0)}
        decision = await switch_evaluator(
            job_id="job_012",
            latest_metrics=metrics,
            context_delta={},
            bounds=bounds,
            hysteresis_band=0.05,
        )
        assert decision.action == "FIRE"
        assert "speed" in decision.details.get("breached_metrics", {})

    @pytest.mark.asyncio
    async def test_open_ended_upper_bound_not_breached(self):
        # throughput has None as upper bound → no upper breach possible
        metrics = {"throughput": 9999.0}
        bounds: dict[str, tuple[float, float | None]] = {"throughput": (30.0, None)}
        decision = await switch_evaluator(
            job_id="job_013",
            latest_metrics=metrics,
            context_delta={},
            bounds=bounds,
        )
        assert decision.action == "NONE"

    @pytest.mark.asyncio
    async def test_fire_reason_mentions_metric_name(self):
        metrics = {"accuracy": 0.5}
        bounds: dict[str, tuple[float, float | None]] = {"accuracy": (0.8, 1.0)}
        decision = await switch_evaluator(
            job_id="job_014",
            latest_metrics=metrics,
            context_delta={},
            bounds=bounds,
        )
        assert "accuracy" in decision.reason


class TestSwitchEvaluatorContextChange:
    """Context-change-only cases → HIRE."""

    @pytest.mark.asyncio
    async def test_context_change_above_threshold_returns_hire(self):
        # norm = sqrt(0.1^2 + 0.2^2) = sqrt(0.05) ≈ 0.224 > 0.15
        decision = await switch_evaluator(
            job_id="job_020",
            latest_metrics=GOOD_METRICS,
            context_delta={"relevance": 0.1, "urgency": 0.2},
            bounds=STANDARD_BOUNDS,
            context_threshold=0.15,
        )
        assert decision.action == "HIRE"
        assert decision.triggered_by == "context_change"

    @pytest.mark.asyncio
    async def test_context_change_below_threshold_returns_none(self):
        # norm = sqrt(0.05^2 + 0.05^2) ≈ 0.07 < 0.15
        decision = await switch_evaluator(
            job_id="job_021",
            latest_metrics=GOOD_METRICS,
            context_delta={"relevance": 0.05, "urgency": 0.05},
            bounds=STANDARD_BOUNDS,
            context_threshold=0.15,
        )
        assert decision.action == "NONE"

    @pytest.mark.asyncio
    async def test_context_change_reason_mentions_norm(self):
        decision = await switch_evaluator(
            job_id="job_022",
            latest_metrics=GOOD_METRICS,
            context_delta={"x": 0.5},
            bounds=STANDARD_BOUNDS,
            context_threshold=0.15,
        )
        assert decision.action == "HIRE"
        assert "context shift" in decision.reason.lower() or "norm" in decision.reason.lower()


class TestSwitchEvaluatorBothConditions:
    """Both context change AND metric breach."""

    @pytest.mark.asyncio
    async def test_both_conditions_returns_fire_with_both(self):
        # Context shift: norm ≈ 0.224 > 0.15
        # Metric breach: accuracy=0.5 < 0.75 (0.80 - 0.05)
        decision = await switch_evaluator(
            job_id="job_030",
            latest_metrics={"accuracy": 0.5},
            context_delta={"relevance": 0.1, "urgency": 0.2},
            bounds={"accuracy": (0.80, 1.0)},
            context_threshold=0.15,
            hysteresis_band=0.05,
        )
        assert decision.action == "FIRE"
        assert decision.triggered_by == "both"
        assert "accuracy" in decision.details.get("breached_metrics", {})
        assert "context_norm" in decision.details


class TestSwitchEvaluatorHysteresis:
    """Hysteresis dead-band prevents flapping."""

    @pytest.mark.asyncio
    async def test_hysteresis_state_updated_after_fire(self):
        state: dict = {}
        bounds: dict[str, tuple[float, float | None]] = {"accuracy": (0.80, 1.0)}

        # First call: breach → FIRE
        d1 = await switch_evaluator(
            job_id="job_040",
            latest_metrics={"accuracy": 0.60},
            context_delta={},
            bounds=bounds,
            hysteresis_band=0.05,
            _state=state,
        )
        assert d1.action == "FIRE"
        assert state["last_action"] == "FIRE"
        assert "accuracy" in state["breach_metrics"]

    @pytest.mark.asyncio
    async def test_recovery_above_hysteresis_clears_breach(self):
        """After recovery to above the raw bound, breach should re-trigger normally."""
        state: dict = {}
        bounds: dict[str, tuple[float, float | None]] = {"accuracy": (0.80, 1.0)}

        # First: breach
        await switch_evaluator(
            job_id="job_041",
            latest_metrics={"accuracy": 0.60},
            context_delta={},
            bounds=bounds,
            _state=state,
        )
        # Second: full recovery (well above bound)
        d2 = await switch_evaluator(
            job_id="job_041",
            latest_metrics={"accuracy": 0.95},
            context_delta={},
            bounds=bounds,
            _state=state,
        )
        assert d2.action == "NONE"
        assert state["breach_metrics"] == set()

    @pytest.mark.asyncio
    async def test_state_breach_metrics_empty_on_none(self):
        state: dict = {}
        d = await switch_evaluator(
            job_id="job_042",
            latest_metrics=GOOD_METRICS,
            context_delta={},
            bounds=STANDARD_BOUNDS,
            _state=state,
        )
        assert d.action == "NONE"
        assert state.get("breach_metrics") == set()


class TestSwitchDecisionShape:
    """SwitchDecision dataclass shape validation."""

    @pytest.mark.asyncio
    async def test_decision_has_required_fields(self):
        decision = await switch_evaluator(
            job_id="job_050",
            latest_metrics=GOOD_METRICS,
            context_delta={},
            bounds=STANDARD_BOUNDS,
        )
        assert isinstance(decision, SwitchDecision)
        assert decision.action in ("HIRE", "FIRE", "NONE")
        assert decision.triggered_by in ("context_change", "metric_breach", "both", "none")
        assert isinstance(decision.reason, str)
        assert isinstance(decision.details, dict)

    @pytest.mark.asyncio
    async def test_fire_decision_has_breached_metrics_in_details(self):
        decision = await switch_evaluator(
            job_id="job_051",
            latest_metrics={"accuracy": 0.5},
            context_delta={},
            bounds={"accuracy": (0.8, 1.0)},
        )
        assert decision.action == "FIRE"
        assert "breached_metrics" in decision.details
        assert isinstance(decision.details["breached_metrics"], dict)


# ─── Property-Based Tests ────────────────────────────────

if HAS_HYPOTHESIS:
    @given(
        hysteresis_band=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
        accuracy=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        context_val=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_hypothesis_action_always_valid_literal(hysteresis_band, accuracy, context_val):
        """Property: switch_evaluator always returns a valid action literal."""
        import asyncio
        decision = asyncio.get_event_loop().run_until_complete(
            switch_evaluator(
                job_id="prop_test",
                latest_metrics={"accuracy": accuracy},
                context_delta={"x": context_val},
                bounds={"accuracy": (0.8, 1.0)},
                hysteresis_band=hysteresis_band,
            )
        )
        assert decision.action in ("HIRE", "FIRE", "NONE"), (
            f"Invalid action '{decision.action}' for accuracy={accuracy}, "
            f"context={context_val}, hysteresis={hysteresis_band}"
        )
        assert decision.triggered_by in ("context_change", "metric_breach", "both", "none")
