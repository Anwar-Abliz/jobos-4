"""Tests for database sync — PostgreSQL ↔ Neo4j write-through (MetricService).

Covers:
- MetricService.record_reading(): PostgreSQL write + Neo4j current_value update
- MetricService.record_vfe(): PostgreSQL write + Neo4j vfe_current update
- MetricService.get_history(): delegates to RelationalPort
- MetricService.get_latest(): delegates to RelationalPort
- MetricService.get_vfe_history(): delegates to RelationalPort
- Soft-sync behavior: missing graph entity does NOT raise

Architecture under test (CTO Decision 3):
  PostgreSQL = source of truth (all reads use it)
  Neo4j      = materialized summary cache (write-through on every write)
  Sync is application-level, no distributed transaction.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Any

from jobos.kernel.entity import (
    EntityBase,
    EntityType,
    MetricReading,
    VFEReading,
)
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.metric_service import MetricService


# ─── Fake ports ──────────────────────────────────────────

class FakeRelationalPort(RelationalPort):
    """In-memory relational store."""

    def __init__(self) -> None:
        self._metric_readings: list[MetricReading] = []
        self._vfe_readings: list[VFEReading] = []
        self._job_metrics: list[dict] = []

    # ── RelationalPort API ──────────────────────────────

    async def save_metric_reading(self, reading: MetricReading) -> str:
        self._metric_readings.append(reading)
        return reading.id

    async def get_metric_readings(
        self,
        metric_id: str,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[MetricReading]:
        rows = [r for r in self._metric_readings if r.metric_id == metric_id]
        rows.sort(key=lambda r: r.observed_at, reverse=True)
        return rows[:limit]

    async def get_latest_reading(self, metric_id: str) -> MetricReading | None:
        rows = await self.get_metric_readings(metric_id, limit=1)
        return rows[0] if rows else None

    async def save_vfe_reading(self, reading: VFEReading) -> str:
        self._vfe_readings.append(reading)
        return reading.id

    async def get_vfe_history(self, job_id: str, limit: int = 50) -> list[VFEReading]:
        rows = [r for r in self._vfe_readings if r.job_id == job_id]
        rows.sort(key=lambda r: r.measured_at, reverse=True)
        return rows[:limit]

    async def save_hiring_event(self, event: Any) -> str:
        return event.id

    async def get_hiring_events(self, **kwargs: Any) -> list:
        return []

    async def save_experiment(self, experiment: Any) -> str:
        return experiment.id

    async def get_experiments(self, **kwargs: Any) -> list:
        return []

    async def insert_job_metric(
        self,
        job_id: str,
        metrics: dict[str, float],
        bounds: dict[str, list[float | None]],
        *,
        context_hash: str | None = None,
        context_vector_ref: str | None = None,
    ) -> str:
        row = {
            "job_id": job_id,
            "metrics": metrics,
            "bounds": bounds,
            "context_hash": context_hash,
            "context_vector_ref": context_vector_ref,
        }
        self._job_metrics.append(row)
        return "row_id"

    async def get_job_metrics(self, job_id: str, limit: int = 50) -> list[dict]:
        return [r for r in self._job_metrics if r["job_id"] == job_id][:limit]

    async def verify_connectivity(self) -> bool:
        return True

    async def save_experience_version(self, job_id, version, markers, source, confidence=None, created_by=None):
        return "ev_fake"

    async def get_experience_history(self, job_id, limit=50):
        return []

    async def save_baseline_snapshot(self, scenario_id, job_id, metrics, bounds, captured_by=None):
        return "bs_fake"

    async def get_baseline_snapshot(self, scenario_id, job_id):
        return None

    async def save_switch_event(self, scenario_id, job_id, trigger_metric, trigger_value, trigger_bound, action, reason=""):
        return "se_fake"

    async def get_switch_events(self, scenario_id, limit=50):
        return []


class FakeGraphPort(GraphPort):
    """In-memory graph store."""

    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._saved: list[EntityBase] = []  # spy: track save calls

    def seed(self, entity: EntityBase) -> None:
        self._entities[entity.id] = entity

    # ── GraphPort API ───────────────────────────────────

    async def save_entity(self, entity: EntityBase) -> str:
        self._entities[entity.id] = entity
        self._saved.append(entity)
        return entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self._entities.get(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        return self._entities.pop(entity_id, None) is not None

    async def list_entities(self, **kwargs: Any) -> list[EntityBase]:
        return list(self._entities.values())

    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        return True

    async def delete_edge(self, source_id: str, target_id: str, edge_type: str) -> bool:
        return True

    async def get_edges(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        return []

    async def get_job_subgraph(self, job_id: str, depth: int = 3) -> dict[str, Any]:
        return {}

    async def get_neighbors(self, entity_id: str, **kwargs: Any) -> list[EntityBase]:
        return []

    async def add_label(self, entity_id: str, label: str) -> bool:
        return True

    async def ensure_schema(self) -> None:
        pass

    async def verify_connectivity(self) -> bool:
        return True


# ─── Helpers ─────────────────────────────────────────────

def make_metric_entity(metric_id: str = "m1", entity_id: str = "job1") -> EntityBase:
    return EntityBase(
        id=metric_id,
        statement="Metric: revenue",
        entity_type=EntityType.METRIC,
        properties={"current_value": 0.0, "entity_id": entity_id},
    )


def make_job_entity(job_id: str = "job1") -> EntityBase:
    return EntityBase(
        id=job_id,
        statement="Define scope",
        entity_type=EntityType.JOB,
        properties={"vfe_current": None},
    )


def make_reading(
    metric_id: str = "m1",
    entity_id: str = "job1",
    value: float = 0.75,
) -> MetricReading:
    return MetricReading(metric_id=metric_id, entity_id=entity_id, value=value)


def make_vfe_reading(
    job_id: str = "job1",
    vfe_value: float = 0.4,
    efe_value: float | None = None,
) -> VFEReading:
    return VFEReading(job_id=job_id, vfe_value=vfe_value, efe_value=efe_value)


# ─── record_reading: PostgreSQL write ────────────────────

class TestRecordReadingPostgresWrite:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_reading_persisted_to_postgres(self):
        reading = make_reading(value=0.8)
        await self.svc.record_reading(reading)
        assert len(self.db._metric_readings) == 1
        assert self.db._metric_readings[0].value == 0.8

    @pytest.mark.asyncio
    async def test_returns_same_reading_object(self):
        reading = make_reading(value=0.5)
        returned = await self.svc.record_reading(reading)
        assert returned is reading

    @pytest.mark.asyncio
    async def test_multiple_readings_all_persisted(self):
        for v in [0.1, 0.5, 0.9]:
            await self.svc.record_reading(make_reading(value=v))
        assert len(self.db._metric_readings) == 3


# ─── record_reading: Neo4j write-through ─────────────────

class TestRecordReadingNeo4jSync:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_current_value_updated_in_graph(self):
        metric_entity = make_metric_entity("m1")
        self.graph.seed(metric_entity)

        await self.svc.record_reading(make_reading(metric_id="m1", value=0.72))

        updated = await self.graph.get_entity("m1")
        assert updated is not None
        assert updated.properties["current_value"] == 0.72

    @pytest.mark.asyncio
    async def test_graph_save_called_when_entity_exists(self):
        self.graph.seed(make_metric_entity("m1"))
        await self.svc.record_reading(make_reading(metric_id="m1", value=0.5))
        # save_entity should have been called (entity was updated)
        assert any(e.id == "m1" for e in self.graph._saved)

    @pytest.mark.asyncio
    async def test_multiple_readings_update_to_latest_value(self):
        self.graph.seed(make_metric_entity("m1"))
        await self.svc.record_reading(make_reading(metric_id="m1", value=0.3))
        await self.svc.record_reading(make_reading(metric_id="m1", value=0.9))

        updated = await self.graph.get_entity("m1")
        assert updated is not None
        assert updated.properties["current_value"] == 0.9

    @pytest.mark.asyncio
    async def test_updated_at_refreshed_on_sync(self):
        entity = make_metric_entity("m1")
        original_ts = entity.updated_at
        self.graph.seed(entity)

        await self.svc.record_reading(make_reading(metric_id="m1", value=0.5))

        updated = await self.graph.get_entity("m1")
        assert updated is not None
        assert updated.updated_at >= original_ts


# ─── record_reading: soft-sync (missing graph entity) ────

class TestRecordReadingSoftSync:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()  # empty graph — no entities seeded
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_missing_graph_entity_does_not_raise(self):
        """PostgreSQL write succeeds even if Neo4j entity is absent."""
        reading = make_reading(metric_id="missing_metric")
        # Should not raise:
        result = await self.svc.record_reading(reading)
        assert result is reading

    @pytest.mark.asyncio
    async def test_postgres_still_written_when_graph_entity_missing(self):
        reading = make_reading(metric_id="missing_metric", value=0.6)
        await self.svc.record_reading(reading)
        assert len(self.db._metric_readings) == 1
        assert self.db._metric_readings[0].value == 0.6

    @pytest.mark.asyncio
    async def test_no_graph_save_when_entity_missing(self):
        await self.svc.record_reading(make_reading(metric_id="no_such_id"))
        # Nothing was saved to graph
        assert len(self.graph._saved) == 0


# ─── record_vfe: PostgreSQL write ────────────────────────

class TestRecordVFEPostgresWrite:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_vfe_reading_persisted_to_postgres(self):
        reading = make_vfe_reading(vfe_value=0.65)
        await self.svc.record_vfe(reading)
        assert len(self.db._vfe_readings) == 1
        assert self.db._vfe_readings[0].vfe_value == 0.65

    @pytest.mark.asyncio
    async def test_returns_same_vfe_reading(self):
        reading = make_vfe_reading()
        returned = await self.svc.record_vfe(reading)
        assert returned is reading

    @pytest.mark.asyncio
    async def test_efe_value_stored_in_postgres(self):
        reading = make_vfe_reading(vfe_value=0.4, efe_value=0.24)
        await self.svc.record_vfe(reading)
        stored = self.db._vfe_readings[0]
        assert stored.efe_value == 0.24


# ─── record_vfe: Neo4j write-through ─────────────────────

class TestRecordVFENeo4jSync:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_vfe_current_updated_in_graph(self):
        job = make_job_entity("job1")
        self.graph.seed(job)

        await self.svc.record_vfe(make_vfe_reading(job_id="job1", vfe_value=0.55))

        updated = await self.graph.get_entity("job1")
        assert updated is not None
        assert updated.properties["vfe_current"] == 0.55

    @pytest.mark.asyncio
    async def test_successive_vfe_updates_to_latest(self):
        self.graph.seed(make_job_entity("job1"))
        await self.svc.record_vfe(make_vfe_reading(job_id="job1", vfe_value=0.9))
        await self.svc.record_vfe(make_vfe_reading(job_id="job1", vfe_value=0.2))

        updated = await self.graph.get_entity("job1")
        assert updated is not None
        assert updated.properties["vfe_current"] == 0.2

    @pytest.mark.asyncio
    async def test_vfe_missing_job_does_not_raise(self):
        """Soft sync: missing job in graph is silently skipped."""
        reading = make_vfe_reading(job_id="nonexistent_job")
        result = await self.svc.record_vfe(reading)
        assert result is reading

    @pytest.mark.asyncio
    async def test_postgres_written_even_when_job_missing_in_graph(self):
        await self.svc.record_vfe(make_vfe_reading(job_id="ghost_job", vfe_value=0.7))
        assert len(self.db._vfe_readings) == 1
        assert self.db._vfe_readings[0].vfe_value == 0.7


# ─── get_history: delegates to RelationalPort ────────────

class TestGetHistory:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_returns_readings_for_metric(self):
        r1 = make_reading(metric_id="m1", value=0.3)
        r2 = make_reading(metric_id="m1", value=0.7)
        r3 = make_reading(metric_id="m2", value=0.5)  # different metric
        self.db._metric_readings.extend([r1, r2, r3])

        history = await self.svc.get_history("m1")
        assert len(history) == 2
        ids = {r.id for r in history}
        assert r1.id in ids
        assert r2.id in ids

    @pytest.mark.asyncio
    async def test_empty_history_for_unknown_metric(self):
        history = await self.svc.get_history("no_such_metric")
        assert history == []

    @pytest.mark.asyncio
    async def test_limit_respected(self):
        for i in range(10):
            self.db._metric_readings.append(make_reading(metric_id="m1", value=float(i)))
        history = await self.svc.get_history("m1", limit=3)
        assert len(history) == 3


# ─── get_latest: delegates to RelationalPort ─────────────

class TestGetLatest:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_readings(self):
        result = await self.svc.get_latest("m1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_reading_when_one_exists(self):
        r = make_reading(metric_id="m1", value=0.5)
        self.db._metric_readings.append(r)
        result = await self.svc.get_latest("m1")
        assert result is not None
        assert result.value == 0.5


# ─── get_vfe_history: delegates to RelationalPort ────────

class TestGetVFEHistory:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_returns_vfe_readings_for_job(self):
        r1 = make_vfe_reading(job_id="j1", vfe_value=0.8)
        r2 = make_vfe_reading(job_id="j1", vfe_value=0.5)
        r3 = make_vfe_reading(job_id="j2", vfe_value=0.3)  # different job
        self.db._vfe_readings.extend([r1, r2, r3])

        history = await self.svc.get_vfe_history("j1")
        assert len(history) == 2
        job_ids = {r.job_id for r in history}
        assert job_ids == {"j1"}

    @pytest.mark.asyncio
    async def test_empty_when_no_vfe_for_job(self):
        history = await self.svc.get_vfe_history("unknown_job")
        assert history == []

    @pytest.mark.asyncio
    async def test_vfe_limit_respected(self):
        for i in range(20):
            self.db._vfe_readings.append(make_vfe_reading(job_id="j1", vfe_value=float(i) / 20))
        history = await self.svc.get_vfe_history("j1", limit=5)
        assert len(history) == 5


# ─── Round-trip: write → read consistency ────────────────

class TestRoundTrip:
    def setup_method(self) -> None:
        self.db = FakeRelationalPort()
        self.graph = FakeGraphPort()
        self.svc = MetricService(self.graph, self.db)

    @pytest.mark.asyncio
    async def test_metric_round_trip_postgres_value_preserved(self):
        reading = make_reading(metric_id="m1", value=0.333)
        await self.svc.record_reading(reading)
        latest = await self.svc.get_latest("m1")
        assert latest is not None
        assert abs(latest.value - 0.333) < 1e-9

    @pytest.mark.asyncio
    async def test_vfe_round_trip_value_preserved(self):
        reading = make_vfe_reading(job_id="j1", vfe_value=0.618)
        await self.svc.record_vfe(reading)
        history = await self.svc.get_vfe_history("j1")
        assert len(history) == 1
        assert abs(history[0].vfe_value - 0.618) < 1e-9

    @pytest.mark.asyncio
    async def test_postgres_and_neo4j_agree_on_current_value(self):
        """After a record_reading, both stores have the same value."""
        self.graph.seed(make_metric_entity("m1"))
        await self.svc.record_reading(make_reading(metric_id="m1", value=0.42))

        # PostgreSQL
        latest = await self.svc.get_latest("m1")
        assert latest is not None
        pg_value = latest.value

        # Neo4j
        entity = await self.graph.get_entity("m1")
        assert entity is not None
        neo4j_value = entity.properties["current_value"]

        assert abs(pg_value - neo4j_value) < 1e-9

    @pytest.mark.asyncio
    async def test_postgres_and_neo4j_agree_on_vfe(self):
        """After a record_vfe, both stores reflect the same VFE value."""
        self.graph.seed(make_job_entity("j1"))
        await self.svc.record_vfe(make_vfe_reading(job_id="j1", vfe_value=0.77))

        # PostgreSQL
        history = await self.svc.get_vfe_history("j1")
        pg_vfe = history[0].vfe_value

        # Neo4j
        job = await self.graph.get_entity("j1")
        assert job is not None
        neo4j_vfe = job.properties["vfe_current"]

        assert abs(pg_vfe - neo4j_vfe) < 1e-9
