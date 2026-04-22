"""JobOS 4.0 — Decision API Routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jobos.api.deps import get_decision_service
from jobos.services.decision_service import DecisionService

router = APIRouter(prefix="/decisions")


class RecordDecisionRequest(BaseModel):
    actor: str
    action: str
    target_entity_id: str
    rationale: str = ""
    context_snapshot: dict[str, Any] | None = None
    policies_evaluated: list[str] | None = None
    alternatives: list[dict[str, Any]] | None = None
    vfe_before: float | None = None
    vfe_after: float | None = None


class DecisionResponse(BaseModel):
    decision_id: str
    actor: str
    action: str
    target_entity_id: str
    rationale: str = ""


@router.post("", response_model=DecisionResponse)
async def record_decision(
    request: RecordDecisionRequest,
    svc: DecisionService = Depends(get_decision_service),
):
    trace = await svc.record_decision(
        actor=request.actor,
        action=request.action,
        target_entity_id=request.target_entity_id,
        rationale=request.rationale,
        context_snapshot=request.context_snapshot,
        policies_evaluated=request.policies_evaluated,
        alternatives=request.alternatives,
        vfe_before=request.vfe_before,
        vfe_after=request.vfe_after,
    )
    return DecisionResponse(
        decision_id=trace.decision_id,
        actor=trace.actor,
        action=trace.action,
        target_entity_id=trace.target_entity_id,
        rationale=trace.rationale,
    )


@router.get("/{entity_id}/trail")
async def get_trail(
    entity_id: str,
    depth: int = 10,
    svc: DecisionService = Depends(get_decision_service),
):
    return await svc.get_decision_trail(entity_id, depth=depth)


@router.get("/{decision_id}/explain")
async def explain_decision(
    decision_id: str,
    svc: DecisionService = Depends(get_decision_service),
):
    return await svc.explain_decision(decision_id)
