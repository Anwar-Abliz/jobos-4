"""Tests for ContextEnrichmentEngine.

Covers:
- Relationship inference from keyword overlap
- Coverage scoring
- Cross-source overlap detection
- Empty graph handling
"""
from __future__ import annotations

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.engines.context_enrichment import (
    ContextEnrichmentEngine,
    EnrichmentResult,
)


class FakeGraphPort:
    def __init__(self) -> None:
        self.entities: dict[str, EntityBase] = {}
        self.edges: list[tuple[str, str, str]] = []

    async def get_entity(self, eid: str) -> EntityBase | None:
        return self.entities.get(eid)

    async def list_entities(self, limit: int = 500, **kwargs) -> list[EntityBase]:
        return list(self.entities.values())[:limit]

    async def create_edge(self, src: str, tgt: str, etype: str) -> str:
        self.edges.append((src, tgt, etype))
        return f"{src}-{etype}-{tgt}"

    async def get_neighbors(self, eid, **kwargs):
        return []


def make_entity(
    eid: str, etype: EntityType, statement: str,
    provenance: str = "user", provenance_source: str = "",
    **props,
) -> EntityBase:
    return EntityBase(
        id=eid, name=eid, statement=statement,
        entity_type=etype, provenance=provenance,
        provenance_source=provenance_source,
        properties=props,
    )


class TestEnrichment:
    @pytest.fixture
    def graph(self) -> FakeGraphPort:
        return FakeGraphPort()

    @pytest.fixture
    def engine(self, graph) -> ContextEnrichmentEngine:
        return ContextEnrichmentEngine(graph=graph)

    @pytest.mark.asyncio
    async def test_empty_graph(self, engine):
        result = await engine.enrich()
        assert result.entities_enriched == 0
        assert "No entities" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_infer_metric_to_job_relationship(self, graph, engine):
        job = make_entity("j1", EntityType.JOB, "Reduce customer churn rate")
        metric = make_entity("m1", EntityType.METRIC, "Customer churn rate measurement")
        graph.entities = {"j1": job, "m1": metric}

        result = await engine.enrich()
        assert result.relationships_inferred >= 1
        assert any(e[2] == "MEASURED_BY" for e in graph.edges)

    @pytest.mark.asyncio
    async def test_infer_imperfection_to_job(self, graph, engine):
        job = make_entity("j1", EntityType.JOB, "Improve warehouse shipping speed")
        imp = make_entity("i1", EntityType.IMPERFECTION, "Warehouse shipping delays are excessive")
        graph.entities = {"j1": job, "i1": imp}

        result = await engine.enrich()
        assert result.relationships_inferred >= 1
        assert any(e[2] == "OCCURS_IN" for e in graph.edges)

    @pytest.mark.asyncio
    async def test_coverage_scoring(self, graph, engine):
        job = make_entity(
            "j1", EntityType.JOB, "Reduce churn",
            provenance="llm", level=0,
        )
        graph.entities = {"j1": job}

        result = await engine.enrich()
        assert 0.0 < result.coverage_score <= 1.0

    @pytest.mark.asyncio
    async def test_coverage_empty_statement(self, graph, engine):
        job = make_entity("j1", EntityType.JOB, "")
        graph.entities = {"j1": job}

        result = await engine.enrich()
        assert result.coverage_score < 1.0

    @pytest.mark.asyncio
    async def test_cross_source_detection(self, graph, engine):
        j1 = make_entity(
            "j1", EntityType.JOB, "Reduce customer acquisition cost",
            provenance="llm", provenance_source="session_1",
        )
        j2 = make_entity(
            "j2", EntityType.JOB, "Reduce customer acquisition cost substantially",
            provenance="import", provenance_source="file_upload",
        )
        graph.entities = {"j1": j1, "j2": j2}

        result = await engine.enrich()
        assert result.cross_source_links >= 1

    @pytest.mark.asyncio
    async def test_no_graph_returns_warning(self):
        engine = ContextEnrichmentEngine(graph=None)
        result = await engine.enrich()
        assert "No graph port" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_details_populated(self, graph, engine):
        job = make_entity("j1", EntityType.JOB, "Test job", provenance="llm")
        metric = make_entity("m1", EntityType.METRIC, "Test metric")
        graph.entities = {"j1": job, "m1": metric}

        result = await engine.enrich()
        assert "entity_types" in result.details
        assert result.details["entity_types"].get("job", 0) >= 1

    @pytest.mark.asyncio
    async def test_specific_entity_ids(self, graph, engine):
        j1 = make_entity("j1", EntityType.JOB, "Job one")
        j2 = make_entity("j2", EntityType.JOB, "Job two")
        graph.entities = {"j1": j1, "j2": j2}

        result = await engine.enrich(entity_ids=["j1"])
        assert result.entities_enriched == 1
