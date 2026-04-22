"""Tests for customer perspective service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from jobos.services.customer_perspective_service import CustomerPerspectiveService
from jobos.kernel.entity import EntityBase, EntityType


@pytest.fixture
def mock_graph():
    return AsyncMock()


@pytest.fixture
def svc(mock_graph):
    return CustomerPerspectiveService(graph=mock_graph)


class TestMapProcessToJobs:
    async def test_not_found(self, svc, mock_graph):
        mock_graph.get_entity.return_value = None
        result = await svc.map_process_to_jobs("missing")
        assert "error" in result

    async def test_mapping(self, svc, mock_graph):
        process = EntityBase(id="p1", name="O2C", entity_type=EntityType.SAP_PROCESS)
        step = EntityBase(
            id="s1", name="Create Order",
            entity_type=EntityType.SAP_TRANSACTION,
            properties={"tcode": "VA01"},
        )
        job = EntityBase(
            id="j1", statement="Create sales order",
            entity_type=EntityType.JOB,
        )

        mock_graph.get_entity.return_value = process
        mock_graph.get_neighbors.side_effect = [
            [step],  # EXECUTED_BY
            [job],   # HIRES on step
        ]

        result = await svc.map_process_to_jobs("p1")
        assert result["total_steps"] == 1
        assert result["mapped_steps"] == 1
        assert result["coverage_pct"] == 100.0


class TestIdentifyPainPoints:
    async def test_no_imperfections(self, svc, mock_graph):
        process = EntityBase(id="p1", name="O2C", entity_type=EntityType.SAP_PROCESS)
        step = EntityBase(id="s1", name="Step 1", entity_type=EntityType.SAP_TRANSACTION)

        mock_graph.get_entity.return_value = process
        mock_graph.get_neighbors.side_effect = [
            [step],  # EXECUTED_BY
            [],      # OCCURS_IN
        ]

        result = await svc.identify_pain_points("p1")
        assert result["total_pain_points"] == 0

    async def test_with_imperfections(self, svc, mock_graph):
        process = EntityBase(id="p1", name="O2C", entity_type=EntityType.SAP_PROCESS)
        step = EntityBase(id="s1", name="Step 1", entity_type=EntityType.SAP_TRANSACTION)
        imp = EntityBase(
            id="i1",
            statement="Pricing errors",
            entity_type=EntityType.IMPERFECTION,
            properties={"severity": 0.8},
        )

        mock_graph.get_entity.return_value = process
        mock_graph.get_neighbors.side_effect = [
            [step],  # EXECUTED_BY
            [imp],   # OCCURS_IN
        ]

        result = await svc.identify_pain_points("p1")
        assert result["total_pain_points"] == 1
        assert result["pain_points"][0]["severity"] == 0.8


class TestGenerateCustomerJourney:
    async def test_journey(self, svc, mock_graph):
        process = EntityBase(id="p1", name="O2C", entity_type=EntityType.SAP_PROCESS)
        step = EntityBase(
            id="s1", name="Create Sales Order",
            entity_type=EntityType.SAP_TRANSACTION,
            properties={"tcode": "VA01"},
        )

        mock_graph.get_entity.return_value = process
        mock_graph.get_neighbors.side_effect = [
            [step],  # EXECUTED_BY
            [],      # OPERATES_ON
            [],      # SURVEYED_BY
        ]

        result = await svc.generate_customer_journey("p1")
        assert result["total_stages"] == 1
        assert result["journey_stages"][0]["customer_visible"] is True
