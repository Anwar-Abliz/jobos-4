"""JobOS 4.0 — Scenario API Routes.

Get scenario detail and scenario job tree.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Any

from jobos.api.deps import get_graph_port
from jobos.kernel.entity import EntityType
from jobos.ports.graph_port import GraphPort

router = APIRouter(prefix="/scenarios")


@router.get("/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    graph: GraphPort = Depends(get_graph_port),
) -> dict[str, Any]:
    """Get a Scenario by ID."""
    entity = await graph.get_entity(scenario_id)
    if not entity or entity.entity_type != EntityType.SCENARIO:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")
    return {
        "id": entity.id,
        "name": entity.name,
        "slug": entity.properties.get("slug", ""),
        "segment_id": entity.properties.get("segment_id", ""),
        "pilot_id": entity.properties.get("pilot_id", ""),
        "hypothesis": entity.properties.get("hypothesis", ""),
        "exit_criteria": entity.properties.get("exit_criteria", ""),
        "risks": entity.properties.get("risks", []),
        "dimension_b_metrics": entity.properties.get("dimension_b_metrics", []),
        "dimension_a_config": entity.properties.get("dimension_a_config", {}),
        "status": entity.properties.get("status", "draft"),
        "phase": entity.properties.get("phase", "phase_1"),
    }


@router.get("/{scenario_id}/tree")
async def get_scenario_tree(
    scenario_id: str,
    graph: GraphPort = Depends(get_graph_port),
) -> dict[str, Any]:
    """Get the job tree for a Scenario: T1 → T2 → T3 → T4 spine."""
    entity = await graph.get_entity(scenario_id)
    if not entity or entity.entity_type != EntityType.SCENARIO:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    # Find T1 via TARGETS edge
    t1_jobs = await graph.get_neighbors(scenario_id, edge_type="TARGETS", direction="outgoing")

    visited: set[str] = set()

    async def build_node(job_id: str) -> dict[str, Any] | None:
        if job_id in visited:
            return None
        visited.add(job_id)

        job = await graph.get_entity(job_id)
        if not job or job.entity_type != EntityType.JOB:
            return None

        node: dict[str, Any] = {
            "id": job.id,
            "tier": job.properties.get("hierarchy_tier", ""),
            "statement": job.statement,
            "category": job.properties.get("hierarchy_category", ""),
            "metrics_hint": job.properties.get("metrics_hint", []),
            "step_number": job.properties.get("step_number"),
        }

        children = await graph.get_neighbors(job_id, edge_type="HIRES", direction="outgoing")
        child_nodes = []
        for child in children:
            if child.entity_type == EntityType.JOB:
                child_node = await build_node(child.id)
                if child_node:
                    child_nodes.append(child_node)

        if child_nodes:
            node["children"] = child_nodes

        return node

    functional_spine = []
    for t1 in t1_jobs:
        node = await build_node(t1.id)
        if node:
            functional_spine.append(node)

    return {
        "id": scenario_id,
        "scenario_name": entity.name,
        "functional_spine": functional_spine,
        "experience_dimension": [],  # Populated from Dimension A nodes if available
    }
