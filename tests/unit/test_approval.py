"""Tests for approval gates.

Covers:
- requires_approval returns True for fire on HUMAN executor
- requires_approval returns False for fire on AI executor
- requires_approval returns False when enforcement_mode=permissive
- approve() sets status and resolved_by
- reject() sets status, resolved_by, and reason
- ApprovalRequest creation with defaults
"""
from __future__ import annotations

import pytest

from jobos.kernel.approval import (
    ApprovalRequest,
    ApprovalStatus,
    approve,
    reject,
    requires_approval,
)
from jobos.kernel.entity import EntityBase, EntityType


def _make_executor(executor_type: str = "HUMAN") -> EntityBase:
    return EntityBase(
        id="exec01",
        name="Test Executor",
        entity_type=EntityType.EXECUTOR,
        properties={"executor_type": executor_type},
    )


class TestRequiresApproval:
    def test_fire_on_human_requires_approval(self):
        entity = _make_executor("HUMAN")
        assert requires_approval("fire", entity) is True

    def test_switch_on_human_requires_approval(self):
        entity = _make_executor("HUMAN")
        assert requires_approval("switch", entity) is True

    def test_fire_on_ai_does_not_require_approval(self):
        entity = _make_executor("AI")
        assert requires_approval("fire", entity) is False

    def test_switch_on_ai_does_not_require_approval(self):
        entity = _make_executor("AI")
        assert requires_approval("switch", entity) is False

    def test_permissive_mode_skips_approval(self):
        entity = _make_executor("HUMAN")
        assert requires_approval("fire", entity, enforcement_mode="permissive") is False

    def test_hire_never_requires_approval(self):
        entity = _make_executor("HUMAN")
        assert requires_approval("hire", entity) is False


class TestApproveReject:
    def test_approve_sets_status_and_resolver(self):
        request = ApprovalRequest(
            entity_id="e1",
            action="fire",
        )
        approved = approve(request, approver="admin@example.com")

        assert approved.status == ApprovalStatus.APPROVED
        assert approved.resolved_by == "admin@example.com"
        assert approved.resolved_at is not None

    def test_reject_sets_status_resolver_and_reason(self):
        request = ApprovalRequest(
            entity_id="e1",
            action="fire",
        )
        rejected = reject(request, approver="manager", reason="Insufficient evidence")

        assert rejected.status == ApprovalStatus.REJECTED
        assert rejected.resolved_by == "manager"
        assert rejected.reason == "Insufficient evidence"
        assert rejected.resolved_at is not None

    def test_original_request_unchanged_after_approve(self):
        request = ApprovalRequest(entity_id="e1", action="fire")
        approve(request, approver="admin")
        assert request.status == ApprovalStatus.PENDING


class TestApprovalRequestDefaults:
    def test_default_status_is_pending(self):
        req = ApprovalRequest()
        assert req.status == ApprovalStatus.PENDING

    def test_default_fields(self):
        req = ApprovalRequest()
        assert req.entity_id == ""
        assert req.action == ""
        assert req.requester == "system"
        assert req.approvers == []
        assert req.reason == ""
        assert req.resolved_by == ""
        assert req.resolved_at is None
        assert req.context_snapshot == {}

    def test_request_id_generated(self):
        req1 = ApprovalRequest()
        req2 = ApprovalRequest()
        assert req1.request_id != req2.request_id
        assert len(req1.request_id) == 12
