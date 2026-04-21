"""Tests for Free Energy computation and the NSAIG engine.

Covers:
- PolicyOptimizer.compute_vfe(): VFE = mean normalised deviation
- PolicyOptimizer.select_policy(): greedy EFE minimisation
- BeliefEngine.evaluate_axioms(): axiom satisfaction scores
- BeliefEngine.compute_logic_loss(): aggregate violation sum
- SwitchLogic.analyze(): VFE threshold window monitor

Known Phase 1 approximations (explicitly tested):
- VFE uses |target - observed| / |target| (not KL divergence)
- EFE = VFE_current * (1 - estimated_impact) (not POMDP)
- Missing data counts as surprise = 1.0
"""
from __future__ import annotations

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.engines.nsaig.policy_optimizer import PolicyOptimizer, PolicyResult
from jobos.engines.nsaig.belief_engine import BeliefEngine, AxiomSatisfaction
from jobos.engines.nsaig.switch_logic import SwitchLogic, SwitchRecommendation


# ─── Helpers ─────────────────────────────────────────────

def make_job(job_id: str = "j1", statement: str = "Define scope", level: int = 0) -> EntityBase:
    return EntityBase(
        id=job_id,
        statement=statement,
        entity_type=EntityType.JOB,
        properties={"level": level},
    )

def make_imp(imp_id: str = "i1") -> EntityBase:
    return EntityBase(
        id=imp_id,
        statement="Some imperfection",
        entity_type=EntityType.IMPERFECTION,
        properties={},
    )

def metrics(**kwargs) -> dict:
    """Build a metrics dict: metrics(revenue={"observed": 0.6, "target": 1.0})"""
    return kwargs


# ─── VFE Computation ─────────────────────────────────────

class TestComputeVFE:
    def setup_method(self):
        self.opt = PolicyOptimizer()

    def test_empty_metrics_returns_zero(self):
        assert self.opt.compute_vfe({}) == 0.0

    def test_all_targets_met_returns_zero(self):
        m = {
            "m1": {"observed": 1.0, "target": 1.0},
            "m2": {"observed": 0.5, "target": 0.5},
        }
        assert self.opt.compute_vfe(m) == 0.0

    def test_single_metric_full_miss(self):
        # observed=0.0, target=1.0 → |1-0|/|1| = 1.0
        m = {"m1": {"observed": 0.0, "target": 1.0}}
        assert self.opt.compute_vfe(m) == 1.0

    def test_single_metric_half_miss(self):
        # observed=0.5, target=1.0 → 0.5
        m = {"m1": {"observed": 0.5, "target": 1.0}}
        assert self.opt.compute_vfe(m) == 0.5

    def test_missing_observed_counts_as_max_surprise(self):
        # observed=None → 1.0 surprise
        m = {"m1": {"observed": None, "target": 1.0}}
        assert self.opt.compute_vfe(m) == 1.0

    def test_missing_target_skipped(self):
        # No target → skipped; only the other metric counts
        m = {
            "m1": {"observed": 0.5, "target": None},   # skipped
            "m2": {"observed": 0.0, "target": 1.0},    # 1.0 deviation
        }
        assert self.opt.compute_vfe(m) == 1.0

    def test_mean_of_multiple_deviations(self):
        # m1: |1-0.8|/1 = 0.2   m2: |1-0.6|/1 = 0.4   mean = 0.3
        m = {
            "m1": {"observed": 0.8, "target": 1.0},
            "m2": {"observed": 0.6, "target": 1.0},
        }
        assert abs(self.opt.compute_vfe(m) - 0.3) < 1e-6

    def test_vfe_capped_at_1_0(self):
        # observed way below target — deviation capped at 1.0
        m = {"m1": {"observed": -100.0, "target": 1.0}}
        assert self.opt.compute_vfe(m) == 1.0

    def test_near_zero_target_uses_absolute(self):
        # target ≈ 0 → use min(1.0, abs(observed))
        # abs(0.5) = 0.5 < 1.0 → result = 0.5
        m = {"m1": {"observed": 0.5, "target": 1e-12}}
        assert self.opt.compute_vfe(m) == 0.5  # min(1.0, abs(0.5)) = 0.5

    def test_vfe_in_0_to_1_range_always(self):
        import random
        random.seed(42)
        opt = PolicyOptimizer()
        for _ in range(50):
            m = {
                "m": {
                    "observed": random.uniform(-2, 2),
                    "target": random.uniform(0.01, 2),
                }
            }
            vfe = opt.compute_vfe(m)
            assert 0.0 <= vfe <= 1.0


# ─── EFE / Policy Selection ───────────────────────────────

