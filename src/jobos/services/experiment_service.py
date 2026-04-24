"""JobOS 4.0 — Experiment Orchestration Service.

Manages the lifecycle of hypothesis-driven experiments:
create hypothesis -> run experiment -> record results -> derive evidence.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


class ExperimentService:
    """Orchestrates hypothesis-driven experiments."""

    def __init__(self, graph: GraphPort, db: RelationalPort) -> None:
        self._graph = graph
        self._db = db

    async def create_experiment(
        self,
        hypothesis: str,
        job_id: str,
        success_criteria: str = "",
        failure_criteria: str = "",
        method: str = "observational",
    ) -> dict[str, Any]:
        """Create a new experiment with an associated assumption entity."""
        assumption = EntityBase(
            name=f"Assumption: {hypothesis[:50]}",
            statement=hypothesis,
            entity_type=EntityType.ASSUMPTION,
            properties={
                "assumption_type": "hypothesis",
                "polarity": "positive",
                "confidence_prior": 0.5,
                "confidence_current": 0.5,
                "impact_if_false": "unknown",
            },
            provenance="system",
        )
        await self._graph.save_entity(assumption)

        if job_id:
            await self._graph.create_edge(assumption.id, job_id, "ABOUT")

        experiment_id = await self._db.save_experiment({
            "id": _uid(),
            "assumption_id": assumption.id,
            "method": method,
            "hypothesis": hypothesis,
            "success_criteria": success_criteria,
            "failure_criteria": failure_criteria,
            "results": {},
            "decision": "pending",
        })

        logger.info("Created experiment %s for job %s", experiment_id, job_id)
        return {
            "experiment_id": experiment_id,
            "assumption_id": assumption.id,
            "hypothesis": hypothesis,
            "status": "pending",
        }

    async def record_result(
        self,
        experiment_id: str,
        results: dict[str, Any],
        decision: str = "confirmed",
    ) -> dict[str, Any]:
        """Record experiment results and create evidence entity."""
        evidence = EntityBase(
            name=f"Evidence: {decision}",
            statement=f"Experiment {experiment_id}: {decision}",
            entity_type=EntityType.EVIDENCE,
            properties={
                "evidence_kind": "experimental",
                "source": f"experiment:{experiment_id}",
                "strength": results.get("confidence", 0.5),
                "measured_delta": results.get("effect_size", 0.0),
                "supports": decision == "confirmed",
            },
            provenance="system",
        )
        await self._graph.save_entity(evidence)

        edge_type = "SUPPORTS" if decision == "confirmed" else "REFUTES"
        experiments = await self._db.get_experiments(limit=100)
        for exp in experiments:
            if str(exp.get("id")) == str(experiment_id):
                assumption_id = exp.get("assumption_id", "")
                if assumption_id:
                    await self._graph.create_edge(
                        evidence.id, assumption_id, edge_type,
                    )
                break

        logger.info(
            "Recorded result for experiment %s: %s", experiment_id, decision,
        )
        return {
            "experiment_id": experiment_id,
            "evidence_id": evidence.id,
            "decision": decision,
            "results": results,
        }

    async def get_experiments(
        self,
        job_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List experiments, optionally filtered by job."""
        all_experiments = await self._db.get_experiments(limit=limit)
        if not job_id:
            return all_experiments

        # Filter by job: check if assumption is ABOUT the job
        filtered = []
        for exp in all_experiments:
            assumption_id = exp.get("assumption_id", "")
            if assumption_id:
                neighbors = await self._graph.get_neighbors(
                    assumption_id, edge_type="ABOUT", direction="outgoing",
                )
                if any(n.id == job_id for n in neighbors):
                    filtered.append(exp)
        return filtered
