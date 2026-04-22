"""JobOS 4.0 — Governance Service.

Phase 1: Lightweight CRUD for policies + check_permission.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.governance import evaluate_governance
from jobos.ports.graph_port import GraphPort

logger = logging.getLogger(__name__)


class GovernanceService:
    """Governance policy management and enforcement."""

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph

    async def create_policy(
        self,
        name: str,
        policy_type: str = "access",
        rules: list[dict[str, Any]] | None = None,
        enforcement: str = "advisory",
        owner: str = "",
    ) -> EntityBase:
        """Create a governance policy entity."""
        policy_id = _uid()
        policy = EntityBase(
            id=policy_id,
            name=name,
            statement=f"Governance policy: {name}",
            entity_type=EntityType.POLICY,
            properties={
                "policy_type": policy_type,
                "rules": rules or [],
                "enforcement": enforcement,
                "owner": owner,
                "version": "1.0",
            },
        )
        await self._graph.save_entity(policy)
        logger.info("Created policy '%s' (%s)", name, policy_id)
        return policy

    async def check_permission(
        self,
        actor: str,
        action: str,
        target_entity_id: str,
    ) -> dict[str, Any]:
        """Check if an action is permitted under governance policies.

        Phase 1: Collects GOVERNED_BY policies on the target entity
        and evaluates them.
        """
        entity = await self._graph.get_entity(target_entity_id)
        if not entity:
            return {"allowed": True, "reason": "entity not found — no policies"}

        # Get policies linked via GOVERNED_BY
        policy_entities = await self._graph.get_neighbors(
            target_entity_id, edge_type="GOVERNED_BY", direction="outgoing"
        )

        policies = [
            p.properties for p in policy_entities
            if p.entity_type == EntityType.POLICY
        ]

        target_dict = {
            "entity_type": entity.entity_type.value,
            **entity.properties,
        }

        allowed, reason = evaluate_governance(actor, action, target_dict, policies)

        return {"allowed": allowed, "reason": reason}

    async def get_policies_for_entity(
        self,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """Get all governance policies applied to an entity."""
        policy_entities = await self._graph.get_neighbors(
            entity_id, edge_type="GOVERNED_BY", direction="outgoing"
        )

        return [
            {
                "id": p.id,
                "name": p.name,
                **p.properties,
            }
            for p in policy_entities
            if p.entity_type == EntityType.POLICY
        ]

    async def link_policy(self, entity_id: str, policy_id: str) -> bool:
        """Link a governance policy to an entity via GOVERNED_BY."""
        return await self._graph.create_edge(entity_id, policy_id, "GOVERNED_BY")
