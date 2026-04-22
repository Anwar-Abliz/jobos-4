"""JobOS 4.0 — Decision Service.

Records decisions with full tracing, reconstructs decision trails,
and generates explanations.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.decision_trace import DecisionTrace
from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


class DecisionService:
    """Decision recording and tracing service."""

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort,
        llm: Any | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._llm = llm

    async def record_decision(
        self,
        actor: str,
        action: str,
        target_entity_id: str,
        rationale: str = "",
        context_snapshot: dict[str, Any] | None = None,
        policies_evaluated: list[str] | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        vfe_before: float | None = None,
        vfe_after: float | None = None,
    ) -> DecisionTrace:
        """Record a decision: creates Decision entity + PG audit row.

        Returns the DecisionTrace.
        """
        decision_id = _uid()

        # Create Decision entity in Neo4j
        decision_entity = EntityBase(
            id=decision_id,
            name=f"Decision: {action}",
            statement=rationale or f"{actor} decided to {action}",
            entity_type=EntityType.DECISION,
            properties={
                "decision_type": action,
                "actor": actor,
                "rationale": rationale,
                "context_snapshot": context_snapshot or {},
                "alternatives_considered": alternatives or [],
                "policy_ids": policies_evaluated or [],
                "traceable": True,
            },
        )
        await self._graph.save_entity(decision_entity)

        # Create DECIDED_BY edge
        await self._graph.create_edge(
            target_entity_id, decision_id, "DECIDED_BY"
        )

        # Store in PostgreSQL audit log
        await self._db.save_decision_trace(
            actor=actor,
            action=action,
            target_entity_id=target_entity_id,
            rationale=rationale,
            context_snapshot=context_snapshot,
            policies_evaluated=policies_evaluated,
            alternatives=alternatives,
            vfe_before=vfe_before,
            vfe_after=vfe_after,
        )

        return DecisionTrace(
            decision_id=decision_id,
            actor=actor,
            action=action,
            target_entity_id=target_entity_id,
            rationale=rationale,
            context_snapshot=context_snapshot or {},
            policies_evaluated=policies_evaluated or [],
            alternatives=alternatives or [],
            vfe_before=vfe_before,
            vfe_after=vfe_after,
        )

    async def get_decision_trail(
        self,
        entity_id: str,
        depth: int = 10,
    ) -> list[dict[str, Any]]:
        """Walk DECIDED_BY edges to reconstruct decision chain."""
        # Get from PG for complete picture
        traces = await self._db.get_decision_traces(
            target_entity_id=entity_id, limit=depth
        )

        return traces

    async def explain_decision(self, decision_id: str) -> dict[str, Any]:
        """Generate explanation for a decision."""
        entity = await self._graph.get_entity(decision_id)
        if not entity:
            return {"error": "decision not found"}

        props = entity.properties
        explanation = {
            "decision_id": decision_id,
            "actor": props.get("actor", ""),
            "action": props.get("decision_type", ""),
            "rationale": props.get("rationale", ""),
            "context": props.get("context_snapshot", {}),
            "alternatives": props.get("alternatives_considered", []),
        }

        if self._llm and props.get("rationale"):
            explanation["note"] = "LLM explanation available"
        else:
            explanation["note"] = "Static explanation (no LLM)"

        return explanation
