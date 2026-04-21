"""JobOS 4.0 — Three Foundational Axioms (Meta-Layer).

The 8 operational axioms (axioms.py) encode specific graph invariants.
These 3 foundational axioms sit above them and represent the deep
theoretical pillars from Christensen, Ulwick, and Burleson:

    F1. Teleological Action   — Every entity exists to fulfil a purpose.
        Operational axioms 1 (Hierarchy), 4 (Singularity), 6 (Singularity+).

    F2. Mechanistic Invariance — Solutions must obey structural constraints.
        Operational axioms 2 (Imperfection), 5 (Linguistic), 8 (Market Topology).

    F3. Multidimensional Utility — Value is measured across multiple dimensions.
        Operational axioms 3 (Duality), 7 (The Switch).

This module is purely additive — the operational axioms and their scoring
are unmodified.  FoundationalSatisfaction is a read-only aggregation layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FoundationalAxiom(str, Enum):
    """The three foundational axioms."""
    F1_TELEOLOGICAL_ACTION = "f1_teleological_action"
    F2_MECHANISTIC_INVARIANCE = "f2_mechanistic_invariance"
    F3_MULTIDIMENSIONAL_UTILITY = "f3_multidimensional_utility"


# Maps each operational axiom number (1-8) to its foundational axiom.
OPERATIONAL_TO_FOUNDATIONAL: dict[int, FoundationalAxiom] = {
    1: FoundationalAxiom.F1_TELEOLOGICAL_ACTION,
    4: FoundationalAxiom.F1_TELEOLOGICAL_ACTION,
    6: FoundationalAxiom.F1_TELEOLOGICAL_ACTION,
    2: FoundationalAxiom.F2_MECHANISTIC_INVARIANCE,
    5: FoundationalAxiom.F2_MECHANISTIC_INVARIANCE,
    8: FoundationalAxiom.F2_MECHANISTIC_INVARIANCE,
    3: FoundationalAxiom.F3_MULTIDIMENSIONAL_UTILITY,
    7: FoundationalAxiom.F3_MULTIDIMENSIONAL_UTILITY,
}


@dataclass
class FoundationalSatisfaction:
    """Satisfaction scores for the 3 foundational axioms.

    Each score is the mean of its constituent operational axiom scores.
    foundational_loss = sum of (1 - score) across the three pillars (max 3.0).
    """
    f1_teleological: float = 1.0
    f2_mechanistic: float = 1.0
    f3_multidimensional: float = 1.0
    foundational_loss: float = 0.0


def compute_foundational_satisfaction(
    axiom_scores: dict[int, float],
) -> FoundationalSatisfaction:
    """Aggregate operational axiom scores into foundational satisfaction.

    Args:
        axiom_scores: Mapping of operational axiom number (1-8) to
            satisfaction score [0.0, 1.0].  Missing axioms are ignored
            (treated as not evaluated, not as violated).

    Returns:
        FoundationalSatisfaction with per-pillar means and total loss.
    """
    groups: dict[FoundationalAxiom, list[float]] = {
        FoundationalAxiom.F1_TELEOLOGICAL_ACTION: [],
        FoundationalAxiom.F2_MECHANISTIC_INVARIANCE: [],
        FoundationalAxiom.F3_MULTIDIMENSIONAL_UTILITY: [],
    }

    for axiom_num, score in axiom_scores.items():
        fa = OPERATIONAL_TO_FOUNDATIONAL.get(axiom_num)
        if fa is not None:
            groups[fa].append(score)

    def _mean(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 1.0

    f1 = _mean(groups[FoundationalAxiom.F1_TELEOLOGICAL_ACTION])
    f2 = _mean(groups[FoundationalAxiom.F2_MECHANISTIC_INVARIANCE])
    f3 = _mean(groups[FoundationalAxiom.F3_MULTIDIMENSIONAL_UTILITY])

    return FoundationalSatisfaction(
        f1_teleological=f1,
        f2_mechanistic=f2,
        f3_multidimensional=f3,
        foundational_loss=(1.0 - f1) + (1.0 - f2) + (1.0 - f3),
    )
