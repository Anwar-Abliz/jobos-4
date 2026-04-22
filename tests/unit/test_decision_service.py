"""Tests for the decision service (using mocks)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from jobos.services.decision_service import DecisionService
from jobos.kernel.entity import EntityBase, EntityType


@pytest.fixture
def mock_graph():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def svc(mock_graph, mock_db):
    return DecisionService(graph=mock_graph, db=mock_db)


class TestRecordDecision:
    async def test_record(self, svc, mock_graph, mock_db):
        mock_db.save_decision_trace.return_value = "trace1"

        trace = await svc.record_decision(
            actor="system",
            action="hire",
            target_entity_id="e1",
            rationale="Best EFE",
        )

        assert trace.actor == "system"
        assert trace.action == "hire"
        mock_graph.save_entity.assert_called_once()
        mock_graph.create_edge.assert_called_once()
        mock_db.save_decision_trace.assert_called_once()


class TestGetDecisionTrail:
    async def test_trail(self, svc, mock_graph, mock_db):
        mock_graph.get_neighbors.return_value = []
        mock_db.get_decision_traces.return_value = [
            {"id": "d1", "action": "hire"},
            {"id": "d2", "action": "evaluate"},
        ]

        trail = await svc.get_decision_trail("e1", depth=10)
        assert len(trail) == 2


class TestExplainDecision:
    async def test_explain(self, svc, mock_graph):
        entity = EntityBase(
            id="d1",
            entity_type=EntityType.DECISION,
            properties={
                "actor": "system",
                "decision_type": "hire",
                "rationale": "Best EFE score",
                "context_snapshot": {"vfe": 0.3},
                "alternatives_considered": [],
            },
        )
        mock_graph.get_entity.return_value = entity

        result = await svc.explain_decision("d1")
        assert result["actor"] == "system"
        assert result["rationale"] == "Best EFE score"

    async def test_explain_not_found(self, svc, mock_graph):
        mock_graph.get_entity.return_value = None

        result = await svc.explain_decision("missing")
        assert "error" in result
