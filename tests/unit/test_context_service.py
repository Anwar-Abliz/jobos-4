"""Tests for the context service (using mocks)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from jobos.services.context_service import ContextService
from jobos.kernel.entity import EntityBase, EntityType


@pytest.fixture
def mock_graph():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def svc(mock_graph, mock_db):
    return ContextService(graph=mock_graph, db=mock_db)


class TestCaptureContextSnapshot:
    async def test_capture_success(self, svc, mock_graph, mock_db):
        entity = EntityBase(
            id="e1", name="Test", entity_type=EntityType.SAP_PROCESS
        )
        mock_graph.get_entity.return_value = entity
        mock_graph.get_neighbors.return_value = []
        mock_graph.get_edges.return_value = []
        mock_db.save_context_snapshot.return_value = "snap1"

        result = await svc.capture_context_snapshot("e1")
        assert result["snapshot_id"] == "snap1"
        assert result["entity_id"] == "e1"

    async def test_capture_entity_not_found(self, svc, mock_graph):
        mock_graph.get_entity.return_value = None

        result = await svc.capture_context_snapshot("missing")
        assert "error" in result


class TestDetectContextDecay:
    async def test_no_snapshots(self, svc, mock_db):
        mock_db.get_context_snapshots.return_value = []

        result = await svc.detect_context_decay("e1")
        assert result["stale"] is True
        assert result["freshness"] == "stale"

    async def test_recent_snapshot(self, svc, mock_db):
        mock_db.get_context_snapshots.return_value = [
            {"captured_at": datetime.now(timezone.utc)}
        ]

        result = await svc.detect_context_decay("e1", threshold_hours=24.0)
        assert result["stale"] is False
        assert result["freshness"] == "live"

    async def test_old_snapshot(self, svc, mock_db):
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        mock_db.get_context_snapshots.return_value = [
            {"captured_at": old_time}
        ]

        result = await svc.detect_context_decay("e1", threshold_hours=24.0)
        assert result["stale"] is True


class TestInferRelationships:
    async def test_no_llm(self, svc, mock_graph):
        entity = EntityBase(id="e1", entity_type=EntityType.SAP_PROCESS)
        mock_graph.get_entity.return_value = entity

        result = await svc.infer_relationships("e1")
        assert result["inferred"] == []
        assert "LLM not available" in result.get("note", "")


class TestMergeContextUpdates:
    async def test_merge(self, svc, mock_graph):
        entity = EntityBase(
            id="e1",
            entity_type=EntityType.SAP_PROCESS,
            properties={"automation_level": 0.3},
        )
        mock_graph.get_entity.return_value = entity

        result = await svc.merge_context_updates("e1", {"automation_level": 0.7})
        assert result["updated_fields"] == ["automation_level"]
        mock_graph.save_entity.assert_called_once()
