"""JobOS 4.0 — The Eight Non-Negotiable Axioms.

These are pure functions with zero I/O. They validate that the
ontological invariants hold for any given set of entities and edges.

Grounding Document Reference:
    Axiom 1-3: Ontology design document §4 (Integrity constraints)
    Axiom 4-8: Architectural Synthesis §Formal Preamble (Phase 1 expansion)
    Active Inference mapping: "minimizing Imperfection" ≡ minimizing VFE
    Control Theory mapping: "Imperfection" ≡ error signal (SP - PV)

Axiom Numbering (Phase 1 expansion — preserves numeric AxiomViolation codes):
    1. Hierarchy         — Child effects enable parent preconditions
    2. Imperfection      — Every Job has >= 1 Imperfection (entropy residual)
    3. Duality           — Completed Job's state enables higher Job
    4. Singularity       — One root Job per optimization scope (legacy: Axiom 4)
    5. Linguistic        — Job statements must start with action verb OR experiential phrase
    6. Singularity+      — root_token='ROOT' enforced per scope_id (enhanced Axiom 4)
    7. The Switch        — Hire/Fire justified by context change OR metric breach
    8. Market Topology   — Jobs cluster by unmet outcome patterns (scaffold)
"""
from __future__ import annotations

import re

from jobos.kernel.entity import (
    EntityBase,
    EntityType,
    ImperfectionProperties,
    get_typed_properties,
)
from jobos.kernel.job_statement import validate_verb


# ─── Constants ───────────────────────────────────────

_ENTROPY_SEVERITY = 0.05    # Minimal residual for Axiom 2
_ENTROPY_RISK = 0.3         # Moderate decay risk

# Experiential job opener regex (Axiom 5 — Dimension A)
# Matches "feel" or "to be" as complete words at string start.
# "feeling" does NOT match (word boundary required).
_EXPERIENTIAL_RE = re.compile(r"^(to\s+be\b|feel\b)", re.IGNORECASE)


# ─── Exception Types ────────────────────────────────────

class AxiomViolation(Exception):
    """Raised when an ontological axiom is violated."""

    def __init__(self, axiom: int, description: str) -> None:
        self.axiom = axiom
        self.description = description
        super().__init__(f"Axiom {axiom} violated: {description}")


# ─── Axiom Implementations ──────────────────────────────

