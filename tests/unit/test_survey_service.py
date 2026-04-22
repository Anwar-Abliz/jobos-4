"""Tests for the survey service (using mocks)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from jobos.services.survey_service import SurveyService
from jobos.kernel.entity import EntityBase, EntityType


@pytest.fixture
def mock_graph():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def svc(mock_graph, mock_db):
    return SurveyService(graph=mock_graph, db=mock_db)


class TestCreateSurvey:
    async def test_create(self, svc, mock_graph):
        survey = await svc.create_survey(name="Test Survey")
        assert survey.entity_type == EntityType.SURVEY
        assert survey.name == "Test Survey"
        mock_graph.save_entity.assert_called_once()

    async def test_create_with_links(self, svc, mock_graph):
        survey = await svc.create_survey(
            name="Test", segment_id="seg1", process_id="proc1"
        )
        assert mock_graph.create_edge.call_count == 2


class TestGenerateOutcomes:
    async def test_template_fallback(self, svc, mock_graph):
        mock_graph.get_entity.return_value = EntityBase(
            id="s1",
            entity_type=EntityType.SURVEY,
            properties={"total_outcomes": 0},
        )

        outcomes = await svc.generate_outcomes("s1")
        # 3 contexts x 3 outcomes = 9
        assert len(outcomes) == 9
        for o in outcomes:
            assert o.entity_type == EntityType.OUTCOME


class TestAddOutcome:
    async def test_add(self, svc, mock_graph):
        outcome = await svc.add_outcome(
            survey_id="s1",
            text="Minimize the time it takes to process an order",
            context_label="Order Processing",
        )
        assert outcome.entity_type == EntityType.OUTCOME
        assert outcome.properties["direction"] == "minimize"
        mock_graph.save_entity.assert_called_once()
        mock_graph.create_edge.assert_called_once()

    async def test_maximize_direction(self, svc, mock_graph):
        outcome = await svc.add_outcome(
            survey_id="s1",
            text="Maximize the accuracy of data entry",
        )
        assert outcome.properties["direction"] == "maximize"


class TestSubmitResponse:
    async def test_submit(self, svc, mock_db):
        mock_db.save_survey_response.return_value = "resp1"

        result = await svc.submit_response(
            survey_id="s1",
            outcome_id="o1",
            session_id="sess1",
            importance=8.0,
            satisfaction=4.0,
        )
        assert result["opportunity_score"] == 12.0
        mock_db.save_survey_response.assert_called_once()


class TestSubmitBatch:
    async def test_batch(self, svc, mock_db):
        mock_db.save_survey_response.return_value = "resp1"

        results = await svc.submit_batch([
            {
                "survey_id": "s1",
                "outcome_id": "o1",
                "session_id": "sess1",
                "importance": 8.0,
                "satisfaction": 4.0,
            },
            {
                "survey_id": "s1",
                "outcome_id": "o2",
                "session_id": "sess1",
                "importance": 5.0,
                "satisfaction": 7.0,
            },
        ])
        assert len(results) == 2


class TestGetResults:
    async def test_results(self, svc, mock_db, mock_graph):
        mock_db.get_survey_aggregates.return_value = [
            {
                "outcome_id": "o1",
                "importance_mean": 8.0,
                "satisfaction_mean": 4.0,
                "opportunity_mean": 12.0,
                "response_count": 10,
            },
        ]
        mock_graph.get_entity.return_value = EntityBase(
            id="o1",
            statement="Minimize the time",
            entity_type=EntityType.OUTCOME,
            properties={"context_label": "Order"},
        )

        results = await svc.get_results("s1")
        assert results["total_outcomes"] == 1
        assert results["outcomes"][0]["statement"] == "Minimize the time"


class TestSyncToImperfections:
    async def test_sync(self, svc, mock_db, mock_graph):
        mock_db.get_survey_aggregates.return_value = [
            {
                "outcome_id": "o1",
                "importance_mean": 9.0,
                "satisfaction_mean": 3.0,
                "opportunity_mean": 15.0,
                "response_count": 10,
            },
            {
                "outcome_id": "o2",
                "importance_mean": 3.0,
                "satisfaction_mean": 8.0,
                "opportunity_mean": 3.0,
                "response_count": 10,
            },
        ]
        mock_graph.get_entity.return_value = EntityBase(
            id="o1",
            statement="Minimize the time it takes",
            entity_type=EntityType.OUTCOME,
        )

        imperfections = await svc.sync_to_imperfections("s1")
        # Only o1 has opp_score >= 10
        assert len(imperfections) == 1
        assert imperfections[0].entity_type == EntityType.IMPERFECTION
