"""JobOS 4.0 — Experience Dimension A API Routes.

Endpoints for generating, editing, and viewing experience markers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from jobos.api.deps import get_graph_port, get_relational_port
from jobos.kernel.axioms import AxiomViolation
from jobos.services.experience_service import ExperienceService
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

router = APIRouter(prefix="/experience")


def _get_experience_service(
    graph: GraphPort = Depends(get_graph_port),
) -> ExperienceService:
    try:
        db = get_relational_port()
    except RuntimeError:
        db = None
    return ExperienceService(graph=graph, db=db, llm=None)


# ── Request / Response Models ────────────────────────────

class GenerateRequest(BaseModel):
    job_id: str
    role_archetype: str = ""
    created_by: str = "system"


class EditRequest(BaseModel):
    feel_markers: list[str] = Field(default_factory=list)
    to_be_markers: list[str] = Field(default_factory=list)
    created_by: str = "user"


# ── Endpoints ────────────────────────────────────────────

@router.post("/generate")
async def generate_experience(
    req: GenerateRequest,
    svc: ExperienceService = Depends(_get_experience_service),
) -> dict[str, Any]:
    """Generate experience markers for a job (LLM or template fallback)."""
    try:
        return await svc.generate(
            job_id=req.job_id,
            role_archetype=req.role_archetype,
            created_by=req.created_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{job_id}")
async def edit_experience(
    job_id: str,
    req: EditRequest,
    svc: ExperienceService = Depends(_get_experience_service),
) -> dict[str, Any]:
    """Edit experience markers (human override). Validates Axiom 5."""
    try:
        markers = {
            "feel_markers": req.feel_markers,
            "to_be_markers": req.to_be_markers,
        }
        return await svc.edit(
            job_id=job_id,
            markers=markers,
            created_by=req.created_by,
        )
    except AxiomViolation as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{job_id}/history")
async def get_experience_history(
    job_id: str,
    limit: int = 50,
    svc: ExperienceService = Depends(_get_experience_service),
) -> list[dict[str, Any]]:
    """Get experience marker version history for a job."""
    return await svc.get_history(job_id, limit=limit)
