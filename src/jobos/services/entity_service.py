"""JobOS 4.0 — Entity Service (Unified CRUD).

Single service replaces JobOS 3.0's 8 separate services.
Handles creation, retrieval, update, and deletion of any Entity type.
Type-specific validation is delegated to kernel validators.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from jobos.kernel.entity import (
    EntityBase,
    EntityType,
    validate_entity,
)
from jobos.kernel.axioms import JobOSAxioms, AxiomViolation
from jobos.ports.graph_port import GraphPort

logger = logging.getLogger(__name__)


class EntityService:
    """CRUD operations for the unified Entity model.

    Enforces ontological constraints on create/update:
    - C1: Job statements must start with an action verb (Axiom 5)
    - Axiom 6: At most one root_token='ROOT' per scope_id
    - Axiom 3 (Duality): completed Job gains :Capability label in Neo4j
    - Type-specific property validation via validate_entity()
    - Dynamic label management in Neo4j
    """

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph

    async def create(self, entity: EntityBase) -> EntityBase:
        """Create a new Entity.

        Validates type-specific properties and axiom constraints.
        Persists to Neo4j with appropriate dynamic labels.
        """
        # Validate properties match the entity type
        validate_entity(entity)

        if entity.entity_type == EntityType.JOB:
            # Axiom 5: Job statements must start with verb (or experiential phrase)
            if entity.statement:
                is_experiential = entity.properties.get("job_type") in ("emotional", "social")
                JobOSAxioms.validate_linguistic_structure(
                    entity.statement, experiential=is_experiential
                )

            # Axiom 6: Enforce at most one root_token='ROOT' per scope_id
            if entity.properties.get("root_token") == "ROOT":
                scope_id = entity.properties.get("scope_id", "")
                existing = await self._graph.list_entities(
                    entity_type="job",
                    status=None,
                    limit=10,
                )
                scope_roots = [
                    e for e in existing
                    if e.properties.get("root_token") == "ROOT"
                    and e.properties.get("scope_id", "") == scope_id
                ]
                if scope_roots:
                    raise AxiomViolation(
                        6,
                        f"Scope '{scope_id}' already has a root job: "
                        f"{scope_roots[0].id}. Only one ROOT per scope is allowed."
                    )

        # Set timestamps
        now = datetime.now(timezone.utc)
        entity.created_at = now
        entity.updated_at = now

        # Ensure the type label is in the labels list
        type_label = entity.entity_type.value.capitalize()
        if type_label not in entity.labels:
            entity.labels.append(type_label)

        await self._graph.save_entity(entity)
        logger.info("Created %s entity: %s", entity.entity_type.value, entity.id)
        return entity

    async def get(self, entity_id: str) -> EntityBase | None:
        """Retrieve an Entity by ID."""
        return await self._graph.get_entity(entity_id)

    async def update(self, entity_id: str, updates: dict) -> EntityBase | None:
        """Update an Entity's properties.

        Re-validates after applying updates.
        Duality hook: when a Job transitions to 'completed', applies :Capability
        label in Neo4j and creates a DUAL_AS self-edge (Axiom 3).
        """
        entity = await self._graph.get_entity(entity_id)
        if entity is None:
            return None

        prev_status = entity.status

        # Apply updates
        for key, value in updates.items():
            if key == "properties" and isinstance(value, dict):
                entity.properties.update(value)
            elif hasattr(entity, key) and key not in ("id", "created_at"):
                setattr(entity, key, value)

        entity.updated_at = datetime.now(timezone.utc)

        # Re-validate
        validate_entity(entity)
        if entity.entity_type == EntityType.JOB and entity.statement:
            is_experiential = entity.properties.get("job_type") in ("emotional", "social")
            JobOSAxioms.validate_linguistic_structure(
                entity.statement, experiential=is_experiential
            )

        await self._graph.save_entity(entity)

        # Axiom 3 — Duality hook: completed Job becomes a hireable Capability
        if (
            entity.entity_type == EntityType.JOB
            and prev_status != "completed"
            and entity.status == "completed"
        ):
            await self._apply_duality(entity)

        logger.info("Updated entity: %s", entity.id)
        return entity

    async def _apply_duality(self, job: EntityBase) -> None:
        """Axiom 3 (Duality): add :Capability label and DUAL_AS self-edge.

        Called when a Job transitions to status='completed'. The completed
        job becomes ontologically superposed as both a Job and a Capability —
        it can now be hired by higher-level jobs.

        Neo4j result: (:Entity:Job:Capability {id: job.id})
                      with a (job)-[:DUAL_AS]->(job) self-edge.
        """
        try:
            await self._graph.add_label(job.id, "Capability")
            await self._graph.create_edge(
                source_id=job.id,
                target_id=job.id,
                edge_type="DUAL_AS",
                properties={"dual_at": datetime.now(timezone.utc).isoformat()},
            )
            logger.info(
                "Duality applied: Job %s → :Capability label + DUAL_AS edge", job.id
            )
        except Exception as exc:
            # Duality failure is logged but does not roll back the status update.
            # The job status is the source of truth; label/edge can be repaired.
            logger.warning(
                "Duality hook failed for job %s: %s", job.id, exc
            )

    async def delete(self, entity_id: str) -> bool:
        """Delete an Entity and its incident edges."""
        result = await self._graph.delete_entity(entity_id)
        if result:
            logger.info("Deleted entity: %s", entity_id)
        return result

    async def list_by_type(
        self,
        entity_type: EntityType | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityBase]:
        """List entities with optional filtering."""
        type_str = entity_type.value if entity_type else None
        return await self._graph.list_entities(
            entity_type=type_str,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_neighbors(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[EntityBase]:
        """Get entities connected to this one by edges."""
        return await self._graph.get_neighbors(
            entity_id, edge_type=edge_type, direction=direction
        )
