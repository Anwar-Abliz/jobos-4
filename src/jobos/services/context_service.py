"""JobOS 4.0 — Context Service.

Manages context capture, freshness detection, and coverage analysis.
Addresses "how to realize context beyond static knowledge at scale."
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


class ContextService:
    """Context management service."""

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort,
        llm: Any | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._llm = llm

    async def capture_context_snapshot(self, entity_id: str) -> dict[str, Any]:
        """Freeze current state of entity + neighbors (fully automated)."""
        entity = await self._graph.get_entity(entity_id)
        if not entity:
            return {"error": "entity not found"}

        neighbors = await self._graph.get_neighbors(entity_id, direction="both")
        edges = await self._graph.get_edges(entity_id, direction="both")

        snapshot_data = {
            "entity": entity.model_dump(mode="json"),
            "neighbors": [n.model_dump(mode="json") for n in neighbors],
            "edges": edges,
            "captured_at": datetime.now(UTC).isoformat(),
        }

        snapshot_id = await self._db.save_context_snapshot(
            entity_id=entity_id,
            snapshot_data=snapshot_data,
        )

        return {"snapshot_id": snapshot_id, "entity_id": entity_id}

    async def detect_context_decay(
        self,
        entity_id: str,
        threshold_hours: float = 24.0,
    ) -> dict[str, Any]:
        """Check if context is stale based on timestamps (fully automated)."""
        snapshots = await self._db.get_context_snapshots(entity_id, limit=1)

        if not snapshots:
            return {
                "entity_id": entity_id,
                "stale": True,
                "reason": "no snapshots found",
                "freshness": "stale",
            }

        latest = snapshots[0]
        captured_at = latest.get("captured_at")
        if isinstance(captured_at, str):
            captured_at = datetime.fromisoformat(captured_at)

        age = datetime.now(UTC) - captured_at
        is_stale = age > timedelta(hours=threshold_hours)

        freshness = "stale" if is_stale else "snapshot"
        if age < timedelta(hours=1):
            freshness = "live"

        return {
            "entity_id": entity_id,
            "stale": is_stale,
            "age_hours": round(age.total_seconds() / 3600, 2),
            "freshness": freshness,
            "threshold_hours": threshold_hours,
        }

    async def infer_relationships(self, entity_id: str) -> dict[str, Any]:
        """Discover missing edges from entity properties (LLM-assisted)."""
        entity = await self._graph.get_entity(entity_id)
        if not entity:
            return {"error": "entity not found", "inferred": []}

        if not self._llm:
            return {
                "entity_id": entity_id,
                "inferred": [],
                "note": "LLM not available — skipping inference",
            }

        # LLM inference would go here
        return {
            "entity_id": entity_id,
            "inferred": [],
            "note": "LLM inference placeholder",
        }

    async def compute_context_coverage(self, scope_id: str) -> dict[str, Any]:
        """Compute % of process steps with mapped context (fully automated)."""
        entities = await self._graph.list_entities(
            entity_type="sap_process", limit=500
        )

        total_steps = 0
        covered_steps = 0

        for entity in entities:
            neighbors = await self._graph.get_neighbors(entity.id, direction="outgoing")
            steps = [
                n for n in neighbors
                if n.entity_type.value == "sap_transaction"
            ]
            total_steps += len(steps)

            for step in steps:
                step_neighbors = await self._graph.get_neighbors(
                    step.id, direction="both"
                )
                if len(step_neighbors) > 1:  # has context beyond just the parent
                    covered_steps += 1

        coverage = covered_steps / total_steps if total_steps > 0 else 0.0

        return {
            "scope_id": scope_id,
            "total_steps": total_steps,
            "covered_steps": covered_steps,
            "coverage_pct": round(coverage * 100, 2),
        }

    async def merge_context_updates(
        self,
        entity_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply incremental updates from data sources (fully automated)."""
        entity = await self._graph.get_entity(entity_id)
        if not entity:
            return {"error": "entity not found"}

        # Merge properties
        entity.properties.update(updates)
        entity.updated_at = datetime.now(UTC)
        await self._graph.save_entity(entity)

        return {"entity_id": entity_id, "updated_fields": list(updates.keys())}
