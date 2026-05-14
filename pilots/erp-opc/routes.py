"""ERP-for-OPC — FastAPI Routes for Financial Close Agent.

Agent-first API: no UI, machine-readable responses, explicit escalation signals.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobos.pilots.erp_opc.service import FinancialCloseService

router = APIRouter(prefix="/erp-opc", tags=["erp-opc"])

# Singleton service instance (pilot uses in-memory state)
_service = FinancialCloseService(approval_threshold=500.0)


def get_service() -> FinancialCloseService:
    return _service


# ── Request/Response Models ────────────────────────────────────────────────


class IngestRequest(BaseModel):
    rows: list[dict] = Field(..., min_length=1, description="Bank statement rows: [{date, amount, description, reference?}]")


class ReconcileRequest(BaseModel):
    tolerance_amount: float = Field(0.01, ge=0, description="Amount tolerance for matching")


class AdjustmentRequest(BaseModel):
    adjustments: list[dict] = Field(..., min_length=1, description="[{debit_account, credit_account, amount, description, date?}]")


class ApprovalRequest(BaseModel):
    entry_id: str
    approved_by: str = Field(..., min_length=1)


class RejectionRequest(BaseModel):
    entry_id: str
    reason: str = Field(..., min_length=1)


class PeriodRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2030)
    month: int = Field(..., ge=1, le=12)


class PeriodCloseConfirm(BaseModel):
    year: int = Field(..., ge=2020, le=2030)
    month: int = Field(..., ge=1, le=12)
    approved_by: str = Field(..., min_length=1)


# ── CAP-01: Bank Statement Ingestion ──────────────────────────────────────


@router.post("/ingest")
async def ingest_bank_data(req: IngestRequest):
    """Ingest bank statement rows into the journal.

    Agent calls this with parsed CSV/OFX data.
    Returns: ingested count, duplicates, errors, escalation if error rate > 5%.
    """
    svc = get_service()
    return svc.ingest_bank_data(req.rows)


# ── CAP-02: Reconciliation ────────────────────────────────────────────────


@router.post("/reconcile")
async def reconcile_entries(req: ReconcileRequest):
    """Match bank transactions against ledger entries.

    Returns: reconciliation report + suggestions for ambiguous matches.
    Escalates if match rate < 80%.
    """
    svc = get_service()
    return svc.reconcile_entries(tolerance_amount=req.tolerance_amount)


# ── CAP-03: Adjustment Entries ─────────────────────────────────────────────


@router.post("/adjustments")
async def draft_adjustments(req: AdjustmentRequest):
    """Draft and optionally post adjustment journal entries.

    Entries below the approval threshold are auto-posted.
    Entries above threshold are held for human approval.
    """
    svc = get_service()
    return svc.draft_adjustments(req.adjustments)


@router.post("/adjustments/approve")
async def approve_adjustment(req: ApprovalRequest):
    """Human approves a pending adjustment entry."""
    svc = get_service()
    result = svc.approve_adjustment(req.entry_id, req.approved_by)
    if result["status"] == "error":
        raise HTTPException(404, result["message"])
    return result


@router.post("/adjustments/reject")
async def reject_adjustment(req: RejectionRequest):
    """Human rejects a pending adjustment entry."""
    svc = get_service()
    result = svc.reject_adjustment(req.entry_id, req.reason)
    if result["status"] == "error":
        raise HTTPException(404, result["message"])
    return result


# ── CAP-04: Trial Balance ──────────────────────────────────────────────────


@router.post("/trial-balance")
async def generate_trial_balance(req: PeriodRequest):
    """Generate trial balance for the specified period.

    Returns balanced/imbalanced status. Escalates if imbalanced.
    """
    svc = get_service()
    return svc.generate_trial_balance(req.year, req.month)


# ── CAP-05: Period Close ───────────────────────────────────────────────────


@router.post("/close/request")
async def request_period_close(req: PeriodRequest):
    """Request period close. Checks prerequisites, always escalates for human approval.

    Returns blockers if prerequisites not met.
    """
    svc = get_service()
    return svc.request_period_close(req.year, req.month)


@router.post("/close/confirm")
async def confirm_period_close(req: PeriodCloseConfirm):
    """Human confirms period close — locks the period."""
    svc = get_service()
    result = svc.confirm_period_close(req.year, req.month, req.approved_by)
    if result["status"] == "error":
        raise HTTPException(400, result["message"])
    return result


# ── Query Endpoints ────────────────────────────────────────────────────────


@router.get("/escalations")
async def get_escalations(unresolved_only: bool = True):
    """Get pending escalations requiring human attention."""
    svc = get_service()
    return {"escalations": svc.get_escalations(unresolved_only)}


@router.get("/period/{year}/{month}")
async def get_period_status(year: int, month: int):
    """Get current status of an accounting period."""
    svc = get_service()
    return svc.get_period_status(year, month)


@router.get("/health")
async def health():
    """Health check for the ERP-for-OPC pilot."""
    svc = get_service()
    return {
        "status": "ok",
        "pilot": "erp-opc-financial-close",
        "transactions": len(svc.transactions),
        "ledger_entries": len(svc.ledger_entries),
        "open_escalations": len([e for e in svc.escalations if not e.resolved]),
        "periods": {k: v.status.value for k, v in svc.periods.items()},
    }
