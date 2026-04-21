"""NSAIG Belief Engine — Symbolic axiom evaluation.

Blueprint 1 Component: The Belief Engine (LTN placeholder).
Maintains the ontological truth state by evaluating whether the
current graph satisfies the 6 axioms.

Phase 1: Rule-based evaluation returning satisfaction scores.
Phase 3 hook: Replace with Logic Tensor Network (LTN) where axioms
              become differentiable loss functions for gradient descent.

Architectural Synthesis Reference:
    "A Logic Tensor Network that maintains the 'Foundational Ontology.'
    It encodes 'Jobs' and 'Capabilities' as symbolic axioms and
    'Hires' as grounded predicates."
"""
from __future__ import annotations

from dataclasses import dataclass, field

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.axioms import JobOSAxioms, AxiomViolation
from jobos.kernel.foundational_axioms import (
    FoundationalSatisfaction,
    compute_foundational_satisfaction,
)


@dataclass
class AxiomSatisfaction:
    """Satisfaction scores for each axiom. 1.0 = fully satisfied."""
    axiom_1_hierarchy: float = 1.0
    axiom_2_imperfection: float = 1.0
    axiom_3_contextual: float = 1.0
    axiom_4_singularity: float = 1.0
    axiom_5_linguistic: float = 1.0
    axiom_6_root_token: float = 1.0
    logic_loss: float = 0.0  # Aggregate violation score
    foundational: FoundationalSatisfaction | None = None


class BeliefEngine:
    """Symbolic axiom evaluator — the Phase 1 'LTN placeholder'.

    Evaluates whether the current entity graph satisfies the 6 axioms.
    Returns violation scores that feed into VFE computation.

    In Phase 3, this becomes a differentiable LTN where:
    - Entities are vectors in d-dimensional space
    - Predicates (Hires, Minimizes) are neural networks outputting truth values
    - Logic Loss = aggregate axiom dissatisfaction
    - Gradient of Logic Loss updates Entity embeddings
    """

    def evaluate_axioms(
        self,
        jobs: list[EntityBase],
        imperfections_by_job: dict[str, list[EntityBase]] | None = None,
        *,
        scope_id: str | None = None,
    ) -> AxiomSatisfaction:
        """Evaluate all applicable axioms over a set of Job entities.

        Returns satisfaction scores [0, 1] for each axiom.
        Lower score = more violation = higher Logic Loss.
        """
        imperfections_by_job = imperfections_by_job or {}
        result = AxiomSatisfaction()

        # Axiom 3: Contextual variance — HUMAN jobs require context
        contextual_scores = []
        for job in jobs:
            if job.entity_type != EntityType.JOB:
                continue
            try:
                JobOSAxioms.validate_contextual_variance(job)
                contextual_scores.append(1.0)
            except AxiomViolation:
                contextual_scores.append(0.0)
        if contextual_scores:
            result.axiom_3_contextual = sum(contextual_scores) / len(contextual_scores)

        # Axiom 4: Singularity — at most one root Job
        try:
            JobOSAxioms.validate_singularity(jobs)
            result.axiom_4_singularity = 1.0
        except AxiomViolation:
            result.axiom_4_singularity = 0.0

        # Axiom 5: Linguistic structure — all Jobs must start with verb
        linguistic_scores = []
        for job in jobs:
            if job.entity_type != EntityType.JOB:
                continue
            try:
                JobOSAxioms.validate_linguistic_structure(job.statement)
                linguistic_scores.append(1.0)
            except AxiomViolation:
                linguistic_scores.append(0.0)
        if linguistic_scores:
            result.axiom_5_linguistic = sum(linguistic_scores) / len(linguistic_scores)

        # Axiom 6: root_token uniqueness per scope_id
        if scope_id is not None:
            try:
                JobOSAxioms.validate_root_token(jobs, scope_id)
                result.axiom_6_root_token = 1.0
            except AxiomViolation:
                result.axiom_6_root_token = 0.0

        # Axiom 2: Inherent imperfection — every Job must have >= 1
        imperfection_scores = []
        for job in jobs:
            if job.entity_type != EntityType.JOB:
                continue
            imps = imperfections_by_job.get(job.id, [])
            # If job has imperfections, axiom is satisfied
            imperfection_scores.append(1.0 if imps else 0.0)
        if imperfection_scores:
            result.axiom_2_imperfection = (
                sum(imperfection_scores) / len(imperfection_scores)
            )

        # Compute aggregate Logic Loss
        result.logic_loss = self.compute_logic_loss(result)

        # Compute foundational axiom satisfaction (meta-layer)
        result.foundational = self.evaluate_foundational(result)

        return result

    def evaluate_foundational(
        self, scores: AxiomSatisfaction,
    ) -> FoundationalSatisfaction:
        """Aggregate the 6 evaluated operational axiom scores into 3 foundational pillars.

        Operational axiom 7 (Switch) and 8 (Market Topology) are not directly
        evaluated by BeliefEngine, so they default to 1.0 in the mapping.
        """
        operational_scores: dict[int, float] = {
            1: scores.axiom_1_hierarchy,
            2: scores.axiom_2_imperfection,
            3: scores.axiom_3_contextual,
            4: scores.axiom_4_singularity,
            5: scores.axiom_5_linguistic,
            6: scores.axiom_6_root_token,
            # 7 and 8 are not evaluated by BeliefEngine; default to 1.0
            7: 1.0,
            8: 1.0,
        }
        return compute_foundational_satisfaction(operational_scores)

    def compute_logic_loss(self, scores: AxiomSatisfaction) -> float:
        """Aggregate axiom violations into a single 'Logic Loss'.

        Logic Loss = sum of (1 - satisfaction) for each axiom.
        0.0 = all axioms satisfied. Max = 6.0 (all 6 axioms violated).

        Phase 3: This becomes the differentiable loss function
        for LTN training: minimize Logic Loss via gradient descent
        on Entity embeddings and predicate weights.
        """
        return (
            (1.0 - scores.axiom_1_hierarchy)
            + (1.0 - scores.axiom_2_imperfection)
            + (1.0 - scores.axiom_3_contextual)
            + (1.0 - scores.axiom_4_singularity)
            + (1.0 - scores.axiom_5_linguistic)
            + (1.0 - scores.axiom_6_root_token)
        )
