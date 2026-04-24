"""Tests for SOP ingestion service.

Covers:
- _heuristic_extract_steps parses numbered lists
- _heuristic_extract_steps parses bullet lists
- ingest_from_text returns jobs and edges
- Empty text returns error
"""
from __future__ import annotations

import pytest

from jobos.services.sop_ingestion_service import SOPIngestionService


@pytest.fixture
def service() -> SOPIngestionService:
    return SOPIngestionService(llm=None, graph=None)


class TestHeuristicExtractSteps:
    def test_parses_numbered_list(self, service: SOPIngestionService):
        text = (
            "1. Review the incoming request\n"
            "2. Validate the request parameters\n"
            "3. Process the approved request\n"
        )
        steps = service._heuristic_extract_steps(text)

        assert len(steps) == 3
        assert steps[0]["statement"] == "Review the incoming request"
        assert steps[0]["order"] == 1
        assert steps[2]["statement"] == "Process the approved request"
        assert steps[2]["order"] == 3

    def test_parses_numbered_list_parenthesis(self, service: SOPIngestionService):
        text = (
            "1) Configure the system parameters\n"
            "2) Execute the migration process\n"
        )
        steps = service._heuristic_extract_steps(text)
        assert len(steps) == 2
        assert steps[0]["statement"] == "Configure the system parameters"

    def test_parses_bullet_list_dash(self, service: SOPIngestionService):
        text = (
            "- Review all incoming documents\n"
            "- Classify each document by type\n"
            "- Archive processed documents\n"
        )
        steps = service._heuristic_extract_steps(text)

        assert len(steps) == 3
        assert steps[0]["statement"] == "Review all incoming documents"
        assert steps[1]["statement"] == "Classify each document by type"

    def test_parses_bullet_list_asterisk(self, service: SOPIngestionService):
        text = (
            "* Prepare the environment for deployment\n"
            "* Deploy the application to staging\n"
        )
        steps = service._heuristic_extract_steps(text)
        assert len(steps) == 2
        assert steps[0]["statement"] == "Prepare the environment for deployment"

    def test_skips_short_items(self, service: SOPIngestionService):
        text = (
            "1. OK\n"
            "2. Validate the full configuration\n"
        )
        steps = service._heuristic_extract_steps(text)
        # "OK" is too short (len <= 5), should be skipped
        assert len(steps) == 1
        assert steps[0]["statement"] == "Validate the full configuration"

    def test_skips_blank_lines(self, service: SOPIngestionService):
        text = (
            "\n"
            "1. Perform initial assessment\n"
            "\n"
            "2. Generate the final report\n"
            "\n"
        )
        steps = service._heuristic_extract_steps(text)
        assert len(steps) == 2

    def test_step_prefix_format(self, service: SOPIngestionService):
        text = "Step 1: Initialize the database connection\n"
        steps = service._heuristic_extract_steps(text)
        assert len(steps) == 1
        assert steps[0]["statement"] == "Initialize the database connection"


class TestIngestFromText:
    @pytest.mark.asyncio
    async def test_returns_jobs_and_edges(self, service: SOPIngestionService):
        text = (
            "1. Achieve strategic alignment across teams\n"
            "2. Reduce processing errors in production\n"
            "3. Implement the validation pipeline\n"
            "4. Verify all output parameters\n"
        )
        result = await service.ingest_from_text(text=text, domain="test_domain")

        assert "error" not in result
        assert result["domain"] == "test_domain"
        assert len(result["jobs"]) == 4
        assert result["summary"]["source"] == "sop_ingest"

        # Jobs should have tier assignments
        tiers = [j["tier"] for j in result["jobs"]]
        assert all(t.startswith("T") for t in tiers)

    @pytest.mark.asyncio
    async def test_generates_edges(self, service: SOPIngestionService):
        text = (
            "1. Define strategic objectives for growth\n"
            "2. Reduce error rate across systems\n"
            "3. Deploy the monitoring solution\n"
        )
        result = await service.ingest_from_text(text=text, domain="test")

        # Edges connect lower tiers to higher tiers
        assert "edges" in result
        assert result["summary"]["total_edges"] == len(result["edges"])

    @pytest.mark.asyncio
    async def test_empty_text_returns_error(self, service: SOPIngestionService):
        result = await service.ingest_from_text(text="", domain="empty")
        assert "error" in result
        assert "No process steps" in result["error"]

    @pytest.mark.asyncio
    async def test_no_parseable_steps_returns_error(self, service: SOPIngestionService):
        result = await service.ingest_from_text(
            text="This is just a paragraph with no structure at all.",
            domain="unstructured",
        )
        assert "error" in result
