"""JobOS 4.0 — Baseline & Switch Event API Routes.

Endpoints for capturing baselines, recording switch events,
comparing metrics, and evaluating phase exit criteria.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any

from jobos.api.deps import get_graph_port, get_relational_port
from jobos.services.baseline_service import BaselineService
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

router = APIRouter(prefix="/scenarios")


def _get_baseline_service(
    graph: GraphPort = Depends(get_graph_port),
    db: RelationalPort = Depends(get_relational_port),
) -> BaselineService:
    return BaselineService(graph=graph, db=db)


# ── Request Models ───────────────────────────────────────

class CaptureBaselineRequest(BaseModel):
    captured_by: str = "system"


class SwitchEventRequest(BaseModel):
    job_id: str
    trigger_metric: str
    trigger_value: float
    trigger_bound: str = ""
    action: str = "fire"
    reason: str = ""


# ── Endpoints ────────────────────────────────────────────

@router.post("/{scenario_id}/baseline/capture")
async def capture_baseline(
    scenario_id: str,
    req: CaptureBaselineRequest,
    svc: BaselineService = Depends(_get_baseline_service),
) -> dict[str, Any]:
    """Capture baseline metric snapshots for all jobs in a scenario."""
    try:
        return await svc.capture_baseline(
            scenario_id=scenario_id,
            captured_by=req.captured_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{scenario_id}/baseline/summary")
async def get_baseline_summary(
    scenario_id: str,
    svc: BaselineService = Depends(_get_baseline_service),
) -> dict[str, Any]:
    """Compare current metrics vs baseline for all jobs in a scenario."""
    try:
        return await svc.get_summary(scenario_id=scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{scenario_id}/switch-events")
async def record_switch_event(
    scenario_id: str,
    req: SwitchEventRequest,
    svc: BaselineService = Depends(_get_baseline_service),
) -> dict[str, Any]:
    """Record a switch event for a scenario."""
    return await svc.record_switch_event(
        scenario_id=scenario_id,
        job_id=req.job_id,
        trigger_metric=req.trigger_metric,
        trigger_value=req.trigger_value,
        trigger_bound=req.trigger_bound,
        action=req.action,
        reason=req.reason,
    )


@router.get("/{scenario_id}/switch-events")
async def get_switch_events(
    scenario_id: str,
    limit: int = 50,
    svc: BaselineService = Depends(_get_baseline_service),
) -> list[dict[str, Any]]:
    """Get switch events for a scenario."""
    return await svc.get_switch_events(scenario_id=scenario_id, limit=limit)


@router.get("/{scenario_id}/evaluate-phase")
async def evaluate_phase(
    scenario_id: str,
    svc: BaselineService = Depends(_get_baseline_service),
) -> dict[str, Any]:
    """Evaluate phase exit criteria for a scenario."""
    try:
        return await svc.evaluate_phase(scenario_id=scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
