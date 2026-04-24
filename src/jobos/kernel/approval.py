"""JobOS 4.0 — Approval Gate Model.

Provides approval workflow for high-stakes hiring decisions.
Phase 1: Simple model — "fire" and "switch" on HUMAN executors
require approval.  Phase 2: configurable approval chains.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from jobos.kernel.entity import EntityBase, _uid


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    """A request for human approval before executing an action."""
    request_id: str = Field(default_factory=_uid)
    entity_id: str = ""
    action: str = ""
    requester: str = "system"
    approvers: list[str] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str = ""
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None
    resolved_by: str = ""


def requires_approval(
    action: str,
    entity: EntityBase,
    enforcement_mode: str = "advisory",
) -> bool:
    """Determine whether an action requires human approval.

    Phase 1 rule: "fire" and "switch" actions on HUMAN executors
    require approval when enforcement_mode != "permissive".
    """
    if enforcement_mode == "permissive":
        return False

    executor_type = entity.properties.get("executor_type", "HUMAN")
    if action in ("fire", "switch") and executor_type == "HUMAN":
        return True

    return False


def approve(request: ApprovalRequest, approver: str) -> ApprovalRequest:
    """Mark an approval request as approved."""
    return request.model_copy(update={
        "status": ApprovalStatus.APPROVED,
        "resolved_at": _now(),
        "resolved_by": approver,
    })


def reject(request: ApprovalRequest, approver: str, reason: str = "") -> ApprovalRequest:
    """Mark an approval request as rejected."""
    return request.model_copy(update={
        "status": ApprovalStatus.REJECTED,
        "resolved_at": _now(),
        "resolved_by": approver,
        "reason": reason,
    })
