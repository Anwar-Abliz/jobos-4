"""Tests for ODI (Outcome-Driven Innovation) scoring."""
from __future__ import annotations

import pytest

from jobos.kernel.odi import (
    compute_opportunity_score,
    map_opportunity_to_vfe,
    validate_outcome_statement,
)


class TestComputeOpportunityScore:
    def test_basic(self):
        # importance=8, satisfaction=4 → 8 + max(0, 8-4) = 12
        assert compute_opportunity_score(8, 4) == 12.0

    def test_satisfied(self):
        # importance=5, satisfaction=8 → 5 + max(0, 5-8) = 5
        assert compute_opportunity_score(5, 8) == 5.0

    def test_equal(self):
        # importance=7, satisfaction=7 → 7 + max(0, 0) = 7
        assert compute_opportunity_score(7, 7) == 7.0

    def test_max(self):
        # importance=10, satisfaction=1 → 10 + 9 = 19
        assert compute_opportunity_score(10, 1) == 19.0

    def test_min(self):
        # importance=1, satisfaction=10 → 1 + 0 = 1
        assert compute_opportunity_score(1, 10) == 1.0

    def test_out_of_range_importance(self):
        with pytest.raises(ValueError):
            compute_opportunity_score(0, 5)
        with pytest.raises(ValueError):
            compute_opportunity_score(11, 5)

    def test_out_of_range_satisfaction(self):
        with pytest.raises(ValueError):
            compute_opportunity_score(5, 0)
        with pytest.raises(ValueError):
            compute_opportunity_score(5, 11)


class TestMapOpportunityToVFE:
    def test_min(self):
        assert map_opportunity_to_vfe(1) == pytest.approx(0.0)

    def test_max(self):
        assert map_opportunity_to_vfe(20) == pytest.approx(1.0)

    def test_midpoint(self):
        assert map_opportunity_to_vfe(10.5) == pytest.approx(0.5)

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            map_opportunity_to_vfe(0)
        with pytest.raises(ValueError):
            map_opportunity_to_vfe(21)


class TestValidateOutcomeStatement:
    def test_valid_minimize(self):
        assert validate_outcome_statement(
            "Minimize the time it takes to process an order"
        ) is True

    def test_valid_maximize(self):
        assert validate_outcome_statement(
            "Maximize the accuracy of order entry"
        ) is True

    def test_invalid_no_prefix(self):
        assert validate_outcome_statement(
            "Reduce the time it takes to process an order"
        ) is False

    def test_invalid_empty(self):
        assert validate_outcome_statement("") is False

    def test_case_insensitive(self):
        assert validate_outcome_statement(
            "minimize the effort needed to verify stock"
        ) is True
