"""JobOS 4.0 — Job Hierarchy (Job Triad) Routes.

POST /api/hierarchy/generate — Generate a domain-specific job hierarchy
GET  /api/hierarchy/{id}     — Retrieve a generated hierarchy
GET  /api/hierarchy/{id}/tree — Get the hierarchy as a nested tree (for visualization)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobos.kernel.hierarchy import HierarchyContext
from jobos.api.deps import get_hierarchy_service

router = APIRouter()


# ─── Request / Response Models ───────────────────────────

class HierarchyGenerateIn(BaseModel):
    """Request body for generating a Job Triad."""
    domain: str = Field(..., max_length=200, description="Business domain (e.g., 'B2B SaaS', 'retail operations')")
    keywords: list[str] = Field(default_factory=list, description="Additional domain keywords")
    actor: str = Field(default="", description="Who is the primary job executor")
    goal: str = Field(default="", description="Optional overarching goal statement")
    constraints: str = Field(default="", description="Any constraints or context")


class HierarchyJobOut(BaseModel):
    id: str
    tier: str
    statement: str
    category: str = ""
    rationale: str = ""
    metrics_hint: list[str] = Field(default_factory=list)


class HierarchyEdgeOut(BaseModel):
    parent_id: str
    child_id: str
    strength: float = 1.0


class HierarchyOut(BaseModel):
    id: str
    domain: str
    jobs: list[HierarchyJobOut]
    edges: list[HierarchyEdgeOut]
    summary: dict[str, Any]


# ─── Endpoints ───────────────────────────────────────────

@router.post("/hierarchy/generate", response_model=HierarchyOut)
async def generate_hierarchy(req: HierarchyGenerateIn) -> HierarchyOut:
    """Generate a domain-specific Job Triad hierarchy.

    Provide a business domain (e.g., 'B2B SaaS', 'retail operations',
    'corporate transformation') and the system generates a structured
    job hierarchy with 4 tiers:
    - T1 Strategic: The overarching WHY
    - T2 Core Functional: Solution-agnostic WHAT
    - T3 Execution: Concrete HOW
    - T4 Micro-Job: Smallest discrete functional actions (EXECUTE)

    Experience (FEEL) is Dimension A, orthogonal to the tier hierarchy.

    All generated jobs are persisted to Neo4j as Entity:Job nodes
    connected by HIRES edges.

    With LLM enabled: generates contextually rich, domain-specific hierarchies.
    Without LLM: uses pre-built templates for common domains.
    """
    svc = get_hierarchy_service()
    context = HierarchyContext(
        domain=req.domain,
        keywords=req.keywords,
        actor=req.actor,
        goal=req.goal,
        constraints=req.constraints,
    )
    try:
        result = await svc.generate(context)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Hierarchy generation failed: {e}")

    return HierarchyOut(
        id=result.id,
        domain=result.context.domain,
        jobs=[
            HierarchyJobOut(
                id=j.id, tier=j.tier.value, statement=j.statement,
                category=j.category, rationale=j.rationale,
                metrics_hint=j.metrics_hint,
            )
            for j in result.jobs
        ],
        edges=[
            HierarchyEdgeOut(parent_id=e.parent_id, child_id=e.child_id, strength=e.strength)
            for e in result.edges
        ],
        summary=result.summary,
    )


@router.get("/hierarchy/{hierarchy_id}", response_model=HierarchyOut)
async def get_hierarchy(hierarchy_id: str) -> HierarchyOut:
    """Retrieve a previously generated hierarchy."""
    svc = get_hierarchy_service()
    result = await svc.get(hierarchy_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Hierarchy not found")

    return HierarchyOut(
        id=result.id,
        domain=result.context.domain,
        jobs=[
            HierarchyJobOut(
                id=j.id, tier=j.tier.value, statement=j.statement,
                category=j.category, rationale=j.rationale,
                metrics_hint=j.metrics_hint,
            )
            for j in result.jobs
        ],
        edges=[
            HierarchyEdgeOut(parent_id=e.parent_id, child_id=e.child_id, strength=e.strength)
            for e in result.edges
        ],
        summary={},
    )


@router.get("/hierarchy/{hierarchy_id}/tree")
async def get_hierarchy_tree(hierarchy_id: str) -> dict:
    """Get the hierarchy as a nested tree structure (for visualization).

    Returns a tree where each node has its children nested,
    making it easy to render as an expandable tree or graph.
    """
    svc = get_hierarchy_service()
    result = await svc.get(hierarchy_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Hierarchy not found")

    return result.to_tree_dict()
