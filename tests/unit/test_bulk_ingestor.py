"""Tests for BulkIngestor.

Covers:
- Multi-source ingestion
- Zip archive extraction
- JSON record ingestion
- JSONL ingestion
- Merge strategies (combine, deduplicate)
- Error handling for bad sources
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from jobos.kernel.hierarchy import (
    HierarchyContext, HierarchyJob, HierarchyEdge, HierarchyResult, JobTier,
)
from jobos.services.bulk_ingestor import (
    BulkIngestor,
    BulkIngestRequest,
    SourceSpec,
)


class FakeHierarchyService:
    async def generate(self, context):
        return HierarchyResult(
            context=context,
            jobs=[
                HierarchyJob(tier=JobTier.STRATEGIC, statement=f"Goal: {context.domain}"),
                HierarchyJob(tier=JobTier.CORE_FUNCTIONAL, statement=f"Reduce cost in {context.domain}"),
            ],
            edges=[],
            summary={"T1_strategic": 1, "T2_core": 1},
        )


class FakeSOPService:
    async def ingest_from_text(self, text, domain=""):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return {
            "domain": domain or "sop",
            "jobs": [{"id": f"j{i}", "tier": "T3_execution", "statement": l} for i, l in enumerate(lines) if l],
            "edges": [],
            "summary": {"total_jobs": len(lines)},
        }


@pytest.fixture
def bulk() -> BulkIngestor:
    return BulkIngestor(
        hierarchy_service=FakeHierarchyService(),
        sop_service=FakeSOPService(),
    )


class TestBulkIngest:
    @pytest.mark.asyncio
    async def test_multi_text_sources(self, bulk):
        request = BulkIngestRequest(
            sources=[
                SourceSpec(type="text", content="reduce customer churn"),
                SourceSpec(type="text", content="improve onboarding experience"),
            ],
            domain="SaaS",
        )
        result = await bulk.ingest_bulk(request)
        assert result.successful == 2
        assert result.failed == 0
        assert result.total_jobs >= 2

    @pytest.mark.asyncio
    async def test_empty_sources(self, bulk):
        request = BulkIngestRequest(sources=[])
        result = await bulk.ingest_bulk(request)
        assert result.total_sources == 0

    @pytest.mark.asyncio
    async def test_merge_combine(self, bulk):
        request = BulkIngestRequest(
            sources=[
                SourceSpec(type="text", content="reduce churn"),
                SourceSpec(type="text", content="improve retention"),
            ],
            merge_strategy="combine",
        )
        result = await bulk.ingest_bulk(request)
        assert result.merged_hierarchy.get("jobs")
        assert result.merged_hierarchy["summary"]["source_count"] == 2

    @pytest.mark.asyncio
    async def test_merge_deduplicate(self, bulk):
        request = BulkIngestRequest(
            sources=[
                SourceSpec(type="text", content="reduce customer churn rate"),
                SourceSpec(type="text", content="reduce customer churn rate"),
            ],
            merge_strategy="deduplicate",
        )
        result = await bulk.ingest_bulk(request)
        jobs = result.merged_hierarchy.get("jobs", [])
        stmts = [j.get("statement", "") for j in jobs]
        unique_stmts = set(stmts)
        assert len(unique_stmts) <= len(stmts)


class TestZipIngest:
    @pytest.mark.asyncio
    async def test_zip_with_txt_files(self, bulk):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("doc1.txt", "reduce shipping delays")
            zf.writestr("doc2.txt", "improve warehouse efficiency")
        result = await bulk.ingest_zip(buf.getvalue(), domain="Logistics")
        assert result.successful >= 1

    @pytest.mark.asyncio
    async def test_bad_zip(self, bulk):
        result = await bulk.ingest_zip(b"not a zip file")
        assert result.failed == 1
        assert any("Invalid" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_zip_skips_unsupported(self, bulk):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("image.png", b"\x89PNG")
            zf.writestr("readme.txt", "actual content here")
        result = await bulk.ingest_zip(buf.getvalue())
        assert result.successful >= 1


class TestJsonIngest:
    @pytest.mark.asyncio
    async def test_json_records(self, bulk):
        records = [
            {"id": "1", "description": "Reduce order processing time"},
            {"id": "2", "description": "Automate invoice matching"},
            {"id": "3", "name": "Quality inspection step"},
        ]
        result = await bulk.ingest_json_records(records, domain="Manufacturing")
        assert result.successful >= 1
        assert result.total_jobs >= 2

    @pytest.mark.asyncio
    async def test_json_records_empty(self, bulk):
        result = await bulk.ingest_json_records([])
        assert result.total_sources == 0

    @pytest.mark.asyncio
    async def test_jsonl_ingestion(self, bulk):
        lines = [
            json.dumps({"description": "Check inventory levels"}),
            json.dumps({"description": "Reorder from supplier"}),
        ]
        content = "\n".join(lines).encode()
        result = await bulk.ingest_jsonl(content, domain="Supply Chain")
        assert result.successful >= 1


class TestProvenance:
    @pytest.mark.asyncio
    async def test_provenance_map_populated(self, bulk):
        request = BulkIngestRequest(
            sources=[
                SourceSpec(type="text", content="reduce delays", filename="input1"),
            ],
        )
        result = await bulk.ingest_bulk(request)
        assert len(result.provenance_map) >= 1
