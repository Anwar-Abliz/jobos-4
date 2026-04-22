"""JobOS 4.0 — Governance API Routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jobos.api.deps import get_governance_service
from jobos.services.governance_service import GovernanceService

router = APIRouter(prefix="/governance")


class CreatePolicyRequest(BaseModel):
    name: str
    policy_type: str = "access"
    rules: list[dict[str, Any]] | None = None
    enforcement: str = "advisory"
    owner: str = ""


class PolicyResponse(BaseModel):
    id: str
    name: str
    policy_type: str
    enforcement: str


class CheckPermissionRequest(BaseModel):
    actor: str
    action: str
    target_entity_id: str


class PermissionResponse(BaseModel):
    allowed: bool
    reason: str


@router.post("/policies", response_model=PolicyResponse)
async def create_policy(
    request: CreatePolicyRequest,
    svc: GovernanceService = Depends(get_governance_service),
):
    policy = await svc.create_policy(
        name=request.name,
        policy_type=request.policy_type,
        rules=request.rules,
        enforcement=request.enforcement,
        owner=request.owner,
    )
    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        policy_type=policy.properties.get("policy_type", ""),
        enforcement=policy.properties.get("enforcement", ""),
    )


@router.post("/check", response_model=PermissionResponse)
async def check_permission(
    request: CheckPermissionRequest,
    svc: GovernanceService = Depends(get_governance_service),
):
    result = await svc.check_permission(
        actor=request.actor,
        action=request.action,
        target_entity_id=request.target_entity_id,
    )
    return PermissionResponse(**result)


@router.get("/policies/{entity_id}")
async def get_policies(
    entity_id: str,
    svc: GovernanceService = Depends(get_governance_service),
):
    return await svc.get_policies_for_entity(entity_id)
