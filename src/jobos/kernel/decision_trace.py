"""JobOS 4.0 — Decision Trace Model (Kernel).

Immutable record of every decision made in the system, with full
context snapshots for audit trail and explainability.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from jobos.kernel.entity import _now, _uid


class DecisionTrace(BaseModel):
    """Immutable record of a decision with full context."""
    decision_id: str = Field(default_factory=_uid)
    timestamp: datetime = Field(default_factory=_now)
    actor: str = ""
    action: str = ""
    target_entity_id: str = ""
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    policies_evaluated: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    vfe_before: float | None = None
    vfe_after: float | None = None
    lineage: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


def chain_decision(parent: DecisionTrace, child: DecisionTrace) -> DecisionTrace:
    """Chain a child decision to a parent, building lineage."""
    child.lineage = [*parent.lineage, parent.decision_id]
    return child
