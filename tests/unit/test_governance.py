"""Tests for the governance model."""
from __future__ import annotations

from jobos.kernel.governance import (
    AccessLevel,
    GovernanceScope,
    GovernanceRule,
    evaluate_governance,
)


class TestAccessLevel:
    def test_values(self):
        assert AccessLevel.VIEWER == "viewer"
        assert AccessLevel.ADMIN == "admin"


class TestGovernanceScope:
    def test_defaults(self):
        scope = GovernanceScope()
        assert scope.entity_types == []
        assert scope.org_units == []
        assert scope.sap_modules == []

    def test_serialize(self):
        scope = GovernanceScope(
            entity_types=["sap_process"],
            org_units=["1000"],
            sap_modules=["SD"],
        )
        data = scope.model_dump()
        assert data["sap_modules"] == ["SD"]


class TestGovernanceRule:
    def test_defaults(self):
        rule = GovernanceRule()
        assert rule.action == "allow"
        assert rule.priority == 0

    def test_serialize(self):
        rule = GovernanceRule(
            rule_id="R1",
            policy_id="P1",
            condition="delete",
            action="deny",
            scope=GovernanceScope(entity_types=["sap_process"]),
            priority=10,
        )
        data = rule.model_dump()
        assert data["action"] == "deny"


class TestEvaluateGovernance:
    def test_no_policies(self):
        allowed, reason = evaluate_governance("user1", "create", {}, [])
        assert allowed is True
        assert reason == "no policies configured"

    def test_allow_when_no_matching_rules(self):
        policies = [{"rules": []}]
        allowed, reason = evaluate_governance(
            "user1", "create", {"entity_type": "job"}, policies
        )
        assert allowed is True
        assert reason == "allowed"

    def test_deny_rule(self):
        policies = [
            {
                "rules": [
                    {
                        "rule_id": "R1",
                        "policy_id": "P1",
                        "condition": "delete",
                        "action": "deny",
                        "scope": {"entity_types": ["sap_process"]},
                    }
                ]
            }
        ]
        allowed, reason = evaluate_governance(
            "user1",
            "delete",
            {"entity_type": "sap_process"},
            policies,
        )
        assert allowed is False
        assert "denied by rule R1" in reason

    def test_require_approval_rule(self):
        policies = [
            {
                "rules": [
                    {
                        "rule_id": "R2",
                        "policy_id": "P1",
                        "condition": "create",
                        "action": "require_approval",
                        "scope": {"entity_types": ["policy"]},
                    }
                ]
            }
        ]
        allowed, reason = evaluate_governance(
            "user1",
            "create",
            {"entity_type": "policy"},
            policies,
        )
        assert allowed is False
        assert "requires approval" in reason

    def test_scope_mismatch_allows(self):
        policies = [
            {
                "rules": [
                    {
                        "rule_id": "R1",
                        "policy_id": "P1",
                        "condition": "delete",
                        "action": "deny",
                        "scope": {"entity_types": ["sap_process"]},
                    }
                ]
            }
        ]
        allowed, reason = evaluate_governance(
            "user1",
            "delete",
            {"entity_type": "job"},
            policies,
        )
        assert allowed is True

    def test_org_unit_scope(self):
        policies = [
            {
                "rules": [
                    {
                        "rule_id": "R3",
                        "policy_id": "P2",
                        "condition": "create",
                        "action": "deny",
                        "scope": {"org_units": ["2000"]},
                    }
                ]
            }
        ]
        allowed, _ = evaluate_governance(
            "user1",
            "create",
            {"entity_type": "sap_object", "org_unit": "2000"},
            policies,
        )
        assert allowed is False

        allowed, _ = evaluate_governance(
            "user1",
            "create",
            {"entity_type": "sap_object", "org_unit": "1000"},
            policies,
        )
        assert allowed is True
