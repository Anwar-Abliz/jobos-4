"""Tests for phase scoring (Identify-Define-Decide loop).

Covers:
- score_identify_phase with all tiers present
- score_identify_phase with no jobs
- score_define_phase with full metric coverage
- score_define_phase with no metrics
- score_decide_phase with go verdict
- score_decide_phase with no_go verdict
- composite_score weighting
"""
from __future__ import annotations

import pytest

from jobos.kernel.phase_metrics import (
    PhaseScore,
    composite_score,
    score_decide_phase,
    score_define_phase,
    score_identify_phase,
)


class TestScoreIdentifyPhase:
    def test_all_tiers_present(self):
        jobs = [
            {"tier": "T1_strategic", "statement": "Achieve sustainable growth"},
            {"tier": "T2_core", "statement": "Reduce processing errors"},
            {"tier": "T3_execution", "statement": "Implement validation pipeline"},
            {"tier": "T4_micro", "statement": "Verify output parameters"},
        ]
        result = score_identify_phase(jobs)

        assert result.phase == "identify"
        assert result.components["tier_coverage"] == 1.0
        assert result.score > 0.0

    def test_partial_tiers(self):
        jobs = [
            {"tier": "T1_strategic", "statement": "Achieve growth"},
            {"tier": "T3_execution", "statement": "Implement pipeline"},
        ]
        result = score_identify_phase(jobs)

        assert result.components["tier_coverage"] == 0.5
        assert result.score < 1.0

    def test_no_jobs(self):
        result = score_identify_phase([])

        assert result.phase == "identify"
        assert result.score == 0.0
        assert "No jobs" in result.reasoning

    def test_with_axiom_satisfaction(self):
        jobs = [
            {"tier": "T1_strategic", "statement": "Achieve growth"},
            {"tier": "T2_core", "statement": "Reduce errors"},
        ]
        axioms = {"hierarchy": 1.0, "imperfection": 0.8, "linguistic": 1.0}
        result = score_identify_phase(jobs, axiom_satisfaction=axioms)

        # Axiom compliance should be the mean of the provided values
        expected_axiom = (1.0 + 0.8 + 1.0) / 3.0
        assert result.components["axiom_compliance"] == pytest.approx(
            expected_axiom, abs=0.01,
        )

    def test_statement_quality_scoring(self):
        jobs = [
            {"tier": "T1_strategic", "statement": "Achieve sustainable growth"},
            {"tier": "T2_core", "statement": "not a verb statement"},
        ]
        result = score_identify_phase(jobs)

        # One valid, one invalid statement
        assert result.components["statement_quality"] == pytest.approx(0.5, abs=0.01)


class TestScoreDefinePhase:
    def test_full_metric_coverage(self):
        result = score_define_phase(
            total_jobs=10,
            jobs_with_metrics=10,
            jobs_with_experience=10,
            baseline_captured=True,
        )

        assert result.phase == "define"
        assert result.score == pytest.approx(1.0, abs=0.01)
        assert result.components["metric_completeness"] == 1.0
        assert result.components["experience_coverage"] == 1.0
        assert result.components["baseline_status"] == 1.0

    def test_no_metrics(self):
        result = score_define_phase(
            total_jobs=10,
            jobs_with_metrics=0,
            jobs_with_experience=0,
            baseline_captured=False,
        )

        assert result.score == 0.0

    def test_partial_coverage(self):
        result = score_define_phase(
            total_jobs=10,
            jobs_with_metrics=5,
            jobs_with_experience=3,
            baseline_captured=True,
        )

        assert 0.0 < result.score < 1.0
        assert result.components["metric_completeness"] == 0.5
        assert result.components["experience_coverage"] == pytest.approx(0.3)

    def test_no_jobs(self):
        result = score_define_phase(
            total_jobs=0,
            jobs_with_metrics=0,
            jobs_with_experience=0,
        )

        assert result.score == 0.0
        assert "No jobs" in result.reasoning


class TestScoreDecidePhase:
    def test_go_verdict(self):
        result = score_decide_phase(
            verdict="go",
            vfe_trend="decreasing",
            comparisons_improving=5,
            comparisons_degrading=0,
        )

        assert result.phase == "decide"
        assert result.components["verdict_quality"] == 1.0
        assert result.components["vfe_trend_quality"] == 1.0
        assert result.components["metric_direction"] == 1.0
        assert result.score == pytest.approx(1.0, abs=0.01)

    def test_no_go_verdict(self):
        result = score_decide_phase(
            verdict="no_go",
            vfe_trend="increasing",
            comparisons_improving=1,
            comparisons_degrading=4,
        )

        assert result.components["verdict_quality"] == 0.3
        assert result.components["vfe_trend_quality"] == 0.0
        assert result.score < 0.5

    def test_inconclusive_verdict(self):
        result = score_decide_phase(
            verdict="inconclusive",
            vfe_trend="stable",
        )

        assert result.components["verdict_quality"] == 0.5
        assert result.components["vfe_trend_quality"] == 0.5

    def test_switch_events_in_reasoning(self):
        result = score_decide_phase(
            verdict="go",
            switch_events_count=3,
        )
        assert "3 switch events" in result.reasoning


class TestCompositeScore:
    def test_weighting(self):
        identify = PhaseScore(phase="identify", score=1.0)
        define = PhaseScore(phase="define", score=1.0)
        decide = PhaseScore(phase="decide", score=1.0)

        total = composite_score(identify, define, decide)
        assert total == pytest.approx(1.0, abs=0.01)

    def test_weighted_average(self):
        # Weights: identify=0.3, define=0.3, decide=0.4
        identify = PhaseScore(phase="identify", score=0.5)
        define = PhaseScore(phase="define", score=0.5)
        decide = PhaseScore(phase="decide", score=1.0)

        total = composite_score(identify, define, decide)
        expected = 0.3 * 0.5 + 0.3 * 0.5 + 0.4 * 1.0
        assert total == pytest.approx(expected, abs=0.01)

    def test_all_zero(self):
        identify = PhaseScore(phase="identify", score=0.0)
        define = PhaseScore(phase="define", score=0.0)
        decide = PhaseScore(phase="decide", score=0.0)

        total = composite_score(identify, define, decide)
        assert total == 0.0
