"""JobOS 4.0 — Graph Database Port (Neo4j abstraction).

This port abstracts the graph database operations for the unified
Entity model. A single repository replaces JobOS 3.0's 8 separate
repository ABCs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from jobos.kernel.entity import EntityBase


class GraphPort(ABC):
    """Abstract interface for graph database operations.

    Implementations: Neo4jEntityRepo (adapters/neo4j/entity_repo.py)
    """

    # ── Entity CRUD ──────────────────────────────────────

    @abstractmethod
    async def save_entity(self, entity: EntityBase) -> str:
        """Create or update an Entity node with dynamic labels.

        Returns the entity ID.
        """
        ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> EntityBase | None:
        """Retrieve an Entity by ID."""
        ...

    @abstractmethod
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an Entity and its incident edges. Returns True if found."""
        ...

    @abstractmethod
    async def list_entities(
        self,
        entity_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityBase]:
        """List entities with optional type/status filtering."""
        ...

    # ── Edge Operations ──────────────────────────────────

    @abstractmethod
    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Create a directed edge between two entities.

        edge_type: HIRES, FIRES, MINIMIZES, PART_OF, QUALIFIES,
                   MEASURED_BY, OCCURS_IN, IMPACTS, ABOUT,
                   SUPPORTS, REFUTES, DUAL_AS
        """
        ...

    @abstractmethod
    async def delete_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
    ) -> bool:
        """Delete a specific edge. Returns True if found."""
        ...

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[EntityBase]:
        """Get neighboring entities connected by edges.

        direction: 'outgoing', 'incoming', or 'both'
        """
        ...

    @abstractmethod
    async def get_edges(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get edges with their properties for an entity."""
        ...

    # ── Graph Queries ────────────────────────────────────

    @abstractmethod
    async def get_job_subgraph(
        self,
        job_id: str,
        depth: int = 3,
    ) -> dict[str, Any]:
        """Get the full subgraph rooted at a Job: children, metrics,
        imperfections, hires, context."""
        ...

    # ── Schema Management ────────────────────────────────

    @abstractmethod
    async def add_label(self, entity_id: str, label: str) -> bool:
        """Add an extra Neo4j label to an existing Entity node.

        Used by the Duality hook (Axiom 3): when a Job completes it gains
        the :Capability label in addition to :Job.

        Returns True if the node was found and updated.
        """
        ...

    @abstractmethod
    async def ensure_schema(self) -> int:
        """Initialize constraints, indexes. Returns count of statements run."""
        ...

    @abstractmethod
    async def verify_connectivity(self) -> bool:
        """Health check. Returns True if reachable."""
        ...

    # ── Graph Path Queries ────────────────────────────────

    @abstractmethod
    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find shortest path between two entities.

        Returns list of dicts with node/edge info along the path.
        """
        ...

    @abstractmethod
    async def get_subgraph_by_label(
        self,
        label: str,
        limit: int = 100,
    ) -> list[EntityBase]:
        """Query entities by dynamic Neo4j label."""
        ...
