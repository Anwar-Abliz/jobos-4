"""Tests for UniversalIngestor.

Covers:
- Keyword/text input → hierarchy generation
- Numbered text → SOP extraction path
- CSV with tier columns → direct CSV parsing
- Domain inference from context
- Empty input → warning
- Mixed input (text + file) → merge
- File extraction routing
"""
from __future__ import annotations

import pytest

from jobos.adapters.extraction.context_builder import ContextSummary
from jobos.kernel.hierarchy import HierarchyContext, HierarchyJob, HierarchyEdge, HierarchyResult, JobTier
from jobos.services.universal_ingestor import (
    IngestRequest,
    IngestResult,
    UniversalIngestor,
)


# ─── Fakes ──────────────────────────────────────────────

class FakeHierarchyService:
    def __init__(self) -> None:
        self.last_context: HierarchyContext | None = None

    async def generate(self, context: HierarchyContext) -> HierarchyResult:
        self.last_context = context
        return HierarchyResult(
            context=context,
            jobs=[
                HierarchyJob(
                    tier=JobTier.STRATEGIC,
                    statement=f"Achieve {context.domain} goals",
                ),
                HierarchyJob(
                    tier=JobTier.CORE_FUNCTIONAL,
                    statement=f"Reduce cost in {context.domain}",
                ),
            ],
            edges=[],
            summary={"T1_strategic": 1, "T2_core": 1},
        )


class FakeSOPService:
    async def ingest_from_text(self, text: str, domain: str = "") -> dict:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return {
            "domain": domain or "sop",
            "jobs": [
                {"id": f"j{i}", "tier": "T3_execution", "statement": l}
                for i, l in enumerate(lines) if l
            ],
            "edges": [],
            "summary": {"total_jobs": len(lines), "source": "sop_ingest"},
        }


# ─── Tests ──────────────────────────────────────────────

class TestUniversalIngestor:

    @pytest.fixture
    def ingestor(self) -> UniversalIngestor:
        return UniversalIngestor(
            hierarchy_service=FakeHierarchyService(),
            sop_service=FakeSOPService(),
        )

    @pytest.mark.asyncio
    async def test_empty_input_returns_warning(self, ingestor):
        result = await ingestor.ingest(IngestRequest())
        assert len(result.warnings) > 0
        assert "No input" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_keyword_input_generates_hierarchy(self, ingestor):
        result = await ingestor.ingest(IngestRequest(text="customer churn"))
        assert result.hierarchy is not None
        assert len(result.hierarchy.jobs) >= 1
        assert result.source_type == "text_to_hierarchy"

    @pytest.mark.asyncio
    async def test_goal_input_generates_hierarchy(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(
                text="Reduce patient readmission rates",
                goal="Improve patient outcomes",
                domain="Healthcare",
            )
        )
        assert result.hierarchy is not None
        assert result.domain_detected == "Healthcare"

    @pytest.mark.asyncio
    async def test_numbered_text_routes_to_sop(self, ingestor):
        text = """1. Receive the order
2. Check inventory availability
3. Pick items from warehouse
4. Pack the shipment
5. Generate shipping label"""
        result = await ingestor.ingest(IngestRequest(text=text))
        assert result.source_type == "sop_steps"
        assert result.hierarchy_raw.get("jobs")
        assert len(result.hierarchy_raw["jobs"]) >= 3

    @pytest.mark.asyncio
    async def test_bullet_text_routes_to_sop(self, ingestor):
        text = """- Define project scope
- Identify stakeholders
- Create project plan
- Execute deliverables"""
        result = await ingestor.ingest(IngestRequest(text=text))
        assert result.source_type == "sop_steps"

    @pytest.mark.asyncio
    async def test_csv_hierarchy_direct_parse(self, ingestor):
        csv_content = b"Tier 1,Tier 2,Tier 3\nReduce churn,Improve onboarding,Design welcome flow\n"
        result = await ingestor.ingest(
            IngestRequest(files=[(csv_content, "hierarchy.csv")])
        )
        assert result.source_type == "csv_hierarchy"
        assert result.hierarchy_raw.get("jobs")
        assert result.hierarchy_raw["domain"] == "Reduce churn"

    @pytest.mark.asyncio
    async def test_txt_file_extraction(self, ingestor):
        content = b"Our goal is to reduce customer acquisition cost below $50"
        result = await ingestor.ingest(
            IngestRequest(files=[(content, "strategy.txt")])
        )
        assert result.hierarchy is not None or result.hierarchy_raw
        assert "file:strategy.txt" in result.provenance.get("sources", [])

    @pytest.mark.asyncio
    async def test_domain_inference_from_context(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(text="We need to improve hospital discharge planning")
        )
        assert result.domain_detected

    @pytest.mark.asyncio
    async def test_domain_override(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(text="some text", domain="Manufacturing")
        )
        assert result.domain_detected == "Manufacturing"

    @pytest.mark.asyncio
    async def test_provenance_tracking(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(text="reduce churn")
        )
        sources = result.provenance.get("sources", [])
        assert "text:direct_input" in sources

    @pytest.mark.asyncio
    async def test_unsupported_file_warns(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(
                text="fallback text",
                files=[(b"binary data", "image.png")],
            )
        )
        assert any("Unsupported" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_context_populated(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(text="We need to reduce shipping delays in our warehouse")
        )
        assert result.context is not None
        assert isinstance(result.context, ContextSummary)

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self, ingestor):
        result = await ingestor.ingest(
            IngestRequest(text="reduce churn")
        )
        d = result.to_dict()
        assert "hierarchy" in d
        assert "context" in d
        assert "provenance" in d
        assert "source_type" in d


class TestMergeTexts:
    def test_deduplicates_identical(self):
        ingestor = UniversalIngestor()
        merged = ingestor._merge_texts(["hello", "hello", "world"])
        assert merged.count("hello") == 1
        assert "world" in merged

    def test_empty_list(self):
        ingestor = UniversalIngestor()
        assert ingestor._merge_texts([]) == ""

    def test_strips_whitespace(self):
        ingestor = UniversalIngestor()
        merged = ingestor._merge_texts(["  hello  ", ""])
        assert "hello" in merged


class TestLooksLikeSteps:
    def test_numbered_list(self):
        ingestor = UniversalIngestor()
        text = "1. Step one\n2. Step two\n3. Step three"
        assert ingestor._looks_like_steps(text) is True

    def test_bullet_list(self):
        ingestor = UniversalIngestor()
        text = "- Step one\n- Step two\n- Step three"
        assert ingestor._looks_like_steps(text) is True

    def test_prose_text(self):
        ingestor = UniversalIngestor()
        text = "We want to reduce churn by improving the onboarding experience."
        assert ingestor._looks_like_steps(text) is False


class TestInferDomain:
    def test_from_where(self):
        ingestor = UniversalIngestor()
        ctx = ContextSummary(where="Healthcare")
        assert ingestor._infer_domain(ctx) == "Healthcare"

    def test_from_keywords(self):
        ingestor = UniversalIngestor()
        ctx = ContextSummary(keywords=["supply", "chain", "logistics"])
        assert "supply" in ingestor._infer_domain(ctx)

    def test_from_what(self):
        ingestor = UniversalIngestor()
        ctx = ContextSummary(what="Reduce customer churn in SaaS products")
        assert "Reduce" in ingestor._infer_domain(ctx)

    def test_fallback_general(self):
        ingestor = UniversalIngestor()
        ctx = ContextSummary()
        assert ingestor._infer_domain(ctx) == "general"
