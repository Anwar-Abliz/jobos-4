"""JobOS 4.0 — Context API Routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jobos.api.deps import get_context_service
from jobos.services.context_service import ContextService

router = APIRouter(prefix="/context")


class ContextSnapshotResponse(BaseModel):
    snapshot_id: str = ""
    entity_id: str = ""
    error: str | None = None


class FreshnessResponse(BaseModel):
    entity_id: str = ""
    stale: bool = False
    age_hours: float = 0.0
    freshness: str = "snapshot"
    threshold_hours: float = 24.0
    reason: str | None = None


class CoverageResponse(BaseModel):
    scope_id: str = ""
    total_steps: int = 0
    covered_steps: int = 0
    coverage_pct: float = 0.0


class ThresholdRequest(BaseModel):
    threshold_hours: float = 24.0


@router.post("/snapshot/{entity_id}", response_model=ContextSnapshotResponse)
async def capture_snapshot(
    entity_id: str,
    svc: ContextService = Depends(get_context_service),
):
    result = await svc.capture_context_snapshot(entity_id)
    return ContextSnapshotResponse(**result)


@router.get("/freshness/{entity_id}", response_model=FreshnessResponse)
async def check_freshness(
    entity_id: str,
    threshold_hours: float = 24.0,
    svc: ContextService = Depends(get_context_service),
):
    result = await svc.detect_context_decay(entity_id, threshold_hours)
    return FreshnessResponse(**result)


@router.post("/infer/{entity_id}")
async def infer_relationships(
    entity_id: str,
    svc: ContextService = Depends(get_context_service),
):
    return await svc.infer_relationships(entity_id)


@router.get("/coverage/{scope_id}", response_model=CoverageResponse)
async def get_coverage(
    scope_id: str,
    svc: ContextService = Depends(get_context_service),
):
    result = await svc.compute_context_coverage(scope_id)
    return CoverageResponse(**result)
