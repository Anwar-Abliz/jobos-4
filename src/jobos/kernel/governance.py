"""JobOS 4.0 — Governance Model (Kernel).

Defines access levels, governance scopes, rules, and policy evaluation.
Phase 1: lightweight — evaluate_governance always allows. The structure
is in place for Phase 2+ enforcement.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AccessLevel(str, Enum):
    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    APPROVER = "approver"
    ADMIN = "admin"


class GovernanceScope(BaseModel):
    """Defines what a governance rule applies to."""
    entity_types: list[str] = Field(default_factory=list)
    org_units: list[str] = Field(default_factory=list)
    sap_modules: list[str] = Field(default_factory=list)


class GovernanceRule(BaseModel):
    """A single governance rule within a policy."""
    rule_id: str = ""
    policy_id: str = ""
    condition: str = ""
    action: str = "allow"  # allow | deny | require_approval | log
    scope: GovernanceScope = Field(default_factory=GovernanceScope)
    priority: int = 0


def evaluate_governance(
    actor: str,
    action: str,
    target_entity: dict[str, Any],
    policies: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Evaluate governance policies for an action.

    Phase 1: always returns (True, "no policies configured") unless
    a blocking rule explicitly matches.

    Args:
        actor: ID or name of the acting user/system.
        action: The action being attempted (e.g., "create", "delete", "approve").
        target_entity: Dict with at least entity_type and optional org_unit.
        policies: List of policy dicts, each with 'rules' key.

    Returns:
        Tuple of (allowed: bool, reason: str).
    """
    if not policies:
        return True, "no policies configured"

    for policy in policies:
        rules = policy.get("rules", [])
        for rule_data in rules:
            rule = (
                GovernanceRule.model_validate(rule_data)
                if isinstance(rule_data, dict) else rule_data
            )
            if _rule_matches(rule, actor, action, target_entity):
                if rule.action == "deny":
                    return False, f"denied by rule {rule.rule_id} in policy {rule.policy_id}"
                if rule.action == "require_approval":
                    return False, f"requires approval per rule {rule.rule_id}"

    return True, "allowed"


def _rule_matches(
    rule: GovernanceRule,
    actor: str,
    action: str,
    target_entity: dict[str, Any],
) -> bool:
    """Check if a governance rule's scope matches the target."""
    scope = rule.scope

    # Check entity type scope
    if scope.entity_types:
        entity_type = target_entity.get("entity_type", "")
        if entity_type not in scope.entity_types:
            return False

    # Check org unit scope
    if scope.org_units:
        org_unit = target_entity.get("org_unit", "")
        if org_unit not in scope.org_units:
            return False

    # Check SAP module scope
    if scope.sap_modules:
        sap_module = target_entity.get("sap_module", "")
        if sap_module not in scope.sap_modules:
            return False

    # Check condition (simple string match for Phase 1)
    return not (rule.condition and rule.condition != action)
