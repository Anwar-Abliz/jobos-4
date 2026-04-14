"""Tests for Causal Discovery Automation — CDEE engine.

Covers:
- DynamicController.compute_error_signal(): SP - PV formula
- DynamicController.analyze(): PID terms, trend classification
- DynamicController.check_controllability(): before/after correlation
- CausalGuardian.estimate_ate(): ATE from metric history
- CausalGuardian.compute_counterfactual(): phase 1 projection
- SwitchHub.check_stability(): Lyapunov stability classification

Known Phase 1 approximations (explicitly tested):
- ATE = simple mean_after - mean_before (no backdoor adjustment)
- Controllability = (avg_before - avg_after) / avg_before
- Counterfactual = baseline * (1 - alt_impact) (no SCM do-calculus)
- Stability = monotone trend analysis (no Lyapunov function V(x))
"""
from __future__ import annotations

import pytest

from jobos.engines.cdee.controller import DynamicController, ControlSignal, ControllabilityResult
from jobos.engines.cdee.causal_guardian import CausalGuardian, ATEResult, CounterfactualResult
from jobos.engines.cdee.switch_hub import SwitchHub, StabilityResult


# ─── DynamicController: error signal ─────────────────────

class TestComputeErrorSignal:
    def setup_method(self):
        self.ctrl = DynamicController()

    def test_at_target_zero_error(self):
        assert self.ctrl.compute_error_signal(1.0, 1.0) == 0.0

    def test_below_target_positive_error(self):
        # SP=1.0, PV=0.6 → error = 0.4 (needs to go up)
        assert abs(self.ctrl.compute_error_signal(1.0, 0.6) - 0.4) < 1e-9

    def test_above_target_negative_error(self):
        # SP=0.5, PV=0.8 → error = -0.3 (overshot)
        assert abs(self.ctrl.compute_error_signal(0.5, 0.8) - (-0.3)) < 1e-9


# ─── DynamicController: PID analysis ─────────────────────

class TestControllerAnalyze:
    def setup_method(self):
        self.ctrl = DynamicController(kp=1.0, ki=0.1, kd=0.5)

    def test_empty_history_returns_default(self):
        sig = self.ctrl.analyze([])
        assert sig.error_current == 0.0
        assert "No error" in sig.reasoning

    def test_single_reading_p_term_only(self):
        sig = self.ctrl.analyze([0.5])
        assert abs(sig.proportional - 0.5) < 1e-6  # kp * 0.5
        assert sig.derivative == 0.0                # needs 2 readings

    def test_pid_terms_computed_correctly(self):
        history = [0.4, 0.5, 0.6]  # kp=1, ki=0.1, kd=0.5, dt=1
        sig = self.ctrl.analyze(history)
        # P = kp * 0.6 = 0.6
        # I = ki * (0.4+0.5+0.6) * 1.0 = 0.1 * 1.5 = 0.15
        # D = kd * (0.6 - 0.5) / 1.0 = 0.5 * 0.1 = 0.05
        assert abs(sig.proportional - 0.6) < 1e-6
        assert abs(sig.integral - 0.15) < 1e-6
        assert abs(sig.derivative - 0.05) < 1e-6
        assert abs(sig.control_action - 0.8) < 1e-6

    def test_error_current_is_last_reading(self):
        sig = self.ctrl.analyze([0.1, 0.2, 0.9])
        assert sig.error_current == 0.9

    def test_trend_converging(self):
        # Errors decreasing monotonically
        sig = self.ctrl.analyze([0.9, 0.7, 0.5, 0.3, 0.1])
        assert sig.error_trend == "converging"

    def test_trend_diverging(self):
        sig = self.ctrl.analyze([0.1, 0.3, 0.5, 0.7, 0.9])
        assert sig.error_trend == "diverging"

    def test_trend_stable(self):
        sig = self.ctrl.analyze([0.5, 0.5, 0.5])
        assert sig.error_trend == "stable"

    def test_phase1_always_reports_controllable(self):
        sig = self.ctrl.analyze([0.9, 0.95, 1.0])
        assert sig.is_controllable is True


# ─── DynamicController: controllability ──────────────────

class TestCheckControllability:
    def setup_method(self):
        self.ctrl = DynamicController()

    def test_no_data_returns_controllable(self):
        result = self.ctrl.check_controllability([], [], [])
        assert result.is_controllable is True
        assert "Insufficient" in result.reasoning

    def test_error_reduced_after_hire_is_controllable(self):
        before = [0.8, 0.9]
        after = [0.3, 0.2]
        result = self.ctrl.check_controllability([], before, after)
        assert result.is_controllable is True
        assert result.correlation > 0

    def test_error_increased_after_hire_is_uncontrollable(self):
        before = [0.2, 0.3]
        after = [0.8, 0.9]  # got much worse
        result = self.ctrl.check_controllability([], before, after)
        assert result.is_controllable is False
        assert result.correlation < -0.1

    def test_correlation_formula(self):
        # avg_before=1.0, avg_after=0.5 → correlation = (1-0.5)/1 = 0.5
        before = [1.0, 1.0]
        after = [0.5, 0.5]
        result = self.ctrl.check_controllability([], before, after)
        assert abs(result.correlation - 0.5) < 1e-4

    def test_evidence_count_is_total_readings(self):
        before = [0.5, 0.6, 0.7]
        after = [0.3, 0.2]
        result = self.ctrl.check_controllability([], before, after)
        assert result.evidence_count == 5


