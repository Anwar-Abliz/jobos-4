"""JobOS 4.0 — ODI (Outcome-Driven Innovation) Scoring (Kernel).

Pure functions for computing opportunity scores from importance/satisfaction
ratings and mapping them to VFE values. No I/O dependencies.
"""
from __future__ import annotations

import re


def compute_opportunity_score(importance: float, satisfaction: float) -> float:
    """Compute the ODI opportunity score.

    Formula: importance + max(0, importance - satisfaction)

    Both importance and satisfaction are on a 1-10 scale.
    Returns a value in [1, 20] range.

    Raises:
        ValueError: If inputs are outside [1, 10] range.
    """
    if not (1 <= importance <= 10):
        raise ValueError(f"importance must be 1-10, got {importance}")
    if not (1 <= satisfaction <= 10):
        raise ValueError(f"satisfaction must be 1-10, got {satisfaction}")
    return importance + max(0.0, importance - satisfaction)


def map_opportunity_to_vfe(opportunity_score: float) -> float:
    """Map an ODI opportunity score to a VFE value in [0, 1].

    Linear normalization: (score - 1) / 19
    Scores range from 1 (min: imp=1, sat>=1) to 20 (max: imp=10, sat=1).

    Raises:
        ValueError: If score is outside [1, 20] range.
    """
    if not (1 <= opportunity_score <= 20):
        raise ValueError(f"opportunity_score must be 1-20, got {opportunity_score}")
    return (opportunity_score - 1) / 19.0


def validate_outcome_statement(statement: str) -> bool:
    """Validate that an outcome statement follows ODI format.

    Must match: "[Minimize/Maximize] the [metric_type] ..."
    Returns True if valid.
    """
    pattern = r"^(Minimize|Maximize)\s+the\s+\w+"
    return bool(re.match(pattern, statement, re.IGNORECASE))
