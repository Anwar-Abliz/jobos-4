"""JobOS 4.0 — Imperfection Service.

Derives, ranks, and enforces Axiom 2 (inherent imperfection).
"""
from __future__ import annotations

import logging

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.imperfection import (
    compute_severity,
    derive_imperfection_properties,
    rank_imperfections,
)
from jobos.kernel.axioms import JobOSAxioms
from jobos.ports.graph_port import GraphPort

logger = logging.getLogger(__name__)


class ImperfectionService:
    """Imperfection derivation, ranking, and Axiom 2 enforcement."""

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph

    async def derive_imperfections(self, job_id: str) -> list[EntityBase]:
        """Derive imperfections from unmet metric thresholds.

        For each Metric attached to the Job:
        1. Compare current_value to target_value
        2. Compute severity, frequency, entropy_risk, fixability
        3. Create or update Imperfection entity
        4. Enforce Axiom 2: if all met, create entropy residual

        Returns the list of imperfection entities.
        """
        # Get metrics for this job
        metrics = await self._graph.get_neighbors(
            job_id, edge_type="MEASURED_BY", direction="outgoing"
        )

        imperfections: list[EntityBase] = []

        for metric in metrics:
            props = metric.properties
            target = props.get("target_value")
            observed = props.get("current_value")
            direction = props.get("direction", "minimize")
            op = "<=" if direction == "minimize" else ">="

            if target is None:
                continue

            severity = compute_severity(observed, target, op)

            if severity > 0.0:
                imp_props = derive_imperfection_properties(observed, target, op)
                imp = EntityBase(
                    id=f"imp_{job_id}_{metric.id}",
                    name=f"Gap on {metric.name or metric.id}",
                    statement=(
                        f"Metric '{metric.name or metric.id}' "
                        f"(observed={observed}, target {op} {target}) is not met"
                    ),
                    entity_type=EntityType.IMPERFECTION,
                    status="observed" if observed is not None else "hypothesized",
                    properties=imp_props,
                )
                await self._graph.save_entity(imp)
                await self._graph.create_edge(imp.id, job_id, "OCCURS_IN")
                await self._graph.create_edge(imp.id, metric.id, "IMPACTS")
                imperfections.append(imp)

        # Axiom 2: ensure at least one imperfection
        job = await self._graph.get_entity(job_id)
        if job:
            imperfections = JobOSAxioms.validate_imperfection_inherent(
                job, imperfections
            )
            # If the axiom added an entropy residual, persist it
            for imp in imperfections:
                if imp.properties.get("entropy_risk", 0) == 0.3 and imp.properties.get("severity", 0) == 0.05:
                    await self._graph.save_entity(imp)
                    await self._graph.create_edge(imp.id, job_id, "OCCURS_IN")

        logger.info("Derived %d imperfections for job %s", len(imperfections), job_id)
        return imperfections

    async def rank(self, job_id: str) -> list[EntityBase]:
        """Return imperfections for a Job, ranked by IPS (highest first)."""
        imperfections = await self._graph.get_neighbors(
            job_id, edge_type="OCCURS_IN", direction="incoming"
        )
        return rank_imperfections(imperfections)

    async def get_top_blocker(self, job_id: str) -> EntityBase | None:
        """Get the highest-priority blocker for a Job."""
        ranked = await self.rank(job_id)
        if not ranked:
            return None
        # Return first blocker, or first imperfection if none are blockers
        for imp in ranked:
            if imp.properties.get("is_blocker", False):
                return imp
        return ranked[0] if ranked else None
