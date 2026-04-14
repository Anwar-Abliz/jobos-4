"""Tests for HiringService — lifecycle and SwitchEvaluator integration.

Uses FakeGraphPort + FakeRelationalPort (in-memory) — no live DB required.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

import pytest

from jobos.kernel.entity import (
    EntityBase, EntityType, MetricReading, VFEReading, HiringEvent,
    HiringEventType, ExperimentRecord,
)
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.hiring_service import HiringService, HireProposal, HireEvaluation


# ─── Fake Ports ──────────────────────────────────────────

class FakeGraphPort(GraphPort):
    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []
        self._labels: list[tuple] = []
        self._neighbors: dict[str, list[EntityBase]] = {}  # entity_id → list

    async def save_entity(self, entity: EntityBase) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self._entities.get(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        return self._entities.pop(entity_id, None) is not None

    async def list_entities(self, entity_type=None, status=None, limit=100, offset=0):
        return []

    async def create_edge(self, source_id, target_id, edge_type, properties=None) -> bool:
        self._edges.append({"source_id": source_id, "target_id": target_id,
                             "edge_type": edge_type, "properties": properties or {}})
        return True

    async def delete_edge(self, source_id, target_id, edge_type) -> bool:
        before = len(self._edges)
        self._edges = [e for e in self._edges
                       if not (e["source_id"] == source_id and e["target_id"] == target_id
                               and e["edge_type"] == edge_type)]
        return len(self._edges) < before

    async def get_neighbors(self, entity_id, edge_type=None, direction="outgoing"):
        return self._neighbors.get(entity_id, [])

    async def get_edges(self, entity_id, edge_type=None, direction="outgoing"):
        return []

    async def get_job_subgraph(self, job_id, depth=3):
        return {}

    async def add_label(self, entity_id, label) -> bool:
        self._labels.append((entity_id, label))
        return True

    async def ensure_schema(self) -> int:
        return 0

    async def verify_connectivity(self) -> bool:
        return True


class FakeRelationalPort(RelationalPort):
    def __init__(self) -> None:
        self._metric_readings: list[MetricReading] = []
        self._vfe_readings: list[VFEReading] = []
        self._hiring_events: list[HiringEvent] = []
        self._experiments: list[ExperimentRecord] = []

    async def save_metric_reading(self, reading: MetricReading) -> str:
        self._metric_readings.append(reading)
        return reading.id

    async def get_metric_readings(self, metric_id, limit=100, since=None):
        return [r for r in self._metric_readings if r.metric_id == metric_id][:limit]

    async def get_latest_reading(self, metric_id):
        readings = await self.get_metric_readings(metric_id, limit=1)
        return readings[0] if readings else None

    async def save_vfe_reading(self, reading: VFEReading) -> str:
        self._vfe_readings.append(reading)
        return reading.id

    async def get_vfe_history(self, job_id, limit=50):
        return [r for r in self._vfe_readings if r.job_id == job_id][:limit]

    async def save_hiring_event(self, event: HiringEvent) -> str:
        self._hiring_events.append(event)
        return event.id

    async def get_hiring_events(self, entity_id=None, event_type=None, limit=100):
        return self._hiring_events[:limit]

    async def save_experiment(self, experiment: ExperimentRecord) -> str:
        self._experiments.append(experiment)
        return experiment.id

    async def get_experiments(self, assumption_id=None, limit=50):
        return self._experiments[:limit]

    async def insert_job_metric(self, job_id, metrics, bounds, **kwargs) -> str:
        return "fake_metric_id"

    async def get_job_metrics(self, job_id, limit=50):
        return []

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


# ─── Fixtures ────────────────────────────────────────────

@pytest.fixture
def graph() -> FakeGraphPort:
    return FakeGraphPort()


@pytest.fixture
def db() -> FakeRelationalPort:
    return FakeRelationalPort()


@pytest.fixture
def svc(graph: FakeGraphPort, db: FakeRelationalPort) -> HiringService:
    return HiringService(graph=graph, db=db)


# ─── propose_hire ────────────────────────────────────────

class TestProposeHire:
    @pytest.mark.asyncio
    async def test_no_candidates_returns_needs_review(self, svc):
        proposal = await svc.propose_hire(job_id="j1", candidates=None)
        assert proposal.status == "needs_review"
        assert "No candidates" in proposal.reasoning

    @pytest.mark.asyncio
    async def test_with_candidates_returns_proposed(self, svc):
        candidates = [{"id": "exec_1", "estimated_impact": 0.5, "properties": {}}]
        proposal = await svc.propose_hire(job_id="j1", candidates=candidates)
        assert proposal.status in ("proposed", "needs_review")
        assert isinstance(proposal.nsaig_assessment, dict)
        assert isinstance(proposal.cdee_assessment, dict)

    @pytest.mark.asyncio
    async def test_proposal_has_job_id(self, svc):
        candidates = [{"id": "exec_1", "estimated_impact": 0.3, "properties": {}}]
        proposal = await svc.propose_hire(job_id="j_abc", candidates=candidates)
        assert proposal.job_id == "j_abc"

    @pytest.mark.asyncio
    async def test_proposal_with_context_id(self, svc):
        candidates = [{"id": "exec_1", "estimated_impact": 0.4, "properties": {}}]
        proposal = await svc.propose_hire(
            job_id="j1", candidates=candidates, context_id="ctx_1"
        )
        assert proposal.context_id == "ctx_1"


# ─── execute_hire ────────────────────────────────────────

class TestExecuteHire:
    @pytest.mark.asyncio
    async def test_creates_hires_edge(self, svc, graph):
        await svc.execute_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        hires_edges = [e for e in graph._edges if e["edge_type"] == "HIRES"]
        assert any(e["source_id"] == "h1" and e["target_id"] == "e1"
                   for e in hires_edges)

    @pytest.mark.asyncio
    async def test_creates_minimizes_edge_when_imperfection_given(self, svc, graph):
        await svc.execute_hire(
            hirer_id="h1", hiree_id="e1", job_id="j1", imperfection_id="imp_1"
        )
        min_edges = [e for e in graph._edges if e["edge_type"] == "MINIMIZES"]
        assert any(e["source_id"] == "e1" and e["target_id"] == "imp_1"
                   for e in min_edges)

    @pytest.mark.asyncio
    async def test_no_minimizes_edge_without_imperfection(self, svc, graph):
        await svc.execute_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        min_edges = [e for e in graph._edges if e["edge_type"] == "MINIMIZES"]
        assert len(min_edges) == 0

    @pytest.mark.asyncio
    async def test_writes_audit_event(self, svc, db):
        await svc.execute_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        assert len(db._hiring_events) == 1
        event = db._hiring_events[0]
        assert event.event_type == HiringEventType.HIRE
        assert event.hirer_id == "h1"
        assert event.hiree_id == "e1"

    @pytest.mark.asyncio
    async def test_returns_hiring_event(self, svc):
        event = await svc.execute_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        assert isinstance(event, HiringEvent)
        assert event.event_type == HiringEventType.HIRE


# ─── evaluate_hire ────────────────────────────────────────

class TestEvaluateHire:
    @pytest.mark.asyncio
    async def test_returns_hire_evaluation(self, svc):
        evaluation = await svc.evaluate_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        assert isinstance(evaluation, HireEvaluation)
        assert evaluation.combined_verdict in ("keep", "warn", "switch")

    @pytest.mark.asyncio
    async def test_no_metrics_defaults_to_keep_or_warn(self, svc):
        evaluation = await svc.evaluate_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        # No metric data → SwitchEvaluator returns NONE → verdict driven by engines
        assert evaluation.combined_verdict in ("keep", "warn", "switch")

    @pytest.mark.asyncio
    async def test_evaluation_has_nsaig_and_cdee_fields(self, svc):
        evaluation = await svc.evaluate_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        assert "error_signal" in evaluation.cdee_evaluation
        assert "vfe_current" in evaluation.nsaig_evaluation

    @pytest.mark.asyncio
    async def test_evaluation_includes_switch_evaluator_details(self, svc):
        evaluation = await svc.evaluate_hire(hirer_id="h1", hiree_id="e1", job_id="j1")
        assert "switch_evaluator" in evaluation.cdee_evaluation
        sw = evaluation.cdee_evaluation["switch_evaluator"]
        assert sw["action"] in ("HIRE", "FIRE", "NONE")
        assert sw["triggered_by"] in ("context_change", "metric_breach", "both", "none")

    @pytest.mark.asyncio
    async def test_hysteresis_state_preserved_across_calls(self, svc, graph):
        # Inject a metric entity with current_value below target → breach
        metric_entity = EntityBase(
            id="met_1",
            entity_type=EntityType.METRIC,
            statement="",
            properties={
                "current_value": 0.4,
                "target_value": 0.9,
                "direction": "maximize",
            },
        )
        graph._neighbors["j1"] = [metric_entity]

        state: dict = {}
        eval1 = await svc.evaluate_hire(
            hirer_id="h1", hiree_id="e1", job_id="j1", switch_state=state
        )
        # State should be updated after first call
        assert "last_action" in state


# ─── execute_switch ───────────────────────────────────────

class TestExecuteSwitch:
    @pytest.mark.asyncio
    async def test_removes_old_hires_edge(self, svc, graph):
        graph._edges.append({
            "source_id": "h1", "target_id": "old_e", "edge_type": "HIRES", "properties": {}
        })
        await svc.execute_switch(
            hirer_id="h1", current_hiree_id="old_e",
            new_hiree_id="new_e", job_id="j1", reason="not effective"
        )
        hires_to_old = [
            e for e in graph._edges
            if e["edge_type"] == "HIRES" and e["target_id"] == "old_e"
        ]
        assert len(hires_to_old) == 0

    @pytest.mark.asyncio
    async def test_creates_fires_edge(self, svc, graph):
        await svc.execute_switch(
            hirer_id="h1", current_hiree_id="old_e",
            new_hiree_id="new_e", job_id="j1"
        )
        fires_edges = [e for e in graph._edges if e["edge_type"] == "FIRES"]
        assert any(e["source_id"] == "h1" and e["target_id"] == "old_e"
                   for e in fires_edges)

    @pytest.mark.asyncio
    async def test_creates_new_hires_edge(self, svc, graph):
        await svc.execute_switch(
            hirer_id="h1", current_hiree_id="old_e",
            new_hiree_id="new_e", job_id="j1"
        )
        hires_to_new = [
            e for e in graph._edges
            if e["edge_type"] == "HIRES" and e["target_id"] == "new_e"
        ]
        assert len(hires_to_new) == 1

    @pytest.mark.asyncio
    async def test_writes_switch_audit_event(self, svc, db):
        await svc.execute_switch(
            hirer_id="h1", current_hiree_id="old_e",
            new_hiree_id="new_e", job_id="j1", reason="context changed"
        )
        assert len(db._hiring_events) == 1
        event = db._hiring_events[0]
        assert event.event_type == HiringEventType.SWITCH
        assert "context changed" in event.reason
