"""JobOS 4.0 — Neo4j Entity Repository (GraphPort implementation).

Implements the unified Entity model with dynamic Neo4j labels.
Single repository replaces JobOS 3.0's 8 separate repositories.

CTO Decision 2: Unified Entity with ECS-style components.
    Every node is (:Entity) with additional dynamic labels based on
    entity_type: (:Entity:Job), (:Entity:Executor), etc.
    Properties are stored as a JSON map in the `properties` field.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType
from jobos.ports.graph_port import GraphPort
from jobos.adapters.neo4j.connection import Neo4jConnection

logger = logging.getLogger(__name__)


def _entity_to_node_params(entity: EntityBase) -> dict[str, Any]:
    """Convert an EntityBase to Neo4j node parameters."""
    return {
        "id": entity.id,
        "name": entity.name,
        "statement": entity.statement,
        "entity_type": entity.entity_type.value,
        "status": entity.status,
        "properties_json": json.dumps(entity.properties, default=str),
        "labels": entity.labels,
        "created_at": entity.created_at.isoformat(),
        "updated_at": entity.updated_at.isoformat(),
        "slug": entity.properties.get("slug", ""),
    }


def _row_to_entity(row: dict[str, Any], node_key: str = "e") -> EntityBase:
    """Convert a Neo4j result row to an EntityBase."""
    n = row.get(node_key) or row
    props_raw = n.get("properties_json", "{}")
    if isinstance(props_raw, str):
        properties = json.loads(props_raw)
    else:
        properties = props_raw or {}

    return EntityBase(
        id=n.get("id", ""),
        name=n.get("name", ""),
        statement=n.get("statement", ""),
        entity_type=EntityType(n.get("entity_type", "job")),
        status=n.get("status", "active"),
        properties=properties,
        labels=n.get("labels", []),
        created_at=n.get("created_at", ""),
        updated_at=n.get("updated_at", ""),
    )


class Neo4jEntityRepo(GraphPort):
    """Neo4j implementation of the GraphPort.

    All entities are stored as (:Entity) nodes with dynamic labels.
    Edge types map directly to Neo4j relationship types.
    """

    def __init__(self, conn: Neo4jConnection) -> None:
        self._conn = conn

    # ── Entity CRUD ──────────────────────────────────────

    async def save_entity(self, entity: EntityBase) -> str:
        """Create or update an Entity node with dynamic labels.

        Uses MERGE on Entity.id for idempotent upsert.
        Dynamic labels are applied via APOC or Cypher CALL subquery.
        """
        params = _entity_to_node_params(entity)

        # Base label is always :Entity. Additional type label is dynamic.
        type_label = entity.entity_type.value.capitalize()

        query = f"""
        MERGE (e:Entity {{id: $id}})
        SET e.name = $name,
            e.statement = $statement,
            e.entity_type = $entity_type,
            e.status = $status,
            e.properties_json = $properties_json,
            e.labels = $labels,
            e.slug = $slug,
            e.created_at = coalesce(e.created_at, $created_at),
            e.updated_at = $updated_at
        SET e:{type_label}
        RETURN e.id AS id
        """

        rows = await self._conn.run(query, params)
        return rows[0]["id"] if rows else entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        """Retrieve an Entity by ID."""
        query = """
        MATCH (e:Entity {id: $id})
        RETURN e {.*} AS e
        LIMIT 1
        """
        rows = await self._conn.run(query, {"id": entity_id})
        if not rows:
            return None
        return _row_to_entity(rows[0])

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an Entity and all its incident edges."""
        query = """
        MATCH (e:Entity {id: $id})
        DETACH DELETE e
        RETURN count(e) AS deleted
        """
        rows = await self._conn.run(query, {"id": entity_id})
        return bool(rows and rows[0].get("deleted", 0) > 0)

    async def list_entities(
        self,
        entity_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityBase]:
        """List entities with optional filtering."""
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if entity_type:
            conditions.append("e.entity_type = $entity_type")
            params["entity_type"] = entity_type
        if status:
            conditions.append("e.status = $status")
            params["status"] = status

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (e:Entity)
        {where}
        RETURN e {{.*}} AS e
        ORDER BY e.updated_at DESC
        SKIP $offset
        LIMIT $limit
        """
        rows = await self._conn.run(query, params)
        return [_row_to_entity(r) for r in rows]

    # ── Edge Operations ──────────────────────────────────

    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Create a directed edge between two entities.

        Uses MERGE for idempotent creation. Properties are set on the edge.
        """
        edge_type = edge_type.upper()
        props = properties or {}
        props_json = json.dumps(props, default=str)

        # Dynamic relationship type via APOC or string interpolation
        # Safe because edge_type is validated against a known set
        allowed_types = {
            "HIRES", "FIRES", "MINIMIZES", "PART_OF", "QUALIFIES",
            "MEASURED_BY", "OCCURS_IN", "IMPACTS", "ABOUT",
            "SUPPORTS", "REFUTES", "DUAL_AS", "DEPENDS_ON", "HAS_STEP",
            "CHILD_OF", "CONTAINS", "TARGETS", "EXPERIENCE_OF",
        }
        if edge_type not in allowed_types:
            logger.warning("Unknown edge type: %s", edge_type)
            return False

        query = f"""
        MATCH (src:Entity {{id: $source_id}})
        MATCH (tgt:Entity {{id: $target_id}})
        MERGE (src)-[r:{edge_type}]->(tgt)
        SET r.properties_json = $props_json,
            r.updated_at = datetime()
        RETURN type(r) AS rel_type
        """
        rows = await self._conn.run(query, {
            "source_id": source_id,
            "target_id": target_id,
            "props_json": props_json,
        })
        return bool(rows)

    async def delete_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
    ) -> bool:
        """Delete a specific edge."""
        edge_type = edge_type.upper()

        query = f"""
        MATCH (src:Entity {{id: $source_id}})-[r:{edge_type}]->(tgt:Entity {{id: $target_id}})
        DELETE r
        RETURN count(r) AS deleted
        """
        rows = await self._conn.run(query, {
            "source_id": source_id,
            "target_id": target_id,
        })
        return bool(rows and rows[0].get("deleted", 0) > 0)

    async def get_neighbors(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[EntityBase]:
        """Get neighboring entities."""
        if direction == "outgoing":
            pattern = "(e:Entity {id: $id})-[r]->(n:Entity)"
        elif direction == "incoming":
            pattern = "(e:Entity {id: $id})<-[r]-(n:Entity)"
        else:
            pattern = "(e:Entity {id: $id})-[r]-(n:Entity)"

        type_filter = f"AND type(r) = $edge_type" if edge_type else ""

        query = f"""
        MATCH {pattern}
        WHERE true {type_filter}
        RETURN n {{.*}} AS e
        """
        params: dict[str, Any] = {"id": entity_id}
        if edge_type:
            params["edge_type"] = edge_type.upper()

        rows = await self._conn.run(query, params)
        return [_row_to_entity(r) for r in rows]

    async def get_edges(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get edges with properties."""
        if direction == "outgoing":
            pattern = "(e:Entity {id: $id})-[r]->(n:Entity)"
        elif direction == "incoming":
            pattern = "(e:Entity {id: $id})<-[r]-(n:Entity)"
        else:
            pattern = "(e:Entity {id: $id})-[r]-(n:Entity)"

        type_filter = f"AND type(r) = $edge_type" if edge_type else ""

        query = f"""
        MATCH {pattern}
        WHERE true {type_filter}
        RETURN type(r) AS edge_type,
               n.id AS target_id,
               r.properties_json AS properties_json
        """
        params: dict[str, Any] = {"id": entity_id}
        if edge_type:
            params["edge_type"] = edge_type.upper()

        rows = await self._conn.run(query, params)
        results = []
        for row in rows:
            props_raw = row.get("properties_json", "{}")
            props = json.loads(props_raw) if isinstance(props_raw, str) else (props_raw or {})
            results.append({
                "edge_type": row.get("edge_type", ""),
                "target_id": row.get("target_id", ""),
                "properties": props,
            })
        return results

    # ── Graph Queries ────────────────────────────────────

    async def get_job_subgraph(
        self,
        job_id: str,
        depth: int = 3,
    ) -> dict[str, Any]:
        """Get the full subgraph rooted at a Job."""
        query = """
        MATCH (root:Entity:Job {id: $job_id})
        OPTIONAL MATCH (root)-[:MEASURED_BY]->(metric:Entity:Metric)
        OPTIONAL MATCH (imp:Entity:Imperfection)-[:OCCURS_IN]->(root)
        OPTIONAL MATCH (ctx:Entity:Context)-[:QUALIFIES]->(root)
        OPTIONAL MATCH (hirer:Entity)-[:HIRES]->(root)
        OPTIONAL MATCH (root)<-[:PART_OF]-(child:Entity:Job)
        RETURN root {.*} AS job,
               collect(DISTINCT metric {.*}) AS metrics,
               collect(DISTINCT imp {.*}) AS imperfections,
               collect(DISTINCT ctx {.*}) AS contexts,
               collect(DISTINCT hirer {.*}) AS hirers,
               collect(DISTINCT child {.*}) AS children
        """
        rows = await self._conn.run(query, {"job_id": job_id})
        if not rows:
            return {}

        row = rows[0]
        return {
            "job": row.get("job"),
            "metrics": row.get("metrics", []),
            "imperfections": row.get("imperfections", []),
            "contexts": row.get("contexts", []),
            "hirers": row.get("hirers", []),
            "children": row.get("children", []),
        }

    # ── Schema Management ────────────────────────────────

    async def add_label(self, entity_id: str, label: str) -> bool:
        """Add an extra label to an existing Entity node.

        Used by the Duality hook: completed Job gains :Capability label.
        Label is sanitised to alpha-numeric + underscore only.
        """
        # Sanitise: only allow safe label characters
        safe_label = "".join(c for c in label if c.isalnum() or c == "_")
        if not safe_label:
            logger.warning("add_label: rejected unsafe label '%s'", label)
            return False

        query = f"""
        MATCH (e:Entity {{id: $id}})
        SET e:{safe_label}
        RETURN e.id AS id
        """
        rows = await self._conn.run(query, {"id": entity_id})
        return bool(rows)

    async def ensure_schema(self) -> int:
        """Initialize Neo4j schema."""
        from jobos.adapters.neo4j.schema import ensure_schema
        return await ensure_schema(self._conn)

    async def verify_connectivity(self) -> bool:
        """Health check."""
        return await self._conn.verify_connectivity()