class TestSelectPolicy:
    def setup_method(self):
        self.opt = PolicyOptimizer()

    def test_no_candidates_returns_empty_result(self):
        result = self.opt.select_policy(current_metrics={}, candidates=[])
        assert result.recommended_hiree_id is None
        assert "No candidates" in result.reasoning

    def test_selects_highest_impact_candidate(self):
        m = {"m1": {"observed": 0.0, "target": 1.0}}  # VFE = 1.0
        candidates = [
            {"id": "c1", "estimated_impact": 0.3},
            {"id": "c2", "estimated_impact": 0.9},  # best
            {"id": "c3", "estimated_impact": 0.5},
        ]
        result = self.opt.select_policy(m, candidates)
        assert result.recommended_hiree_id == "c2"

    def test_efe_is_lower_than_vfe(self):
        m = {"m1": {"observed": 0.0, "target": 1.0}}
        candidates = [{"id": "c1", "estimated_impact": 0.5}]
        result = self.opt.select_policy(m, candidates)
        assert result.efe_score <= result.vfe_current

    def test_efe_score_formula(self):
        # VFE = 1.0, impact = 0.4 → EFE = 1.0 * (1 - 0.4) = 0.6
        m = {"m1": {"observed": 0.0, "target": 1.0}}
        candidates = [{"id": "c1", "estimated_impact": 0.4}]
        result = self.opt.select_policy(m, candidates)
        assert abs(result.efe_score - 0.6) < 1e-4

    def test_policy_confidence_between_0_and_1(self):
        m = {"m1": {"observed": 0.5, "target": 1.0}}
        candidates = [{"id": "c1", "estimated_impact": 0.6}]
        result = self.opt.select_policy(m, candidates)
        assert 0.0 <= result.policy_confidence <= 1.0

    def test_alternatives_contain_non_selected_candidates(self):
        m = {"m1": {"observed": 0.0, "target": 1.0}}
        candidates = [
            {"id": "c1", "estimated_impact": 0.9},
            {"id": "c2", "estimated_impact": 0.5},
            {"id": "c3", "estimated_impact": 0.3},
            {"id": "c4", "estimated_impact": 0.1},
        ]
        result = self.opt.select_policy(m, candidates)
        assert result.recommended_hiree_id == "c1"
        alt_ids = {a["id"] for a in result.alternatives}
        assert "c1" not in alt_ids  # winner not in alternatives

    def test_zero_vfe_gives_moderate_confidence(self):
        # All metrics met → VFE = 0.0 → confidence defaults to 0.5
        m = {"m1": {"observed": 1.0, "target": 1.0}}
        candidates = [{"id": "c1", "estimated_impact": 0.5}]
        result = self.opt.select_policy(m, candidates)
        assert result.policy_confidence == 0.5


# ─── BeliefEngine ────────────────────────────────────────

