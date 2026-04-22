"""Tests for context ingestion pipeline."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from jobos.pipeline.context_ingestion import ContextIngestionPipeline


@pytest.fixture
def mock_graph():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def pipeline(mock_graph, mock_db):
    return ContextIngestionPipeline(graph=mock_graph, db=mock_db)


class TestPipelineRun:
    async def test_empty_data(self, pipeline, mock_graph):
        mock_graph.save_entity.return_value = "e1"

        result = await pipeline.run({"entities": [], "edges": []})
        assert result["success"] is True
        assert len(result["stages"]) == 5

    async def test_single_entity(self, pipeline, mock_graph):
        mock_graph.save_entity.return_value = "e1"

        result = await pipeline.run({
            "entities": [
                {
                    "name": "Test Process",
                    "entity_type": "sap_process",
                    "properties": {"sap_module": "SD"},
                }
            ],
            "edges": [],
        })
        assert result["success"] is True
        mock_graph.save_entity.assert_called_once()

    async def test_with_edges(self, pipeline, mock_graph):
        mock_graph.save_entity.return_value = "e1"

        result = await pipeline.run({
            "entities": [
                {"name": "P1", "entity_type": "sap_process", "properties": {}},
                {"name": "T1", "entity_type": "sap_transaction", "properties": {}},
            ],
            "edges": [
                {"source_id": "id1", "target_id": "id2", "edge_type": "EXECUTED_BY"},
            ],
        })
        assert result["success"] is True
        assert mock_graph.save_entity.call_count == 2
        mock_graph.create_edge.assert_called_once()

    async def test_invalid_entity_type(self, pipeline, mock_graph):
        result = await pipeline.run({
            "entities": [
                {"name": "Bad", "entity_type": "invalid_type", "properties": {}},
            ],
            "edges": [],
        })
        # Transform stage should fail
        assert result["success"] is False

    async def test_all_stages_present(self, pipeline, mock_graph):
        mock_graph.save_entity.return_value = "e1"

        result = await pipeline.run({"entities": [], "edges": []})
        stage_names = [s["name"] for s in result["stages"]]
        assert stage_names == ["EXTRACT", "TRANSFORM", "ENRICH", "VALIDATE", "PERSIST"]
