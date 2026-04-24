"""Tests for ROI computation.

Covers:
- compute_roi with positive improvement
- compute_roi with negative improvement (degradation)
- compute_roi with zero baseline (division safety)
- compute_roi skips metrics without value_map entry
- compute_total_roi aggregation
"""
from __future__ import annotations

import pytest

from jobos.kernel.roi import ROIEstimate, compute_roi, compute_total_roi


class TestComputeROI:
    def test_positive_improvement(self):
        baselines = {"accuracy": 0.80}
        current = {"accuracy": 0.90}
        value_map = {"accuracy": 10000.0}  # $10k per unit improvement

        estimates = compute_roi(baselines, current, value_map)

        assert len(estimates) == 1
        est = estimates[0]
        assert est.metric_name == "accuracy"
        assert est.improvement == pytest.approx(0.10, abs=0.001)
        assert est.estimated_value == pytest.approx(1000.0, abs=1.0)
        assert est.improvement_pct > 0

    def test_negative_improvement_degradation(self):
        baselines = {"throughput": 100.0}
        current = {"throughput": 80.0}
        value_map = {"throughput": 50.0}

        estimates = compute_roi(baselines, current, value_map)

        assert len(estimates) == 1
        est = estimates[0]
        assert est.improvement < 0
        assert est.estimated_value < 0
        assert est.improvement_pct < 0

    def test_zero_baseline_division_safety(self):
        baselines = {"latency": 0.0}
        current = {"latency": 5.0}
        value_map = {"latency": 100.0}

        estimates = compute_roi(baselines, current, value_map)

        assert len(estimates) == 1
        est = estimates[0]
        # improvement_pct should be 0.0 when baseline is zero (division safety)
        assert est.improvement_pct == 0.0
        # But the absolute improvement and value should still be computed
        assert est.improvement == pytest.approx(5.0, abs=0.001)
        assert est.estimated_value == pytest.approx(500.0, abs=1.0)

    def test_skips_metrics_without_value_map(self):
        baselines = {"accuracy": 0.80, "speed": 50.0}
        current = {"accuracy": 0.90, "speed": 60.0}
        value_map = {"accuracy": 10000.0}  # no entry for "speed"

        estimates = compute_roi(baselines, current, value_map)

        assert len(estimates) == 1
        assert estimates[0].metric_name == "accuracy"

    def test_skips_metrics_without_current_value(self):
        baselines = {"accuracy": 0.80}
        current = {}  # no current value
        value_map = {"accuracy": 10000.0}

        estimates = compute_roi(baselines, current, value_map)
        assert len(estimates) == 0

    def test_multiple_metrics(self):
        baselines = {"accuracy": 0.80, "speed": 50.0}
        current = {"accuracy": 0.90, "speed": 70.0}
        value_map = {"accuracy": 10000.0, "speed": 200.0}

        estimates = compute_roi(baselines, current, value_map)
        assert len(estimates) == 2

    def test_estimate_has_assumptions(self):
        baselines = {"accuracy": 0.80}
        current = {"accuracy": 0.90}
        value_map = {"accuracy": 10000.0}

        estimates = compute_roi(baselines, current, value_map)
        assert len(estimates[0].assumptions) > 0


class TestComputeTotalROI:
    def test_aggregation(self):
        estimates = [
            ROIEstimate(
                metric_name="accuracy",
                baseline_value=0.80,
                current_value=0.90,
                improvement=0.10,
                improvement_pct=12.5,
                estimated_value=1000.0,
            ),
            ROIEstimate(
                metric_name="speed",
                baseline_value=50.0,
                current_value=70.0,
                improvement=20.0,
                improvement_pct=40.0,
                estimated_value=4000.0,
            ),
        ]
        total = compute_total_roi(estimates)

        assert total["total_estimated_value"] == 5000.0
        assert total["metric_count"] == 2
        assert total["currency"] == "USD"
        assert total["average_confidence"] == 0.5

    def test_empty_estimates(self):
        total = compute_total_roi([])
        assert total["total_estimated_value"] == 0.0
        assert total["metric_count"] == 0
        assert total["average_confidence"] == 0.0