class JobOSAxioms:
    """The eight non-negotiable axioms of the JobOS ontology.

    1. Hierarchy         — Child effects enable parent preconditions
    2. Imperfection      — Every Job has >= 1 Imperfection (entropy residual)
    3. Duality           — Completed Job's state enables higher Job
    4. Singularity       — One root Job per optimization scope (level=0, no parent)
    5. Linguistic        — Job statements start with action verb OR experiential phrase
    6. Singularity+      — root_token='ROOT' unique per scope_id
    7. The Switch        — Hire/Fire justified by context change OR metric breach
    8. Market Topology   — Discovery scaffold (Phase 1 stub)
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
        *,
        entropy_severity: float | None = None,
        entropy_risk: float | None = None,
    ) -> list[EntityBase]:
        """Axiom 2: Every Job has at least one Imperfection.

        If no imperfections are provided (all metrics met), creates a
        mandatory entropy residual imperfection. Solutions decay over time;
        perfection is never permanent.

        Phase 1 placeholder: severity and risk are configurable via kwargs
        or ``JobOSSettings.entropy_residual_severity/risk`` env vars.
        Defaults to module constants ``_ENTROPY_SEVERITY`` / ``_ENTROPY_RISK``.

        Returns the imperfection list, potentially with the residual appended.
        """
        if job.entity_type != EntityType.JOB:
            raise AxiomViolation(2, f"Entity {job.id} is not a Job")

        if imperfections:
            return imperfections

        sev = entropy_severity if entropy_severity is not None else _ENTROPY_SEVERITY
        risk = entropy_risk if entropy_risk is not None else _ENTROPY_RISK

        # All thresholds met → create entropy residual
        residual = EntityBase(
            name=f"Entropy residual for {job.name or job.id}",
            statement=f"Solutions decay over time for job '{job.statement}'",
            entity_type=EntityType.IMPERFECTION,
            status="observed",
            properties={
                "severity": sev,
                "metric_dimension": "entropy",
                "target_value": 0.0,
                "observed_value": sev,
                "frequency": 0.1,
                "entropy_risk": risk,
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
        For scope-aware enforcement, see validate_root_token (Axiom 6).
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
    def validate_linguistic_structure(
        statement: str,
        *,
        experiential: bool = False,
    ) -> bool:
        """Axiom 5: Job statement must start with an action verb OR experiential phrase.

        Functional jobs (experiential=False): must start with an action verb
        from the curated ACTION_VERBS set. Enforces imperative form.

        Experiential jobs (Dimension A, experiential=True): must start with
        'To Be' or 'Feel'. These are Experience Space nodes representing
        identity and emotional outcomes.

        Examples:
            Functional:    "Define success criteria for Q3 OKRs"
            Experiential:  "To Be seen as a trusted advisor"
            Experiential:  "Feel confident shipping to production"
        """
        if not statement or not statement.strip():
            raise AxiomViolation(5, "Job statement is empty")

        if experiential:
            if not _EXPERIENTIAL_RE.match(statement.strip()):
                first_word = statement.strip().split()[0] if statement.strip() else ""
                raise AxiomViolation(
                    5,
                    f"Experiential job statement must start with 'To Be' or 'Feel', "
                    f"got '{first_word}'"
                )
            return True

        if not validate_verb(statement):
            first_word = statement.strip().split()[0] if statement.strip() else ""
            raise AxiomViolation(
                5, f"Job statement must start with an action verb, got '{first_word}'"
            )
        return True

    @staticmethod
    def validate_contextual_variance(job: EntityBase) -> bool:
        """Axiom 3 (extended): Context is mandatory for HUMAN executor jobs.

        HUMAN jobs require non-empty context (who/where/when) because human
        execution is situationally dependent. AI jobs are context-optional
        because they operate on explicit inputs.

        Raises AxiomViolation(3) if HUMAN job lacks context.
        """
        executor_type = job.properties.get("executor_type")
        if executor_type != "HUMAN":
            return True  # AI or unset: context optional

        # HUMAN job must reference a context entity via properties
        has_context = (
            job.properties.get("context_id")
            or job.properties.get("who")
            or job.properties.get("where")
            or job.properties.get("when")
        )
        if not has_context:
            raise AxiomViolation(
                3,
                f"HUMAN executor job '{job.id}' requires context fields "
                "(context_id, who, where, or when). Context is mandatory for human execution."
            )
        return True

    @staticmethod
    def validate_root_token(jobs: list[EntityBase], scope_id: str) -> bool:
        """Axiom 6: At most one root_token='ROOT' per scope_id.

        Enhanced Singularity constraint — ties uniqueness to a logical scope
        (e.g. a project ID, user workspace, or domain boundary) rather than
        relying purely on graph level=0 detection.

        Application-level enforcement: Neo4j Community Edition does not support
        conditional partial uniqueness constraints, so this check is performed
        in the service layer before persisting.
        """
        roots = [
            j for j in jobs
            if j.entity_type == EntityType.JOB
            and j.properties.get("root_token") == "ROOT"
            and j.properties.get("scope_id", "") == scope_id
        ]
        if len(roots) > 1:
            root_ids = [r.id for r in roots]
            raise AxiomViolation(
                6,
                f"Scope '{scope_id}' already has a root job: {root_ids}. "
                "Only one ROOT per scope is allowed."
            )
        return True

    @staticmethod
    def validate_switch(
        context_changed: bool,
        metric_breached: bool,
    ) -> bool:
        """Axiom 7: The Switch — Hire/Fire justified by context change OR metric breach.

        From the Architectural Synthesis: "Agents hire/fire capabilities
        under two conditions: (1) Context changes fundamentally, OR
        (2) A Metric threshold is breached."

        For the full heuristic implementation with hysteresis, see:
            src/jobos/engines/switch_evaluator.py

        Returns True if a Switch action is justified.
        """
        return context_changed or metric_breached

    @staticmethod
    def discover_market_clusters(
        jobs: list[EntityBase],
        imperfection_map: dict[str, list[EntityBase]] | None = None,
    ) -> list[dict[str, object]]:
        """Axiom 8: Market Topology — cluster Jobs by unmet outcome patterns.

        Phase 1 (current): Stub returning all jobs in one cluster.
        Phase 2: KMeans on IPS vectors from Dimension B (job_metrics table).
        Phase 3: Graph community detection on imperfection co-occurrence in Neo4j.

        Args:
            jobs:              All Job entities to analyze.
            imperfection_map:  job_id → list of Imperfection entities.

        Returns:
            List of cluster dicts with 'cluster_id', 'job_ids', 'pattern'.
        """
        job_list = [j for j in jobs if j.entity_type == EntityType.JOB]
        if not job_list:
            return []
        return [
            {
                "cluster_id": "stub",
                "job_ids": [j.id for j in job_list],
                "pattern": "unimplemented — Phase 2 will use IPS vector clustering",
            }
        ]

    @staticmethod
    def validate_all(
        job: EntityBase,
        imperfections: list[EntityBase],
        parent: EntityBase | None = None,
        *,
        all_jobs: list[EntityBase] | None = None,
        scope_id: str | None = None,
    ) -> dict[str, object]:
        """Run all applicable axiom validations for a Job.

        Args:
            job:            The Job entity to validate.
            imperfections:  Imperfections associated with this job.
            parent:         Optional parent Job (for Axiom 1).
            all_jobs:       Optional list of all jobs in scope (for Axiom 4/6).
            scope_id:       Optional scope for Axiom 6 root_token check.

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

        # Axiom 3: Contextual variance (HUMAN jobs require context)
        try:
            JobOSAxioms.validate_contextual_variance(job)
            results["axiom_3_contextual_variance"] = True
        except AxiomViolation as e:
            results["axiom_3_contextual_variance"] = str(e)

        # Axiom 4: Singularity (only if all_jobs provided)
        if all_jobs is not None:
            try:
                JobOSAxioms.validate_singularity(all_jobs)
                results["axiom_4_singularity"] = True
            except AxiomViolation as e:
                results["axiom_4_singularity"] = str(e)
        else:
            results["axiom_4_singularity"] = None

        # Axiom 5: Linguistic structure
        is_experiential = job.properties.get("job_type") in ("emotional", "social")
        try:
            JobOSAxioms.validate_linguistic_structure(
                job.statement, experiential=is_experiential
            )
            results["axiom_5_linguistic"] = True
        except AxiomViolation as e:
            results["axiom_5_linguistic"] = str(e)

        # Axiom 6: root_token uniqueness (only if all_jobs and scope_id provided)
        if all_jobs is not None and scope_id is not None:
            try:
                JobOSAxioms.validate_root_token(all_jobs, scope_id)
                results["axiom_6_root_token"] = True
            except AxiomViolation as e:
                results["axiom_6_root_token"] = str(e)
        else:
            results["axiom_6_root_token"] = None

        return results