class TestBeliefEngine:
    def setup_method(self):
        self.engine = BeliefEngine()

    def test_empty_jobs_returns_all_ones(self):
        sat = self.engine.evaluate_axioms([])
        assert sat.axiom_3_contextual == 1.0
        assert sat.axiom_4_singularity == 1.0
        assert sat.axiom_5_linguistic == 1.0
        assert sat.axiom_6_root_token == 1.0
        assert sat.axiom_2_imperfection == 1.0
        assert sat.logic_loss == 0.0

    def test_valid_jobs_with_imperfections_full_satisfaction(self):
        jobs = [make_job("j1", "Define scope")]
        imps = {"j1": [make_imp()]}
        sat = self.engine.evaluate_axioms(jobs, imps)
        assert sat.axiom_2_imperfection == 1.0
        assert sat.axiom_3_contextual == 1.0
        assert sat.axiom_5_linguistic == 1.0
        assert sat.axiom_4_singularity == 1.0

    def test_two_root_jobs_degrades_singularity(self):
        # Both at level=0 with no parent → Axiom 4 violation
        j1 = make_job("j1", "Define scope", level=0)
        j2 = make_job("j2", "Build product", level=0)
        sat = self.engine.evaluate_axioms([j1, j2])
        assert sat.axiom_4_singularity == 0.0

    def test_missing_imperfection_degrades_axiom_2(self):
        jobs = [make_job("j1", "Define scope")]
        # No imperfections provided
        sat = self.engine.evaluate_axioms(jobs, {})
        assert sat.axiom_2_imperfection == 0.0

    def test_mixed_linguistic_gives_fractional_score(self):
        j_good = make_job("j1", "Define the roadmap")
        j_bad = make_job("j2", "Success is important")  # no action verb
        sat = self.engine.evaluate_axioms([j_good, j_bad])
        assert 0.0 < sat.axiom_5_linguistic < 1.0
        assert abs(sat.axiom_5_linguistic - 0.5) < 1e-6

    def test_logic_loss_is_sum_of_violations(self):
        sat = AxiomSatisfaction(
            axiom_1_hierarchy=0.8,
            axiom_2_imperfection=0.6,
            axiom_3_contextual=0.9,
            axiom_4_singularity=1.0,
            axiom_5_linguistic=0.5,
            axiom_6_root_token=0.7,
        )
        expected = (
            (1 - 0.8) + (1 - 0.6) + (1 - 0.9)
            + (1 - 1.0) + (1 - 0.5) + (1 - 0.7)
        )
        assert abs(self.engine.compute_logic_loss(sat) - expected) < 1e-9

    def test_perfect_satisfaction_gives_zero_logic_loss(self):
        sat = AxiomSatisfaction(
            axiom_1_hierarchy=1.0,
            axiom_2_imperfection=1.0,
            axiom_3_contextual=1.0,
            axiom_4_singularity=1.0,
            axiom_5_linguistic=1.0,
            axiom_6_root_token=1.0,
        )
        assert self.engine.compute_logic_loss(sat) == 0.0

    def test_all_violations_gives_max_logic_loss(self):
        sat = AxiomSatisfaction(
            axiom_1_hierarchy=0.0,
            axiom_2_imperfection=0.0,
            axiom_3_contextual=0.0,
            axiom_4_singularity=0.0,
            axiom_5_linguistic=0.0,
            axiom_6_root_token=0.0,
        )
        assert abs(self.engine.compute_logic_loss(sat) - 6.0) < 1e-9

    def test_non_job_entities_ignored_in_linguistic_check(self):
        cap = EntityBase(
            id="cap1",
            statement="A capability entity",
            entity_type=EntityType.CAPABILITY,
        )
        sat = self.engine.evaluate_axioms([cap])
        # No jobs → default scores all 1.0
        assert sat.axiom_5_linguistic == 1.0

    def test_evaluate_axioms_populates_foundational(self):
        """evaluate_axioms should set the foundational field."""
        jobs = [make_job("j1", "Define scope")]
        imps = {"j1": [make_imp()]}
        sat = self.engine.evaluate_axioms(jobs, imps)
        assert sat.foundational is not None
        assert sat.foundational.f1_teleological == 1.0
        assert sat.foundational.f2_mechanistic == 1.0
        assert sat.foundational.f3_multidimensional == 1.0
        assert abs(sat.foundational.foundational_loss) < 1e-9

    def test_foundational_loss_reflects_operational_violations(self):
        """Foundational loss should increase when operational axioms are violated."""
        # Two root jobs → axiom 4 violation (F1 group)
        # No imperfections → axiom 2 violation (F2 group)
        j1 = make_job("j1", "Define scope", level=0)
        j2 = make_job("j2", "Build product", level=0)
        sat = self.engine.evaluate_axioms([j1, j2], {})
        assert sat.foundational is not None
        # F1 group: axiom 4=0.0, axioms 1=1.0(default), 6=1.0(default) → mean < 1.0
        assert sat.foundational.f1_teleological < 1.0
        # F2 group: axiom 2=0.0 → mean < 1.0
        assert sat.foundational.f2_mechanistic < 1.0
        # Total foundational loss > 0
        assert sat.foundational.foundational_loss > 0.0


# ─── SwitchLogic VFE Monitor ─────────────────────────────

class TestSwitchLogic:
    def setup_method(self):
        self.sl = SwitchLogic(threshold=0.6, window_size=5)

    def test_empty_history_no_switch(self):
        rec = self.sl.analyze([])
        assert rec.should_switch is False
        assert "No VFE" in rec.reasoning

    def test_all_below_threshold_no_switch(self):
        rec = self.sl.analyze([0.1, 0.2, 0.3, 0.4, 0.5])
        assert rec.should_switch is False
        assert rec.urgency == "none"

    def test_sustained_above_threshold_triggers_switch(self):
        # 5 readings all above 0.6 → sustained >= window_size → critical
        rec = self.sl.analyze([0.7, 0.8, 0.9, 0.85, 0.75])
        assert rec.should_switch is True
        assert rec.urgency == "critical"

    def test_partial_breach_gives_warning_not_switch(self):
        # window_size=5, 2-3 consecutive above → warning, not switch
        rec = self.sl.analyze([0.3, 0.3, 0.3, 0.7, 0.8])
        assert rec.should_switch is False
        assert rec.urgency == "warning"

    def test_single_breach_no_warning(self):
        rec = self.sl.analyze([0.3, 0.3, 0.3, 0.3, 0.8])
        # only 1 consecutive above threshold — below window//2=2
        assert rec.should_switch is False
        assert rec.urgency == "none"

    def test_vfe_current_is_last_value(self):
        history = [0.3, 0.4, 0.75]
        rec = self.sl.analyze(history)
        assert rec.vfe_current == 0.75

    def test_trend_decreasing(self):
        rec = self.sl.analyze([0.8, 0.6, 0.4])
        assert rec.vfe_trend == "decreasing"

    def test_trend_increasing(self):
        rec = self.sl.analyze([0.2, 0.4, 0.7])
        assert rec.vfe_trend == "increasing"

    def test_trend_stable(self):
        rec = self.sl.analyze([0.5, 0.5, 0.5])
        assert rec.vfe_trend == "stable"

    def test_custom_threshold(self):
        # Threshold at 0.9 — nothing above it
        sl_strict = SwitchLogic(threshold=0.9, window_size=3)
        rec = sl_strict.analyze([0.8, 0.85, 0.88])
        assert rec.should_switch is False
