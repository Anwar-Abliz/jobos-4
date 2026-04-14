"""JobOS 4.0 — Imperfection Routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from jobos.api.deps import get_imperfection_service, get_entity_service

router = APIRouter()


@router.get("/imperfections")
async def list_imperfections(job_id: str | None = None) -> dict:
    """List imperfections, optionally filtered by Job and ranked by severity."""
    if job_id:
        svc = get_imperfection_service()
        ranked = await svc.rank(job_id)
        return {
            "job_id": job_id,
            "count": len(ranked),
            "imperfections": [
                {
                    "id": i.id,
                    "name": i.name,
                    "statement": i.statement,
                    "status": i.status,
                    "severity": i.properties.get("severity", 0),
                    "is_blocker": i.properties.get("is_blocker", False),
                }
                for i in ranked
            ],
        }

    # No job filter: list all imperfections
    from jobos.kernel.entity import EntityType
    svc = get_entity_service()
    entities = await svc.list_by_type(EntityType.IMPERFECTION)
    return {"count": len(entities), "imperfections": [{"id": e.id, "name": e.name} for e in entities]}


@router.get("/imperfections/{imperfection_id}")
async def get_imperfection(imperfection_id: str) -> dict:
    """Get imperfection detail."""
    svc = get_entity_service()
    entity = await svc.get(imperfection_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Imperfection not found")
    return {
        "id": entity.id,
        "name": entity.name,
        "statement": entity.statement,
        "status": entity.status,
        "properties": entity.properties,
    }
