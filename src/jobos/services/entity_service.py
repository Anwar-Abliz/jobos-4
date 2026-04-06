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

        # Axiom 5: Job statements must start with verb
        if entity.entity_type == EntityType.JOB and entity.statement:
            JobOSAxioms.validate_linguistic_structure(entity.statement)

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
        """
        entity = await self._graph.get_entity(entity_id)
        if entity is None:
            return None

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
            JobOSAxioms.validate_linguistic_structure(entity.statement)

        await self._graph.save_entity(entity)
        logger.info("Updated entity: %s", entity.id)
        return entity

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
