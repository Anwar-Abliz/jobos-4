"""Integration tests for entity_service + hiring_service workflows.

These tests exercise multiple components together using FakeGraphPort and
FakeRelationalPort — no live Neo4j or PostgreSQL required.

Covers API-level scenarios:
  - Create entity → validate → persist → retrieve round-trip
  - Axiom 6: two ROOT jobs in same scope → second raises AxiomViolation(6)
  - Full hiring lifecycle: propose → execute → evaluate → switch
  - Duality: job completion → :Capability label + DUAL_AS edge
"""
from __future__ import annotations

from typing import Any

import pytest

from jobos.kernel.entity import (
    EntityBase, EntityType, HiringEvent, HiringEventType,
    MetricReading, VFEReading, ExperimentRecord,
)
from jobos.kernel.axioms import AxiomViolation
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.entity_service import EntityService
from jobos.services.hiring_service import HiringService


# ─── Shared Fake Ports ───────────────────────────────────

class FakeGraphPort(GraphPort):
    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []
        self._labels: list[tuple] = []

    async def save_entity(self, entity: EntityBase) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self._entities.get(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        return self._entities.pop(entity_id, None) is not None

    async def list_entities(self, entity_type=None, status=None, limit=100, offset=0):
        result = list(self._entities.values())
        if entity_type:
            result = [e for e in result if e.entity_type.value == entity_type]
        if status:
            result = [e for e in result if e.status == status]
        return result[offset: offset + limit]

    async def create_edge(self, source_id, target_id, edge_type, properties=None) -> bool:
        self._edges.append({
            "source_id": source_id, "target_id": target_id,
            "edge_type": edge_type, "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id, target_id, edge_type) -> bool:
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (e["source_id"] == source_id and e["target_id"] == target_id
                    and e["edge_type"] == edge_type)
        ]
        return len(self._edges) < before

    async def get_neighbors(self, entity_id, edge_type=None, direction="outgoing"):
        return []

    async def get_edges(self, entity_id, edge_type=None, direction="outgoing"):
        return []

    async def get_job_subgraph(self, job_id, depth=3):
        return {}

    async def add_label(self, entity_id, label) -> bool:
        self._labels.append((entity_id, label))
        return True

    async def ensure_schema(self) -> int:
        return 0

    async def find_path(self, source_id, target_id, max_depth=5):
        return []

    async def get_subgraph_by_label(self, label, limit=100):
        return []

    async def verify_connectivity(self) -> bool:
        return True


class FakeRelationalPort(RelationalPort):
    def __init__(self) -> None:
        self._hiring_events: list[HiringEvent] = []
        self._vfe: list[VFEReading] = []

    async def save_metric_reading(self, reading): return reading.id
    async def get_metric_readings(self, metric_id, limit=100, since=None): return []
    async def get_latest_reading(self, metric_id): return None
    async def save_vfe_reading(self, reading): self._vfe.append(reading); return reading.id
    async def get_vfe_history(self, job_id, limit=50): return self._vfe[:limit]
    async def save_hiring_event(self, event):
        self._hiring_events.append(event); return event.id
    async def get_hiring_events(self, entity_id=None, event_type=None, limit=100):
        return self._hiring_events[:limit]
    async def save_experiment(self, experiment): return experiment.id
    async def get_experiments(self, assumption_id=None, limit=50): return []
    async def insert_job_metric(self, job_id, metrics, bounds, **kwargs): return "mid"
    async def get_job_metrics(self, job_id, limit=50): return []
    async def verify_connectivity(self): return True
    async def save_experience_version(self, job_id, version, markers, source, confidence=None, created_by=None): return "ev_fake"
    async def get_experience_history(self, job_id, limit=50): return []
    async def save_baseline_snapshot(self, scenario_id, job_id, metrics, bounds, captured_by=None): return "bs_fake"
    async def get_baseline_snapshot(self, scenario_id, job_id): return None
    async def save_switch_event(self, scenario_id, job_id, trigger_metric, trigger_value, trigger_bound, action, reason=""): return "se_fake"
    async def get_switch_events(self, scenario_id, limit=50): return []
    async def save_decision_trace(self, actor, action, target_entity_id, rationale="",
                                   context_snapshot=None, policies_evaluated=None,
                                   alternatives=None, vfe_before=None, vfe_after=None,
                                   lineage=None): return "trace-id"
    async def get_decision_traces(self, target_entity_id=None, actor=None, limit=50): return []
    async def save_survey_response(self, survey_id, outcome_id, session_id,
                                    importance, satisfaction, opportunity_score): return "resp-id"
    async def get_survey_responses(self, survey_id, outcome_id=None, limit=500): return []
    async def get_survey_aggregates(self, survey_id): return []
    async def save_context_snapshot(self, entity_id, snapshot_data, source="system"): return "snap-id"
    async def get_context_snapshots(self, entity_id, limit=10): return []


@pytest.fixture
def graph():
    return FakeGraphPort()


@pytest.fixture
def db():
    return FakeRelationalPort()


@pytest.fixture
def entity_svc(graph):
    return EntityService(graph)


@pytest.fixture
def hiring_svc(graph, db):
    return HiringService(graph=graph, db=db)


# ─── Entity round-trip ───────────────────────────────────

class TestEntityRoundTrip:
    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, entity_svc, graph):
        entity = EntityBase(
            id="j_rt1",
            statement="Define the roadmap",
            entity_type=EntityType.JOB,
            properties={"scope_id": "s1"},
        )
        await entity_svc.create(entity)
        retrieved = await entity_svc.get("j_rt1")
        assert retrieved is not None
        assert retrieved.id == "j_rt1"

    @pytest.mark.asyncio
    async def test_update_and_retrieve(self, entity_svc, graph):
        entity = EntityBase(
            id="j_rt2",
            statement="Build the feature",
            entity_type=EntityType.JOB,
            properties={"scope_id": "s1"},
        )
        await entity_svc.create(entity)
        await entity_svc.update("j_rt2", {"status": "in_progress"})
        retrieved = await entity_svc.get("j_rt2")
        assert retrieved.status == "in_progress"

    @pytest.mark.asyncio
    async def test_delete_removes_entity(self, entity_svc, graph):
        entity = EntityBase(
            id="j_del1",
            statement="Deploy the service",
            entity_type=EntityType.JOB,
            properties={"scope_id": "s1"},
        )
        await entity_svc.create(entity)
        await entity_svc.delete("j_del1")
        assert await entity_svc.get("j_del1") is None


# ─── Axiom 6: two ROOT jobs same scope ───────────────────

class TestAxiom6Integration:
    @pytest.mark.asyncio
    async def test_two_root_jobs_same_scope_raises(self, entity_svc):
        root1 = EntityBase(
            id="r1",
            statement="Define strategy",
            entity_type=EntityType.JOB,
            properties={"root_token": "ROOT", "scope_id": "proj_x", "scope_id": "proj_x"},
        )
        root2 = EntityBase(
            id="r2",
            statement="Build product",
            entity_type=EntityType.JOB,
            properties={"root_token": "ROOT", "scope_id": "proj_x"},
        )
        await entity_svc.create(root1)
        with pytest.raises(AxiomViolation) as exc_info:
            await entity_svc.create(root2)
        assert exc_info.value.axiom == 6

    @pytest.mark.asyncio
    async def test_root_jobs_different_scopes_pass(self, entity_svc):
        root1 = EntityBase(
            id="r1",
            statement="Define strategy",
            entity_type=EntityType.JOB,
            properties={"root_token": "ROOT", "scope_id": "proj_a"},
        )
        root2 = EntityBase(
            id="r2",
            statement="Build product",
            entity_type=EntityType.JOB,
            properties={"root_token": "ROOT", "scope_id": "proj_b"},
        )
        await entity_svc.create(root1)
        result = await entity_svc.create(root2)
        assert result.id == "r2"


# ─── Duality integration ─────────────────────────────────

class TestDualityIntegration:
    @pytest.mark.asyncio
    async def test_job_completion_triggers_duality(self, entity_svc, graph):
        entity = EntityBase(
            id="j_dual",
            statement="Deliver the feature",
            entity_type=EntityType.JOB,
            status="active",
            properties={"scope_id": "s1"},
        )
        await entity_svc.create(entity)
        await entity_svc.update("j_dual", {"status": "completed"})

        # :Capability label applied
        assert ("j_dual", "Capability") in graph._labels

        # DUAL_AS self-edge created
        dual_edges = [
            e for e in graph._edges
            if e["edge_type"] == "DUAL_AS"
            and e["source_id"] == "j_dual"
            and e["target_id"] == "j_dual"
        ]
        assert len(dual_edges) == 1

    @pytest.mark.asyncio
    async def test_duality_not_triggered_twice(self, entity_svc, graph):
        entity = EntityBase(
            id="j_dual2",
            statement="Ship the release",
            entity_type=EntityType.JOB,
            status="active",
            properties={"scope_id": "s1"},
        )
        await entity_svc.create(entity)
        await entity_svc.update("j_dual2", {"status": "completed"})
        # Update again — already completed, should not fire again
        await entity_svc.update("j_dual2", {"properties": {"tier": 2}})
        dual_edges = [e for e in graph._edges if e["edge_type"] == "DUAL_AS"]
        assert len(dual_edges) == 1


# ─── Full hiring lifecycle ────────────────────────────────

class TestHiringLifecycle:
    @pytest.mark.asyncio
    async def test_propose_execute_evaluate_lifecycle(self, hiring_svc, graph, db):
        candidates = [{"id": "exec_1", "estimated_impact": 0.7, "properties": {}}]

        # propose
        proposal = await hiring_svc.propose_hire(
            job_id="j1", candidates=candidates, context_id="ctx_1"
        )
        assert proposal.status in ("proposed", "needs_review")

        # execute
        event = await hiring_svc.execute_hire(
            hirer_id="j1", hiree_id="exec_1", job_id="j1"
        )
        assert event.event_type == HiringEventType.HIRE
        assert len(db._hiring_events) == 1

        # evaluate
        evaluation = await hiring_svc.evaluate_hire(
            hirer_id="j1", hiree_id="exec_1", job_id="j1"
        )
        assert evaluation.combined_verdict in ("keep", "warn", "switch")

    @pytest.mark.asyncio
    async def test_execute_switch_full_audit(self, hiring_svc, graph, db):
        # Setup initial hire edge
        graph._edges.append({
            "source_id": "h1", "target_id": "exec_old",
            "edge_type": "HIRES", "properties": {}
        })

        event = await hiring_svc.execute_switch(
            hirer_id="h1",
            current_hiree_id="exec_old",
            new_hiree_id="exec_new",
            job_id="j1",
            reason="metric breach",
        )

        assert event.event_type == HiringEventType.SWITCH
        assert len(db._hiring_events) == 1

        fires = [e for e in graph._edges if e["edge_type"] == "FIRES"]
        assert any(e["target_id"] == "exec_old" for e in fires)

        hires_new = [
            e for e in graph._edges
            if e["edge_type"] == "HIRES" and e["target_id"] == "exec_new"
        ]
        assert len(hires_new) == 1

    @pytest.mark.asyncio
    async def test_switch_evaluator_integrated_in_evaluate(self, hiring_svc):
        state: dict = {}
        evaluation = await hiring_svc.evaluate_hire(
            hirer_id="h1", hiree_id="e1", job_id="j1", switch_state=state
        )
        assert "switch_evaluator" in evaluation.cdee_evaluation
        sw = evaluation.cdee_evaluation["switch_evaluator"]
        assert sw["action"] in ("HIRE", "FIRE", "NONE")
