"""JobOS 4.0 — Hiring Routes (Core Axiom API).

Entity HIRES Entity IN Context TO MINIMIZE Imperfection.

These endpoints expose the full Hire lifecycle:
    propose → execute → evaluate → switch
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobos.api.deps import get_hiring_service

router = APIRouter()


# ─── Request / Response Models ───────────────────────────

class HireCandidateIn(BaseModel):
    id: str
    name: str = ""
    estimated_impact: float = Field(default=0.0, ge=0.0, le=1.0)


class HireProposeIn(BaseModel):
    candidates: list[HireCandidateIn] = Field(default_factory=list)
    context_id: str | None = None


class HireExecuteIn(BaseModel):
    hirer_id: str
    hiree_id: str
    context_id: str | None = None
    imperfection_id: str | None = None


class HireSwitchIn(BaseModel):
    hirer_id: str
    current_hiree_id: str
    new_hiree_id: str
    reason: str = ""
    context_id: str | None = None


class HireEvaluateIn(BaseModel):
    hirer_id: str
    hiree_id: str


# ─── Endpoints ───────────────────────────────────────────

@router.post("/jobs/{job_id}/hire/propose")
async def propose_hire(job_id: str, req: HireProposeIn) -> dict:
    """Propose a Hire — NSAIG proposes, CDEE validates.

    Dry-run: does not commit to the graph. Returns the combined
    assessment from both engines so the user can review.

    The response includes:
    - nsaig_assessment: EFE score, policy confidence, reasoning
    - cdee_assessment: estimated impact, controllability, stability forecast
    - combined_recommendation: "hire" | "caution" | "reject"
    """
    svc = get_hiring_service()
    candidates = [c.model_dump() for c in req.candidates]
    proposal = await svc.propose_hire(
        job_id=job_id,
        candidates=candidates,
        context_id=req.context_id,
    )
    return {
        "hire_id": proposal.hire_id,
        "job_id": proposal.job_id,
        "hiree_id": proposal.hiree_id,
        "status": proposal.status,
        "nsaig_assessment": proposal.nsaig_assessment,
        "cdee_assessment": proposal.cdee_assessment,
        "combined_recommendation": proposal.combined_recommendation,
        "expected_imperfection_reduction": proposal.expected_imperfection_reduction,
        "reasoning": proposal.reasoning,
    }


@router.post("/jobs/{job_id}/hire")
async def execute_hire(job_id: str, req: HireExecuteIn) -> dict:
    """Execute a Hire — commit to graph + audit log.

    Creates:
    - HIRES edge in Neo4j (hirer → hiree)
    - MINIMIZES edge if imperfection_id provided
    - HiringEvent in PostgreSQL audit log
    """
    svc = get_hiring_service()
    event = await svc.execute_hire(
        hirer_id=req.hirer_id,
        hiree_id=req.hiree_id,
        job_id=job_id,
        context_id=req.context_id,
        imperfection_id=req.imperfection_id,
    )
    return {
        "event_id": event.id,
        "event_type": event.event_type.value,
        "hirer_id": event.hirer_id,
        "hiree_id": event.hiree_id,
        "occurred_at": event.occurred_at.isoformat(),
    }


@router.post("/hires/evaluate")
async def evaluate_hire(req: HireEvaluateIn, job_id: str = "") -> dict:
    """Evaluate an active Hire — both engines assess effectiveness.

    Returns:
    - nsaig_evaluation: VFE current/trend, switch recommendation
    - cdee_evaluation: error signal, stability status
    - combined_verdict: "keep" | "warn" | "switch"

    Requires job_id as a query parameter.
    """
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id query parameter required")
    svc = get_hiring_service()
    evaluation = await svc.evaluate_hire(
        hirer_id=req.hirer_id,
        hiree_id=req.hiree_id,
        job_id=job_id,
    )
    return {
        "hire_id": evaluation.hire_id,
        "status": evaluation.status,
        "nsaig_evaluation": evaluation.nsaig_evaluation,
        "cdee_evaluation": evaluation.cdee_evaluation,
        "combined_verdict": evaluation.combined_verdict,
        "reasoning": evaluation.reasoning,
    }


@router.post("/hires/switch")
async def execute_switch(req: HireSwitchIn, job_id: str = "") -> dict:
    """Execute a Switch — Fire current, Hire replacement.

    Creates FIRES edge, new HIRES edge, and HiringEvent (type=switch).

    This is Axiom 6 in action: the decision to replace a Hiring
    relationship when context changes or metrics are breached.
    """
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id query parameter required")
    svc = get_hiring_service()
    event = await svc.execute_switch(
        hirer_id=req.hirer_id,
        current_hiree_id=req.current_hiree_id,
        new_hiree_id=req.new_hiree_id,
        job_id=job_id,
        reason=req.reason,
        context_id=req.context_id,
    )
    return {
        "event_id": event.id,
        "event_type": event.event_type.value,
        "hirer_id": event.hirer_id,
        "hiree_id": event.hiree_id,
        "reason": event.reason,
        "occurred_at": event.occurred_at.isoformat(),
    }
