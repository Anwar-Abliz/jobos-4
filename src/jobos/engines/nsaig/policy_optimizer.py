"""NSAIG Policy Optimizer — Active Inference (discrete POMDP).

Blueprint 1 Component: The Policy Optimizer.
Selects which Entity to Hire based on Expected Free Energy (EFE).

Phase 1: Simplified VFE computation (weighted metric deviations).
         Policy selection via greedy EFE minimization over candidates.
Phase 2: pymdp POMDP with learned state-action-observation matrices.
Phase 3: Continuous-state AIF via RxInfer.jl microservice.

CTO Decision 1: "Option A+ — Symbolic with differentiable hook."
    The interface is designed so pymdp can be swapped for RxInfer
    without re-architecting the service boundary.

Architectural Synthesis Reference:
    "An EFE-minimization module that selects the next 'Hire.'
    It treats the GAT embeddings as the state representation s
    and searches for a policy π that maximizes 'Progress'."
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PolicyResult:
    """Result of policy selection."""
    recommended_hiree_id: str | None = None
    efe_score: float = float("inf")  # Lower = better
    vfe_current: float = 0.0
    policy_confidence: float = 0.0
    reasoning: str = ""
    alternatives: list[dict] = field(default_factory=list)


class PolicyOptimizer:
    """Active Inference policy selection — discrete state-space.

    Phase 1 implementation:
        VFE = weighted sum of |target - observed| / |target| for each metric.
        EFE = VFE_expected_after_action (estimated from capability impact).
        Policy = hire the candidate with lowest EFE.

    Phase 2 upgrade path:
        Replace _compute_vfe and _compute_efe with pymdp.Agent methods.
        States = discretized severity levels per metric.
        Actions = available capability entity IDs.
        Observations = metric reading values.

    Phase 3 upgrade path:
        Replace entire class with HTTP call to RxInfer.jl microservice.
        Interface (select_policy, compute_vfe) remains identical.
    """

    def select_policy(
        self,
        current_metrics: dict[str, dict],
        candidates: list[dict],
        job_preferred_states: list[str] | None = None,
    ) -> PolicyResult:
        """Select the hiring action that minimizes Expected Free Energy.

        Args:
            current_metrics: {metric_id: {"observed": float, "target": float, "op": str}}
            candidates: [{"id": str, "estimated_impact": float, "name": str}]
            job_preferred_states: optional list of preferred state predicates

        Returns:
            PolicyResult with recommended hiree and EFE score.
        """
        if not candidates:
            return PolicyResult(reasoning="No candidates available")

        vfe_current = self.compute_vfe(current_metrics)

        # Score each candidate by estimated EFE after hiring
        scored: list[tuple[float, dict]] = []
        for candidate in candidates:
            impact = candidate.get("estimated_impact", 0.0)
            # EFE = estimated VFE after action
            # Simplified: reduce current VFE by the candidate's estimated impact
            efe = vfe_current * (1.0 - impact)
            scored.append((efe, candidate))

        scored.sort(key=lambda x: x[0])

        best_efe, best_candidate = scored[0]
        confidence = max(0.0, min(1.0, 1.0 - best_efe)) if vfe_current > 0 else 0.5

        alternatives = [
            {"id": c["id"], "name": c.get("name", ""), "efe": round(efe, 4)}
            for efe, c in scored[1:4]  # top 3 alternatives
        ]

        return PolicyResult(
            recommended_hiree_id=best_candidate["id"],
            efe_score=round(best_efe, 4),
            vfe_current=round(vfe_current, 4),
            policy_confidence=round(confidence, 4),
            reasoning=(
                f"Hiring '{best_candidate.get('name', best_candidate['id'])}' "
                f"minimizes EFE from {vfe_current:.3f} to {best_efe:.3f}"
            ),
            alternatives=alternatives,
        )

    def compute_vfe(self, metrics: dict[str, dict]) -> float:
        """Compute Variational Free Energy for a Job.

        VFE = weighted average of metric deviations from targets.

        Phase 1 approximation:
            VFE = mean( |target - observed| / |target| ) for all metrics
            This is the 'Imperfection as Surprise' — how far is reality
            from the generative model's (Job's) preferred states.

        Phase 2: Replace with proper KL divergence computation
                 between posterior beliefs and preferred states.
        Phase 3: Full VFE = E_q[log q(s) - log p(o,s)] via RxInfer.

        Args:
            metrics: {metric_id: {"observed": float|None, "target": float, "op": str}}

        Returns:
            VFE score in [0.0, 1.0]. 0.0 = no surprise (all met).
        """
        if not metrics:
            return 0.0

        deviations = []
        for metric_id, m in metrics.items():
            observed = m.get("observed")
            target = m.get("target")

            if target is None:
                continue

            if observed is None:
                deviations.append(1.0)  # Missing data = maximum surprise
                continue

            if abs(target) < 1e-9:
                deviations.append(min(1.0, abs(observed)))
            else:
                deviations.append(min(1.0, abs(target - observed) / abs(target)))

        if not deviations:
            return 0.0

        return sum(deviations) / len(deviations)
