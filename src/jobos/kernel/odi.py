"""JobOS 4.0 — ODI (Outcome-Driven Innovation) Scoring (Kernel).

Pure functions for computing opportunity scores from importance/satisfaction
ratings, mapping them to VFE values, classifying opportunities, and
generating outcome discovery prompts. No I/O dependencies.
"""
from __future__ import annotations

import re
from typing import Any

from jobos.kernel.entity import EntityBase


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
        raise ValueError(
            f"opportunity_score must be 1-20, got {opportunity_score}"
        )
    return (opportunity_score - 1) / 19.0


def validate_outcome_statement(statement: str) -> bool:
    """Validate that an outcome statement follows ODI format.

    Must match: "[Minimize/Maximize] the [metric_type] ..."
    Returns True if valid.
    """
    pattern = r"^(Minimize|Maximize)\s+the\s+\w+"
    return bool(re.match(pattern, statement, re.IGNORECASE))


# ─── Opportunity Thresholds ─────────────────────────────

OPPORTUNITY_THRESHOLDS: dict[str, float] = {
    "overserved": 5.0,
    "appropriately_served_upper": 10.0,
    "underserved": 10.0,
}


def classify_opportunity(score: float) -> str:
    """Classify an opportunity score into market segments.

    Returns: "overserved", "appropriately_served", or "underserved"
    """
    if score < OPPORTUNITY_THRESHOLDS["overserved"]:
        return "overserved"
    elif score >= OPPORTUNITY_THRESHOLDS["underserved"]:
        return "underserved"
    else:
        return "appropriately_served"


# ─── Outcome Discovery Prompts ──────────────────────────

OUTCOME_DISCOVERY_PROMPT = """You are an ODI (Outcome-Driven Innovation) \
analyst. Generate desired outcome statements that customers would use to \
evaluate how well this job is done.

Each outcome MUST follow the format:
"[Minimize/Maximize] the [metric_type] it takes to [action] when [context]"

Metric types: time, cost, likelihood of error, effort, variability, accuracy

Generate {count} outcomes grouped by execution context.
Match the user's language.

Respond with JSON:
{{
  "outcomes": [
    {{
      "statement": "Minimize the time it takes to ...",
      "direction": "minimize",
      "metric_type": "time",
      "context": "when ..."
    }}
  ]
}}"""


def generate_outcome_prompt(
    job: EntityBase,
    tier: int = 2,
    count: int = 10,
) -> str:
    """Build an LLM prompt for outcome discovery for a specific job."""
    tier_labels = {
        1: "strategic goal",
        2: "core functional job",
        3: "execution step",
        4: "micro-task",
    }
    tier_label = tier_labels.get(tier, "job")

    return (
        OUTCOME_DISCOVERY_PROMPT.format(count=count)
        + f"\n\nJob ({tier_label}): \"{job.statement}\""
    )


def template_outcomes(
    domain: str,
    count: int = 9,
) -> list[dict[str, Any]]:
    """Generate template outcomes when LLM is unavailable.

    Returns 3 contexts x 3 outcomes each.
    """
    contexts = ["during planning", "during execution", "during review"]
    metric_types = ["time", "likelihood of error", "effort"]
    outcomes: list[dict[str, Any]] = []

    for i, ctx in enumerate(contexts):
        for j, mt in enumerate(metric_types):
            direction = "minimize"
            outcomes.append({
                "statement": (
                    f"Minimize the {mt} it takes to complete "
                    f"{domain} tasks {ctx}"
                ),
                "direction": direction,
                "metric_type": mt,
                "context": ctx,
            })
            if len(outcomes) >= count:
                return outcomes

    return outcomes
