"""Tests for the 3 Foundational Axioms meta-layer.

Covers:
- OPERATIONAL_TO_FOUNDATIONAL mapping completeness
- F1, F2, F3 groupings
- compute_foundational_satisfaction with all-satisfied, all-violated, partial, missing
"""
from __future__ import annotations

import pytest

from jobos.kernel.foundational_axioms import (
    FoundationalAxiom,
    FoundationalSatisfaction,
    OPERATIONAL_TO_FOUNDATIONAL,
    compute_foundational_satisfaction,
)


class TestOperationalMapping:
    def test_all_8_operational_axioms_mapped(self):
        """Every operational axiom (1-8) maps to exactly one foundational axiom."""
        for ax_num in range(1, 9):
            assert ax_num in OPERATIONAL_TO_FOUNDATIONAL, (
                f"Operational axiom {ax_num} missing from mapping"
            )

    def test_f1_groups_axioms_1_4_6(self):
        f1_axioms = [
            k for k, v in OPERATIONAL_TO_FOUNDATIONAL.items()
            if v == FoundationalAxiom.F1_TELEOLOGICAL_ACTION
        ]
        assert sorted(f1_axioms) == [1, 4, 6]

    def test_f2_groups_axioms_2_5_8(self):
        f2_axioms = [
            k for k, v in OPERATIONAL_TO_FOUNDATIONAL.items()
            if v == FoundationalAxiom.F2_MECHANISTIC_INVARIANCE
        ]
        assert sorted(f2_axioms) == [2, 5, 8]

    def test_f3_groups_axioms_3_7(self):
        f3_axioms = [
            k for k, v in OPERATIONAL_TO_FOUNDATIONAL.items()
            if v == FoundationalAxiom.F3_MULTIDIMENSIONAL_UTILITY
        ]
        assert sorted(f3_axioms) == [3, 7]

    def test_each_axiom_maps_to_exactly_one(self):
        """No operational axiom appears in more than one foundational group."""
        seen: set[int] = set()
        for ax_num in OPERATIONAL_TO_FOUNDATIONAL:
            assert ax_num not in seen, f"Axiom {ax_num} mapped twice"
            seen.add(ax_num)


class TestComputeFoundationalSatisfaction:
    def test_all_satisfied(self):
        scores = {i: 1.0 for i in range(1, 9)}
        result = compute_foundational_satisfaction(scores)
        assert result.f1_teleological == 1.0
        assert result.f2_mechanistic == 1.0
        assert result.f3_multidimensional == 1.0
        assert abs(result.foundational_loss) < 1e-9

    def test_all_violated(self):
        scores = {i: 0.0 for i in range(1, 9)}
        result = compute_foundational_satisfaction(scores)
        assert result.f1_teleological == 0.0
        assert result.f2_mechanistic == 0.0
        assert result.f3_multidimensional == 0.0
        assert abs(result.foundational_loss - 3.0) < 1e-9

    def test_partial_satisfaction(self):
        # F1 (axioms 1,4,6): mean(1.0, 0.0, 1.0) = 2/3
        # F2 (axioms 2,5,8): mean(0.5, 0.5, 0.5) = 0.5
        # F3 (axioms 3,7):   mean(0.8, 0.2) = 0.5
        scores = {
            1: 1.0, 4: 0.0, 6: 1.0,
            2: 0.5, 5: 0.5, 8: 0.5,
            3: 0.8, 7: 0.2,
        }
        result = compute_foundational_satisfaction(scores)
        assert abs(result.f1_teleological - 2 / 3) < 1e-9
        assert abs(result.f2_mechanistic - 0.5) < 1e-9
        assert abs(result.f3_multidimensional - 0.5) < 1e-9

        expected_loss = (1 - 2 / 3) + (1 - 0.5) + (1 - 0.5)
        assert abs(result.foundational_loss - expected_loss) < 1e-9

    def test_missing_axioms_default_to_satisfied(self):
        """If no operational scores are provided, foundational defaults to 1.0."""
        result = compute_foundational_satisfaction({})
        assert result.f1_teleological == 1.0
        assert result.f2_mechanistic == 1.0
        assert result.f3_multidimensional == 1.0
        assert abs(result.foundational_loss) < 1e-9

    def test_partial_missing_axioms(self):
        # Only axiom 1 provided (F1 group) → F1 = 0.3, others default 1.0
        result = compute_foundational_satisfaction({1: 0.3})
        assert abs(result.f1_teleological - 0.3) < 1e-9
        assert result.f2_mechanistic == 1.0
        assert result.f3_multidimensional == 1.0

    def test_unknown_axiom_numbers_ignored(self):
        """Axiom numbers outside 1-8 are silently ignored."""
        scores = {99: 0.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0}
        result = compute_foundational_satisfaction(scores)
        assert abs(result.foundational_loss) < 1e-9

    def test_returns_dataclass_instance(self):
        result = compute_foundational_satisfaction({})
        assert isinstance(result, FoundationalSatisfaction)
