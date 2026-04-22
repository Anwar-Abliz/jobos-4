"""Tests for the governance service (using mocks)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from jobos.services.governance_service import GovernanceService
from jobos.kernel.entity import EntityBase, EntityType


@pytest.fixture
def mock_graph():
    return AsyncMock()


@pytest.fixture
def svc(mock_graph):
    return GovernanceService(graph=mock_graph)


class TestCreatePolicy:
    async def test_create(self, svc, mock_graph):
        policy = await svc.create_policy(
            name="Test Policy",
            policy_type="access",
            rules=[{"action": "deny", "condition": "delete"}],
        )
        assert policy.name == "Test Policy"
        assert policy.entity_type == EntityType.POLICY
        mock_graph.save_entity.assert_called_once()


class TestCheckPermission:
    async def test_no_entity(self, svc, mock_graph):
        mock_graph.get_entity.return_value = None

        result = await svc.check_permission("user1", "create", "missing")
        assert result["allowed"] is True

    async def test_no_policies(self, svc, mock_graph):
        entity = EntityBase(id="e1", entity_type=EntityType.SAP_PROCESS)
        mock_graph.get_entity.return_value = entity
        mock_graph.get_neighbors.return_value = []

        result = await svc.check_permission("user1", "create", "e1")
        assert result["allowed"] is True

    async def test_with_deny_policy(self, svc, mock_graph):
        entity = EntityBase(id="e1", entity_type=EntityType.SAP_PROCESS)
        mock_graph.get_entity.return_value = entity

        policy = EntityBase(
            id="p1",
            entity_type=EntityType.POLICY,
            properties={
                "policy_type": "access",
                "rules": [
                    {
                        "rule_id": "R1",
                        "policy_id": "p1",
                        "condition": "delete",
                        "action": "deny",
                        "scope": {"entity_types": ["sap_process"]},
                    }
                ],
            },
        )
        mock_graph.get_neighbors.return_value = [policy]

        result = await svc.check_permission("user1", "delete", "e1")
        assert result["allowed"] is False


class TestGetPolicies:
    async def test_get(self, svc, mock_graph):
        policy = EntityBase(
            id="p1",
            name="Test",
            entity_type=EntityType.POLICY,
            properties={"policy_type": "access"},
        )
        mock_graph.get_neighbors.return_value = [policy]

        result = await svc.get_policies_for_entity("e1")
        assert len(result) == 1
        assert result[0]["name"] == "Test"