# ─── CausalGuardian: ATE estimation ──────────────────────

class TestCausalGuardianATE:
    def setup_method(self):
        self.cg = CausalGuardian()

    def test_insufficient_data_returns_zero_effect(self):
        result = self.cg.estimate_ate([0.8], [0.5])  # only 1 each
        assert result.effect_estimate == 0.0
        assert result.is_significant is False
        assert "Insufficient" in result.reasoning

    def test_positive_ate_improvement(self):
        # Mean before=0.8, mean after=0.4 → ATE = -0.4 (metric improved — lower is better)
        result = self.cg.estimate_ate([0.8, 0.9], [0.4, 0.3])
        assert result.effect_estimate < 0  # metric went down
        assert result.method == "before_after"

    def test_negative_ate_worsened(self):
        result = self.cg.estimate_ate([0.2, 0.3], [0.8, 0.9])
        assert result.effect_estimate > 0  # metric went up (worse for a 'minimize' metric)

    def test_ci_spans_zero_when_marginal_change(self):
        # Tiny change → CI will span zero → not significant
        result = self.cg.estimate_ate([0.500, 0.501], [0.499, 0.502])
        assert result.is_significant is False

    def test_large_clear_change_is_significant(self):
        # Need enough readings for SE to be small relative to ATE
        # ATE = -0.8, SE = 0.8/sqrt(10) ≈ 0.253 → CI = (-0.8 ± 0.496) → entirely negative
        before = [0.9] * 10
        after = [0.1] * 10
        result = self.cg.estimate_ate(before, after)
        assert result.is_significant is True

    def test_ate_formula(self):
        # mean_before = 0.8, mean_after = 0.4 → ATE = -0.4
        result = self.cg.estimate_ate([0.8, 0.8], [0.4, 0.4])
        assert abs(result.effect_estimate - (-0.4)) < 1e-4

    def test_ci_lower_less_than_upper(self):
        result = self.cg.estimate_ate([0.8, 0.9], [0.3, 0.4])
        ci_lower, ci_upper = result.confidence_interval
        assert ci_lower <= ci_upper


# ─── CausalGuardian: counterfactual ──────────────────────

class TestCausalGuardianCounterfactual:
    def setup_method(self):
        self.cg = CausalGuardian()

    def test_no_history_returns_empty_result(self):
        result = self.cg.compute_counterfactual("h1", "h2", [], 0.5)
        assert result.current_outcome == 0.0
        assert "No metric" in result.reasoning

    def test_current_outcome_is_last_reading(self):
        result = self.cg.compute_counterfactual("h1", "h2", [0.8, 0.6, 0.4], 0.5)
        assert result.current_outcome == 0.4  # last reading

    def test_counterfactual_formula(self):
        # baseline = history[0] = 0.8
        # counterfactual = 0.8 * (1 - 0.5) = 0.4
        # delta = 0.4 - 0.4 (current) = 0.0
        result = self.cg.compute_counterfactual("h1", "h2", [0.8, 0.4], 0.5)
        assert abs(result.counterfactual_outcome - 0.4) < 1e-4

    def test_positive_delta_means_alternative_better(self):
        # current_outcome = 0.8 (high/bad)
        # alt: baseline=0.8, impact=0.9 → counterfactual = 0.8 * 0.1 = 0.08
        # delta = 0.08 - 0.8 = -0.72 (negative → alternative is better, lower value)
        result = self.cg.compute_counterfactual("h1", "h2", [0.8], 0.9)
        assert result.delta < 0  # counterfactual outcome is lower (better for minimize metrics)

    def test_confidence_low_for_phase1(self):
        result = self.cg.compute_counterfactual("h1", "h2", [0.8, 0.6], 0.5)
        assert result.confidence <= 0.5  # Phase 1 always returns 0.3


# ─── SwitchHub: Lyapunov stability ───────────────────────

class TestSwitchHub:
    def setup_method(self):
        self.hub = SwitchHub(divergence_window=4)

    def test_insufficient_data_returns_stable(self):
        result = self.hub.check_stability([0.5, 0.6])
        assert result.status == "stable"
        assert result.should_switch is False

    def test_converging_errors_no_switch(self):
        # Errors monotonically decreasing
        result = self.hub.check_stability([0.8, 0.6, 0.4, 0.2])
        assert result.status == "converging"
        assert result.should_switch is False
        assert result.urgency == "none"

    def test_diverging_errors_triggers_switch(self):
        # divergence_window=4 → need 3 consecutive increases
        result = self.hub.check_stability([0.1, 0.3, 0.5, 0.7])
        assert result.status == "diverging"
        assert result.should_switch is True
        assert result.urgency == "critical"

    def test_oscillating_gives_warning_not_switch(self):
        # Up-down-up-down pattern
        result = self.hub.check_stability([0.3, 0.7, 0.2, 0.8, 0.3])
        assert result.status == "oscillating"
        assert result.should_switch is False
        assert result.urgency == "warning"

    def test_stable_flat_errors(self):
        result = self.hub.check_stability([0.4, 0.4, 0.4, 0.4])
        assert result.should_switch is False

    def test_small_noise_does_not_trigger_diverging(self):
        # Tiny fluctuations within 0.005 tolerance
        result = self.hub.check_stability([0.500, 0.503, 0.502, 0.501])
        assert result.status != "diverging"

    def test_consecutive_diverging_count_reported(self):
        result = self.hub.check_stability([0.1, 0.3, 0.5, 0.7])
        assert result.consecutive_diverging >= 2
