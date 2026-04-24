"""JobOS 4.0 — Phase Evaluation Metrics.

Computes quality scores for each phase of the Identify-Define-Decide
loop, plus a composite end-to-end score.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from jobos.kernel.job_statement import validate_verb


class PhaseScore(BaseModel):
    """Quality score for a single phase."""
    phase: str
    score: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    reasoning: str = ""


def score_identify_phase(
    jobs: list[dict[str, Any]],
    axiom_satisfaction: dict[str, float] | None = None,
) -> PhaseScore:
    """Score the Identify phase (hierarchy generation quality).

    Components:
    - tier_coverage: fraction of tiers (T1-T4) present
    - statement_quality: fraction of statements passing verb check
    - axiom_compliance: mean axiom satisfaction (if provided)
    """
    if not jobs:
        return PhaseScore(
            phase="identify", score=0.0,
            reasoning="No jobs generated",
        )

    tiers_present = set()
    verb_pass = 0
    for j in jobs:
        tier = j.get("tier", "")
        if "T1" in str(tier) or str(tier) == "1":
            tiers_present.add(1)
        elif "T2" in str(tier) or str(tier) == "2":
            tiers_present.add(2)
        elif "T3" in str(tier) or str(tier) == "3":
            tiers_present.add(3)
        elif "T4" in str(tier) or str(tier) == "4":
            tiers_present.add(4)
        stmt = j.get("statement", "")
        if validate_verb(stmt):
            verb_pass += 1

    tier_coverage = len(tiers_present) / 4.0
    stmt_quality = verb_pass / len(jobs) if jobs else 0.0

    axiom_score = 1.0
    if axiom_satisfaction:
        vals = [v for v in axiom_satisfaction.values() if isinstance(v, (int, float))]
        axiom_score = sum(vals) / len(vals) if vals else 1.0

    score = 0.4 * tier_coverage + 0.3 * stmt_quality + 0.3 * axiom_score
    return PhaseScore(
        phase="identify",
        score=round(score, 4),
        components={
            "tier_coverage": round(tier_coverage, 4),
            "statement_quality": round(stmt_quality, 4),
            "axiom_compliance": round(axiom_score, 4),
        },
        reasoning=(
            f"{len(tiers_present)}/4 tiers present, "
            f"{verb_pass}/{len(jobs)} statements valid, "
            f"axiom compliance {axiom_score:.2f}"
        ),
    )


def score_define_phase(
    total_jobs: int,
    jobs_with_metrics: int,
    jobs_with_experience: int,
    baseline_captured: bool = False,
) -> PhaseScore:
    """Score the Define phase (outcome + metric definition quality).

    Components:
    - metric_completeness: fraction of jobs with target metrics
    - experience_coverage: fraction of jobs with experience markers
    - baseline_status: 1.0 if baseline captured, 0.0 otherwise
    """
    if total_jobs == 0:
        return PhaseScore(
            phase="define", score=0.0,
            reasoning="No jobs to evaluate",
        )

    metric_completeness = jobs_with_metrics / total_jobs
    experience_coverage = jobs_with_experience / total_jobs
    baseline_status = 1.0 if baseline_captured else 0.0

    score = (
        0.4 * metric_completeness
        + 0.3 * experience_coverage
        + 0.3 * baseline_status
    )
    return PhaseScore(
        phase="define",
        score=round(score, 4),
        components={
            "metric_completeness": round(metric_completeness, 4),
            "experience_coverage": round(experience_coverage, 4),
            "baseline_status": baseline_status,
        },
        reasoning=(
            f"{jobs_with_metrics}/{total_jobs} jobs have metrics, "
            f"{jobs_with_experience}/{total_jobs} have experience markers, "
            f"baseline {'captured' if baseline_captured else 'not captured'}"
        ),
    )


def score_decide_phase(
    verdict: str,
    vfe_trend: str = "stable",
    switch_events_count: int = 0,
    comparisons_improving: int = 0,
    comparisons_degrading: int = 0,
) -> PhaseScore:
    """Score the Decide phase (evaluation quality).

    Components:
    - verdict_quality: go=1.0, inconclusive=0.5, no_go=0.3
    - vfe_trend_quality: decreasing=1.0, stable=0.5, increasing=0.0
    - metric_direction: ratio of improving vs total compared
    """
    verdict_scores = {"go": 1.0, "inconclusive": 0.5, "no_go": 0.3}
    verdict_q = verdict_scores.get(verdict, 0.5)

    trend_scores = {"decreasing": 1.0, "stable": 0.5, "increasing": 0.0}
    trend_q = trend_scores.get(vfe_trend, 0.5)

    total_compared = comparisons_improving + comparisons_degrading
    metric_direction = (
        comparisons_improving / total_compared
        if total_compared > 0 else 0.5
    )

    score = 0.4 * verdict_q + 0.3 * trend_q + 0.3 * metric_direction
    return PhaseScore(
        phase="decide",
        score=round(score, 4),
        components={
            "verdict_quality": round(verdict_q, 4),
            "vfe_trend_quality": round(trend_q, 4),
            "metric_direction": round(metric_direction, 4),
        },
        reasoning=(
            f"Verdict={verdict}, VFE trend={vfe_trend}, "
            f"{comparisons_improving} improving / {comparisons_degrading} degrading, "
            f"{switch_events_count} switch events"
        ),
    )


def composite_score(
    identify: PhaseScore,
    define: PhaseScore,
    decide: PhaseScore,
) -> float:
    """Compute weighted composite score across all three phases."""
    return round(
        0.3 * identify.score + 0.3 * define.score + 0.4 * decide.score,
        4,
    )
