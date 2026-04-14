"""JobOS 4.0 — Segment API Routes.

List segments, get segment detail, list scenarios per segment.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Any

from jobos.api.deps import get_graph_port
from jobos.kernel.entity import EntityType
from jobos.ports.graph_port import GraphPort

router = APIRouter(prefix="/segments")


@router.get("")
async def list_segments(
    graph: GraphPort = Depends(get_graph_port),
) -> list[dict[str, Any]]:
    """List all Segment entities."""
    entities = await graph.list_entities(entity_type="segment", limit=200)
    return [
        {
            "id": e.id,
            "name": e.name,
            "slug": e.properties.get("slug", ""),
            "description": e.properties.get("description", ""),
            "root_job_ids": e.properties.get("root_job_ids", []),
            "tags": e.properties.get("tags", []),
            "status": e.status,
        }
        for e in entities
    ]


@router.get("/{segment_id}")
async def get_segment(
    segment_id: str,
    graph: GraphPort = Depends(get_graph_port),
) -> dict[str, Any]:
    """Get a Segment by ID."""
    entity = await graph.get_entity(segment_id)
    if not entity or entity.entity_type != EntityType.SEGMENT:
        raise HTTPException(status_code=404, detail=f"Segment not found: {segment_id}")
    return {
        "id": entity.id,
        "name": entity.name,
        "slug": entity.properties.get("slug", ""),
        "description": entity.properties.get("description", ""),
        "root_job_ids": entity.properties.get("root_job_ids", []),
        "tags": entity.properties.get("tags", []),
        "status": entity.status,
    }


@router.get("/{segment_id}/scenarios")
async def get_segment_scenarios(
    segment_id: str,
    graph: GraphPort = Depends(get_graph_port),
) -> list[dict[str, Any]]:
    """List all Scenarios belonging to a Segment (via CONTAINS edge)."""
    entity = await graph.get_entity(segment_id)
    if not entity or entity.entity_type != EntityType.SEGMENT:
        raise HTTPException(status_code=404, detail=f"Segment not found: {segment_id}")

    neighbors = await graph.get_neighbors(segment_id, edge_type="CONTAINS", direction="outgoing")
    return [
        {
            "id": n.id,
            "name": n.name,
            "slug": n.properties.get("slug", ""),
            "pilot_id": n.properties.get("pilot_id", ""),
            "hypothesis": n.properties.get("hypothesis", ""),
            "status": n.properties.get("status", "draft"),
            "phase": n.properties.get("phase", "phase_1"),
        }
        for n in neighbors
        if n.entity_type == EntityType.SCENARIO
    ]
