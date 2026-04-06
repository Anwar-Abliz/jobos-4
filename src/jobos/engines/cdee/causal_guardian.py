"""CDEE Causal Guardian — Structural Causal Model for Hire evaluation.

Blueprint 2 Component: The Causal Guardian.
Computes the Average Treatment Effect (ATE) of a Hire on
Imperfection reduction, adjusting for Context confounders.

Phase 1: Simple before/after estimation with effect size.
Phase 2: dowhy SCM with backdoor adjustment for confounders.
Phase 3: Neural Causal Graphs for non-linear intervenable reasoning.

Architectural Synthesis Reference:
    "A Neural Causal Graph that monitors the pipeline. It adjusts for
    'Confounders' in the 'Context' to measure the true effect of each
    'Hire' on the 'Metrics'."
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ATEResult:
    """Average Treatment Effect of a Hire on a Metric."""
    effect_estimate: float = 0.0
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    p_value: float = 1.0
    is_significant: bool = False
    method: str = "before_after"  # Phase 1: "before_after", Phase 2: "backdoor"
    reasoning: str = ""


@dataclass
class CounterfactualResult:
    """What would have happened with an alternative Hire?"""
    current_hire_id: str = ""
    alternative_hire_id: str = ""
    current_outcome: float = 0.0
    counterfactual_outcome: float = 0.0
    delta: float = 0.0  # positive = alternative is better
    confidence: float = 0.0
    reasoning: str = ""


class CausalGuardian:
    """Structural Causal Model for evaluating Hire effectiveness.

    The core question: did the Hire CAUSE the metric improvement,
    or was it coincidence/confounding?

    Phase 1: Simple before/after comparison.
        ATE = mean(metric_after_hire) - mean(metric_before_hire)
        No confounder adjustment (insufficient data).
        Returns the raw effect size with a wide confidence interval.

    Phase 2 upgrade path (via dowhy):
        Build SCM: Hire (treatment) → Metric (outcome), Context (confounders)
        Use backdoor criterion to identify adjustment sets.
        Compute ATE with propensity score matching or inverse probability weighting.

    Phase 3 upgrade path:
        Neural Causal Graph: embed entities, learn non-linear causal functions.
        Test-time intervention: manipulate concept nodes to project outcomes.
    """

    def estimate_ate(
        self,
        metric_before: list[float],
        metric_after: list[float],
    ) -> ATEResult:
        """Estimate Average Treatment Effect of a Hire.

        Phase 1: Simple difference-in-means.
        Requires at least 2 readings before and 2 after the Hire.

        Args:
            metric_before: Metric readings before the Hire (chronological).
            metric_after: Metric readings after the Hire (chronological).

        Returns:
            ATEResult with effect estimate and significance assessment.
        """
        if len(metric_before) < 2 or len(metric_after) < 2:
            return ATEResult(
                reasoning=(
                    f"Insufficient data: {len(metric_before)} before, "
                    f"{len(metric_after)} after (need >= 2 each)"
                ),
            )

        mean_before = sum(metric_before) / len(metric_before)
        mean_after = sum(metric_after) / len(metric_after)
        ate = mean_after - mean_before

        # Simple effect size (Cohen's d approximation)
        # For Phase 1, use a rough confidence interval
        n = min(len(metric_before), len(metric_after))
        se = abs(ate) / max(1, n ** 0.5)  # crude standard error
        ci_lower = ate - 1.96 * se
        ci_upper = ate + 1.96 * se

        # Significance: is the CI entirely on one side of zero?
        is_significant = (ci_lower > 0 and ci_upper > 0) or (ci_lower < 0 and ci_upper < 0)

        return ATEResult(
            effect_estimate=round(ate, 4),
            confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
            p_value=0.05 if is_significant else 0.5,  # placeholder
            is_significant=is_significant,
            method="before_after",
            reasoning=(
                f"Metric changed from {mean_before:.3f} to {mean_after:.3f} "
                f"(ATE={ate:+.3f}). "
                f"{'Statistically significant' if is_significant else 'Not yet significant'} "
                f"with {n} readings per period."
            ),
        )

    def compute_counterfactual(
        self,
        current_hire_id: str,
        alternative_hire_id: str,
        current_metric_history: list[float],
        alternative_estimated_impact: float,
    ) -> CounterfactualResult:
        """What if we had hired the alternative instead?

        Phase 1: Simple projection based on estimated_impact.
        Phase 2: Counterfactual inference via SCM do-calculus.
        Phase 3: Neural counterfactual from learned causal graph.

        This is the 'What-If' analysis from the Architectural Synthesis:
        "allows a human or another Entity to actively manipulate
        'Concept Nodes' to see how the 'Metrics' would change."
        """
        if not current_metric_history:
            return CounterfactualResult(
                current_hire_id=current_hire_id,
                alternative_hire_id=alternative_hire_id,
                reasoning="No metric history for counterfactual analysis",
            )

        current_outcome = current_metric_history[-1]
        baseline = current_metric_history[0] if len(current_metric_history) > 1 else current_outcome

        # Phase 1: project the alternative's impact onto the baseline
        counterfactual_outcome = baseline * (1.0 - alternative_estimated_impact)
        delta = counterfactual_outcome - current_outcome

        return CounterfactualResult(
            current_hire_id=current_hire_id,
            alternative_hire_id=alternative_hire_id,
            current_outcome=round(current_outcome, 4),
            counterfactual_outcome=round(counterfactual_outcome, 4),
            delta=round(delta, 4),
            confidence=0.3,  # Low confidence for Phase 1 projection
            reasoning=(
                f"With alternative hire, metric projected at "
                f"{counterfactual_outcome:.3f} vs current {current_outcome:.3f} "
                f"(delta={delta:+.3f}). Low confidence — based on estimated impact only."
            ),
        )
