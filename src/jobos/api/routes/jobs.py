"""JobOS 4.0 — Job-Specific View Routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from jobos.api.deps import get_entity_service, get_imperfection_service
from jobos.kernel.entity import EntityType

router = APIRouter()


@router.get("/jobs/{job_id}/imperfections")
async def get_job_imperfections(job_id: str) -> dict:
    """List imperfections for a Job, ranked by IPS (highest first)."""
    svc = get_imperfection_service()
    imperfections = await svc.rank(job_id)
    return {
        "job_id": job_id,
        "count": len(imperfections),
        "imperfections": [
            {
                "id": i.id,
                "name": i.name,
                "statement": i.statement,
                "status": i.status,
                "properties": i.properties,
            }
            for i in imperfections
        ],
    }


@router.get("/jobs/{job_id}/metrics")
async def get_job_metrics(job_id: str) -> dict:
    """List metrics attached to a Job with their current values."""
    svc = get_entity_service()
    metrics = await svc.get_neighbors(job_id, edge_type="MEASURED_BY", direction="outgoing")
    return {
        "job_id": job_id,
        "count": len(metrics),
        "metrics": [
            {
                "id": m.id,
                "name": m.name,
                "properties": m.properties,
            }
            for m in metrics
        ],
    }


@router.get("/jobs/{job_id}/hires")
async def get_job_hires(job_id: str) -> dict:
    """List active hires for a Job.

    Traverses: (Job) <-[:HIRES]- (Executor) to find who is hired.
    """
    svc = get_entity_service()
    hires = await svc.get_neighbors(job_id, edge_type="HIRES", direction="incoming")
    return {
        "job_id": job_id,
        "count": len(hires),
        "hires": [
            {
                "id": h.id,
                "name": h.name,
                "entity_type": h.entity_type.value,
                "status": h.status,
            }
            for h in hires
        ],
    }


@router.post("/jobs/{job_id}/derive-imperfections")
async def derive_imperfections(job_id: str) -> dict:
    """Trigger imperfection derivation from unmet metric thresholds.

    Computes severity for each metric gap and creates/updates
    Imperfection entities. Enforces Axiom 2 (entropy residual).
    """
    svc = get_imperfection_service()
    imperfections = await svc.derive_imperfections(job_id)
    return {
        "job_id": job_id,
        "derived_count": len(imperfections),
        "imperfections": [
            {"id": i.id, "severity": i.properties.get("severity", 0), "is_blocker": i.properties.get("is_blocker", False)}
            for i in imperfections
        ],
    }
