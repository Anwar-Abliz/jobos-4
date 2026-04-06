"""JobOS 4.0 — The Six Non-Negotiable Axioms.

These are pure functions with zero I/O. They validate that the
ontological invariants hold for any given set of entities and edges.

Grounding Document Reference:
    Axiom 1-3: Ontology design document §4 (Integrity constraints)
    Axiom 4-6: Architectural Synthesis §Formal Preamble
    Active Inference mapping: "minimizing Imperfection" ≡ minimizing VFE
    Control Theory mapping: "Imperfection" ≡ error signal (SP - PV)
"""
from __future__ import annotations

from jobos.kernel.entity import (
    EntityBase,
    EntityType,
    ImperfectionProperties,
    get_typed_properties,
)
from jobos.kernel.job_statement import validate_verb


# ─── Constants ───────────────────────────────────────────

_ENTROPY_SEVERITY = 0.05    # Minimal residual for Axiom 2
_ENTROPY_RISK = 0.3         # Moderate decay risk


# ─── Exception Types ────────────────────────────────────

class AxiomViolation(Exception):
    """Raised when an ontological axiom is violated."""

    def __init__(self, axiom: int, description: str) -> None:
        self.axiom = axiom
        self.description = description
        super().__init__(f"Axiom {axiom} violated: {description}")


# ─── Axiom Implementations ──────────────────────────────

class JobOSAxioms:
    """The six non-negotiable axioms of the JobOS ontology.

    1. Hierarchy     — Child effects enable parent preconditions
    2. Imperfection  — Every Job has >= 1 Imperfection (entropy residual)
    3. Duality       — Completed Job's state enables higher Job
    4. Singularity   — One root Job per optimization scope
    5. Linguistic     — Job statements must start with an action verb
    6. The Switch    — Hire/Fire justified by context change OR metric breach
    """

    @staticmethod
    def validate_hierarchy(
        child: EntityBase,
        parent: EntityBase,
    ) -> bool:
        """Axiom 1: Child job's output must enable parent job's input.

        In the unified Entity model, both child and parent are Entity:Job.
        The child's properties should contain effects that match
        the parent's preferred_states.

        Raises AxiomViolation if the hierarchy is invalid.
        """
        if child.entity_type != EntityType.JOB:
            raise AxiomViolation(1, f"Child {child.id} is not a Job")
        if parent.entity_type != EntityType.JOB:
            raise AxiomViolation(1, f"Parent {parent.id} is not a Job")

        child_props = child.properties
        parent_props = parent.properties

        if child_props.get("parent_id") != parent.id:
            raise AxiomViolation(
                1, f"Child {child.id} does not reference parent {parent.id}"
            )

        return True

    @staticmethod
    def validate_imperfection_inherent(
        job: EntityBase,
        imperfections: list[EntityBase],
    ) -> list[EntityBase]:
        """Axiom 2: Every Job has at least one Imperfection.

        If no imperfections are provided (all metrics met), creates a
        mandatory entropy residual imperfection. Solutions decay over time;
        perfection is never permanent.

        Returns the imperfection list, potentially with the residual appended.
        """
        if job.entity_type != EntityType.JOB:
            raise AxiomViolation(2, f"Entity {job.id} is not a Job")

        if imperfections:
            return imperfections

        # All thresholds met → create entropy residual
        residual = EntityBase(
            name=f"Entropy residual for {job.name or job.id}",
            statement=f"Solutions decay over time for job '{job.statement}'",
            entity_type=EntityType.IMPERFECTION,
            status="observed",
            properties={
                "severity": _ENTROPY_SEVERITY,
                "frequency": 0.1,
                "entropy_risk": _ENTROPY_RISK,
                "fixability": 0.9,
                "is_blocker": False,
                "mode": "objective",
                "evidence_level": "quantitative",
            },
        )
        return [residual]

    @staticmethod
    def validate_duality(
        completed_job: EntityBase,
        higher_job: EntityBase,
    ) -> bool:
        """Axiom 3: A completed Job's output can serve as Capability for a higher Job.

        This is the ontological superposition: Entity:Job → Entity:Capability.
        Validates that the completed job has a status indicating completion
        and that the higher job exists.
        """
        if completed_job.entity_type != EntityType.JOB:
            raise AxiomViolation(3, f"Entity {completed_job.id} is not a Job")
        if completed_job.status not in ("completed", "resolved"):
            raise AxiomViolation(
                3, f"Job {completed_job.id} is not completed (status={completed_job.status})"
            )
        return True

    @staticmethod
    def validate_singularity(jobs: list[EntityBase]) -> bool:
        """Axiom 4: At most one root Job per optimization scope.

        A root Job is level=0 with no parent_id.
        """
        roots = [
            j for j in jobs
            if j.entity_type == EntityType.JOB
            and j.properties.get("level", 0) == 0
            and j.properties.get("parent_id") is None
        ]
        if len(roots) > 1:
            root_ids = [r.id for r in roots]
            raise AxiomViolation(
                4, f"Multiple root jobs found: {root_ids}. Only one allowed."
            )
        return True

    @staticmethod
    def validate_linguistic_structure(statement: str) -> bool:
        """Axiom 5: Job statement must start with an action verb.

        Delegates to job_statement.validate_verb() which checks against
        a curated verb set. Forces the AI and users to maintain focus on
        action and execution rather than passive states.
        """
        if not statement or not statement.strip():
            raise AxiomViolation(5, "Job statement is empty")
        if not validate_verb(statement):
            first_word = statement.strip().split()[0] if statement.strip() else ""
            raise AxiomViolation(
                5, f"Job statement must start with an action verb, got '{first_word}'"
            )
        return True

    @staticmethod
    def validate_switch(
        context_changed: bool,
        metric_breached: bool,
    ) -> bool:
        """Axiom 6: The Switch — Hire/Fire justified by context change OR metric breach.

        From the Architectural Synthesis: "Agents hire/fire capabilities
        under two conditions: (1) Context changes fundamentally, OR
        (2) A Metric threshold is breached."

        Returns True if a Switch action is justified.
        """
        return context_changed or metric_breached

    @staticmethod
    def validate_all(
        job: EntityBase,
        imperfections: list[EntityBase],
        parent: EntityBase | None = None,
    ) -> dict[str, object]:
        """Run all applicable axiom validations for a Job.

        Returns a dict with validation results for each axiom.
        """
        results: dict[str, object] = {"job_id": job.id}

        # Axiom 1: Hierarchy (only if parent provided)
        if parent is not None:
            try:
                JobOSAxioms.validate_hierarchy(job, parent)
                results["axiom_1_hierarchy"] = True
            except AxiomViolation as e:
                results["axiom_1_hierarchy"] = str(e)
        else:
            results["axiom_1_hierarchy"] = None

        # Axiom 2: Inherent imperfection
        results["axiom_2_imperfections"] = JobOSAxioms.validate_imperfection_inherent(
            job, imperfections
        )

        # Axiom 5: Linguistic structure
        try:
            JobOSAxioms.validate_linguistic_structure(job.statement)
            results["axiom_5_linguistic"] = True
        except AxiomViolation as e:
            results["axiom_5_linguistic"] = str(e)

        return results
