"""Tests for ImperfectionService.

Covers:
- derive_imperfections: metric-based imperfection derivation
- Axiom 2 enforcement: entropy residual auto-creation
- rank: IPS-based ranking
- get_top_blocker: priority blocker selection
"""
from __future__ import annotations

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.services.imperfection_service import ImperfectionService


# ─── Fake Graph Port ────────────────────────────────────

class FakeGraphPort:
    def __init__(self) -> None:
        self.entities: dict[str, EntityBase] = {}
        self.edges: list[tuple[str, str, str]] = []
        self._neighbors: dict[str, list[EntityBase]] = {}

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self.entities.get(entity_id)

    async def save_entity(self, entity: EntityBase) -> str:
        self.entities[entity.id] = entity
        return entity.id

    async def get_neighbors(
        self, entity_id: str, edge_type: str = "", direction: str = "outgoing"
    ) -> list[EntityBase]:
        key = f"{entity_id}:{edge_type}:{direction}"
        return self._neighbors.get(key, [])

    async def create_edge(self, source_id: str, target_id: str, edge_type: str) -> str:
        self.edges.append((source_id, target_id, edge_type))
        return f"{source_id}-{edge_type}-{target_id}"

    def stub_neighbors(
        self, entity_id: str, edge_type: str, direction: str, entities: list[EntityBase]
    ) -> None:
        key = f"{entity_id}:{edge_type}:{direction}"
        self._neighbors[key] = entities


# ─── Helpers ────────────────────────────────────────────

def make_job(job_id: str = "j1", statement: str = "Reduce churn") -> EntityBase:
    return EntityBase(
        id=job_id, name=job_id, statement=statement,
        entity_type=EntityType.JOB, properties={"level": 0},
    )


def make_metric(
    metric_id: str = "m1",
    name: str = "churn_rate",
    target: float = 0.03,
    current: float | None = None,
    direction: str = "minimize",
) -> EntityBase:
    return EntityBase(
        id=metric_id, name=name, statement=f"Metric {name}",
        entity_type=EntityType.METRIC,
        properties={
            "target_value": target,
            "current_value": current,
            "direction": direction,
        },
    )


def make_imperfection(
    imp_id: str = "i1",
    severity: float = 0.5,
    is_blocker: bool = False,
    frequency: float = 0.3,
) -> EntityBase:
    return EntityBase(
        id=imp_id, name=imp_id, statement="Some imperfection",
        entity_type=EntityType.IMPERFECTION,
        properties={
            "severity": severity,
            "is_blocker": is_blocker,
            "frequency": frequency,
            "entropy_risk": 0.1,
            "fixability": 0.8,
        },
    )


# ─── Tests ──────────────────────────────────────────────

class TestDeriveImperfections:
    @pytest.fixture
    def graph(self) -> FakeGraphPort:
        return FakeGraphPort()

    @pytest.fixture
    def svc(self, graph: FakeGraphPort) -> ImperfectionService:
        return ImperfectionService(graph=graph)

    @pytest.mark.asyncio
    async def test_no_metrics_creates_entropy_residual(self, graph, svc):
        job = make_job()
        graph.entities[job.id] = job
        graph.stub_neighbors(job.id, "MEASURED_BY", "outgoing", [])

        result = await svc.derive_imperfections(job.id)
        assert len(result) >= 1
        residual = result[0]
        assert residual.properties.get("severity") == 0.05
        assert residual.properties.get("entropy_risk") == 0.3

    @pytest.mark.asyncio
    async def test_unmet_metric_creates_imperfection(self, graph, svc):
        job = make_job()
        metric = make_metric(target=0.03, current=0.08, direction="minimize")
        graph.entities[job.id] = job
        graph.stub_neighbors(job.id, "MEASURED_BY", "outgoing", [metric])

        result = await svc.derive_imperfections(job.id)
        assert len(result) >= 1
        imp = result[0]
        assert imp.entity_type == EntityType.IMPERFECTION
        assert imp.properties.get("severity", 0) > 0

    @pytest.mark.asyncio
    async def test_met_metric_still_has_entropy_residual(self, graph, svc):
        job = make_job()
        metric = make_metric(target=0.03, current=0.02, direction="minimize")
        graph.entities[job.id] = job
        graph.stub_neighbors(job.id, "MEASURED_BY", "outgoing", [metric])

        result = await svc.derive_imperfections(job.id)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_no_target_metric_skipped(self, graph, svc):
        job = make_job()
        metric = make_metric(target=None, current=0.05)
        graph.entities[job.id] = job
        graph.stub_neighbors(job.id, "MEASURED_BY", "outgoing", [metric])

        result = await svc.derive_imperfections(job.id)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_edges_created_for_derived_imperfections(self, graph, svc):
        job = make_job()
        metric = make_metric(target=0.03, current=0.10, direction="minimize")
        graph.entities[job.id] = job
        graph.stub_neighbors(job.id, "MEASURED_BY", "outgoing", [metric])

        await svc.derive_imperfections(job.id)
        occurs_in_edges = [e for e in graph.edges if e[2] == "OCCURS_IN"]
        assert len(occurs_in_edges) >= 1


class TestRank:
    @pytest.fixture
    def graph(self) -> FakeGraphPort:
        return FakeGraphPort()

    @pytest.fixture
    def svc(self, graph: FakeGraphPort) -> ImperfectionService:
        return ImperfectionService(graph=graph)

    @pytest.mark.asyncio
    async def test_rank_returns_sorted_by_severity(self, graph, svc):
        low = make_imperfection("i1", severity=0.2)
        high = make_imperfection("i2", severity=0.9)
        mid = make_imperfection("i3", severity=0.5)
        graph.stub_neighbors("j1", "OCCURS_IN", "incoming", [low, high, mid])

        ranked = await svc.rank("j1")
        assert len(ranked) == 3
        severities = [r.properties.get("severity", 0) for r in ranked]
        assert severities == sorted(severities, reverse=True)

    @pytest.mark.asyncio
    async def test_rank_empty(self, graph, svc):
        graph.stub_neighbors("j1", "OCCURS_IN", "incoming", [])
        ranked = await svc.rank("j1")
        assert ranked == []


class TestGetTopBlocker:
    @pytest.fixture
    def graph(self) -> FakeGraphPort:
        return FakeGraphPort()

    @pytest.fixture
    def svc(self, graph: FakeGraphPort) -> ImperfectionService:
        return ImperfectionService(graph=graph)

    @pytest.mark.asyncio
    async def test_returns_blocker_over_higher_severity(self, graph, svc):
        high_sev = make_imperfection("i1", severity=0.9, is_blocker=False)
        blocker = make_imperfection("i2", severity=0.3, is_blocker=True)
        graph.stub_neighbors("j1", "OCCURS_IN", "incoming", [high_sev, blocker])

        top = await svc.get_top_blocker("j1")
        assert top is not None
        assert top.properties.get("is_blocker") is True

    @pytest.mark.asyncio
    async def test_returns_first_if_no_blockers(self, graph, svc):
        imp1 = make_imperfection("i1", severity=0.8)
        imp2 = make_imperfection("i2", severity=0.3)
        graph.stub_neighbors("j1", "OCCURS_IN", "incoming", [imp1, imp2])

        top = await svc.get_top_blocker("j1")
        assert top is not None

    @pytest.mark.asyncio
    async def test_returns_none_if_no_imperfections(self, graph, svc):
        graph.stub_neighbors("j1", "OCCURS_IN", "incoming", [])
        top = await svc.get_top_blocker("j1")
        assert top is None
