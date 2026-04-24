"""Tests for experiment orchestration service.

Uses FakeGraphPort and FakeRelationalPort to test:
- create_experiment creates assumption entity + PG record
- record_result creates evidence entity with SUPPORTS/REFUTES edge
"""
from __future__ import annotations

from typing import Any

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.services.experiment_service import ExperimentService


# ── Fake Ports ─────────────────────────────────────────

class FakeGraphPort:
    def __init__(self) -> None:
        self.entities: dict[str, EntityBase] = {}
        self.edges: list[tuple[str, str, str]] = []

    async def save_entity(self, entity: EntityBase) -> str:
        self.entities[entity.id] = entity
        return entity.id

    async def get_entity(self, eid: str) -> EntityBase | None:
        return self.entities.get(eid)

    async def create_edge(
        self,
        src: str,
        tgt: str,
        etype: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        self.edges.append((src, tgt, etype))
        return True

    async def get_neighbors(
        self, eid: str, edge_type: str = "", direction: str = "outgoing",
    ) -> list[EntityBase]:
        return []


class FakeRelationalPort:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def save_experiment(self, data: dict[str, Any]) -> str:
        self.records.append(data)
        return data.get("id", "exp1")

    async def get_experiments(self, limit: int = 50, **kwargs) -> list[dict[str, Any]]:
        return self.records[:limit]


# ── Fixtures ──────────────────────────────────────────

@pytest.fixture
def graph() -> FakeGraphPort:
    return FakeGraphPort()


@pytest.fixture
def db() -> FakeRelationalPort:
    return FakeRelationalPort()


@pytest.fixture
def service(graph: FakeGraphPort, db: FakeRelationalPort) -> ExperimentService:
    return ExperimentService(graph=graph, db=db)  # type: ignore[arg-type]


# ── Tests ────────────────────────────────────────────

class TestCreateExperiment:
    @pytest.mark.asyncio
    async def test_creates_assumption_entity(
        self, service: ExperimentService, graph: FakeGraphPort, db: FakeRelationalPort,
    ):
        result = await service.create_experiment(
            hypothesis="Users prefer faster checkout",
            job_id="job_001",
            method="survey",
        )

        # Should have created an assumption entity in the graph
        assert len(graph.entities) == 1
        assumption = list(graph.entities.values())[0]
        assert assumption.entity_type == EntityType.ASSUMPTION
        assert "Users prefer faster checkout" in assumption.statement
        assert assumption.provenance == "system"

        # Should have created an ABOUT edge to the job
        assert len(graph.edges) == 1
        src, tgt, etype = graph.edges[0]
        assert tgt == "job_001"
        assert etype == "ABOUT"

        # Should have saved experiment in relational DB
        assert len(db.records) == 1
        assert db.records[0]["hypothesis"] == "Users prefer faster checkout"

        # Return structure
        assert result["assumption_id"] == assumption.id
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_creates_experiment_without_job_id(
        self, service: ExperimentService, graph: FakeGraphPort,
    ):
        result = await service.create_experiment(
            hypothesis="Market demand exists",
            job_id="",
        )

        # No ABOUT edge should be created when job_id is empty
        assert len(graph.edges) == 0
        assert len(graph.entities) == 1


class TestRecordResult:
    @pytest.mark.asyncio
    async def test_creates_evidence_with_supports_edge(
        self, service: ExperimentService, graph: FakeGraphPort, db: FakeRelationalPort,
    ):
        # First create an experiment
        create_result = await service.create_experiment(
            hypothesis="Users prefer faster checkout",
            job_id="job_001",
        )
        experiment_id = db.records[0]["id"]
        graph.edges.clear()  # clear the ABOUT edge for clarity

        # Record a confirming result
        result = await service.record_result(
            experiment_id=experiment_id,
            results={"confidence": 0.8, "effect_size": 0.3},
            decision="confirmed",
        )

        # Evidence entity should be created
        evidence_entities = [
            e for e in graph.entities.values()
            if e.entity_type == EntityType.EVIDENCE
        ]
        assert len(evidence_entities) == 1
        evidence = evidence_entities[0]
        assert evidence.provenance == "system"
        assert evidence.properties.get("supports") is True

        # SUPPORTS edge should be created
        support_edges = [(s, t, e) for s, t, e in graph.edges if e == "SUPPORTS"]
        assert len(support_edges) == 1

        assert result["decision"] == "confirmed"

    @pytest.mark.asyncio
    async def test_creates_evidence_with_refutes_edge(
        self, service: ExperimentService, graph: FakeGraphPort, db: FakeRelationalPort,
    ):
        create_result = await service.create_experiment(
            hypothesis="Users want more features",
            job_id="job_002",
        )
        experiment_id = db.records[0]["id"]
        graph.edges.clear()

        result = await service.record_result(
            experiment_id=experiment_id,
            results={"confidence": 0.6, "effect_size": -0.1},
            decision="refuted",
        )

        # REFUTES edge should be created
        refute_edges = [(s, t, e) for s, t, e in graph.edges if e == "REFUTES"]
        assert len(refute_edges) == 1

        evidence_entities = [
            e for e in graph.entities.values()
            if e.entity_type == EntityType.EVIDENCE
        ]
        assert len(evidence_entities) == 1
        assert evidence_entities[0].properties.get("supports") is False
