"""Tests for BaselineService — capture, summary, switch events, phase evaluation.

Uses lightweight fakes so no live Neo4j or PostgreSQL required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.baseline_service import BaselineService


# ─── Fake Graph Port ─────────────────────────────────────

class FakeGraphPort(GraphPort):
    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []

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
        return result[offset:offset + limit]

    async def create_edge(self, source_id, target_id, edge_type, properties=None) -> bool:
        self._edges.append({
            "source_id": source_id, "target_id": target_id,
            "edge_type": edge_type.upper(), "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id, target_id, edge_type) -> bool:
        return False

    async def get_neighbors(self, entity_id, edge_type=None, direction="outgoing"):
        if direction == "outgoing":
            ids = [
                e["target_id"] for e in self._edges
                if e["source_id"] == entity_id
                and (edge_type is None or e["edge_type"] == edge_type.upper())
            ]
        else:
            ids = [
                e["source_id"] for e in self._edges
                if e["target_id"] == entity_id
                and (edge_type is None or e["edge_type"] == edge_type.upper())
            ]
        return [self._entities[i] for i in ids if i in self._entities]

    async def get_edges(self, entity_id, edge_type=None, direction="outgoing"):
        return []

    async def get_job_subgraph(self, job_id, depth=3):
        return {}

    async def add_label(self, entity_id, label):
        return True

    async def ensure_schema(self):
        return 0

    async def find_path(self, source_id, target_id, max_depth=5):
        return []

    async def get_subgraph_by_label(self, label, limit=100):
        return []

    async def verify_connectivity(self):
        return True


# ─── Fake Relational Port ────────────────────────────────

class FakeRelationalPort(RelationalPort):
    def __init__(self) -> None:
        self._baselines: list[dict] = []
        self._switch_events: list[dict] = []
        self._job_metrics: list[dict] = []

    async def save_metric_reading(self, reading): return reading.id
    async def get_metric_readings(self, metric_id, limit=100, since=None): return []
    async def get_latest_reading(self, metric_id): return None
    async def save_vfe_reading(self, reading): return reading.id
    async def get_vfe_history(self, job_id, limit=50): return []
    async def save_hiring_event(self, event): return event.id
    async def get_hiring_events(self, entity_id=None, event_type=None, limit=100): return []
    async def save_experiment(self, experiment): return experiment.id
    async def get_experiments(self, assumption_id=None, limit=50): return []
    async def verify_connectivity(self): return True
    async def save_experience_version(self, job_id, version, markers, source, confidence=None, created_by=None): return "ev_fake"
    async def get_experience_history(self, job_id, limit=50): return []

    async def insert_job_metric(self, job_id, metrics, bounds, **kwargs) -> str:
        row = {"job_id": job_id, **metrics, "bounds": bounds}
        self._job_metrics.append(row)
        return "jm_fake"

    async def get_job_metrics(self, job_id, limit=50):
        return [m for m in self._job_metrics if m["job_id"] == job_id][:limit]

    async def save_baseline_snapshot(self, scenario_id, job_id, metrics, bounds, captured_by=None):
        rec = {
            "id": f"bs_{len(self._baselines)}",
            "scenario_id": scenario_id,
            "job_id": job_id,
            "metrics": metrics,
            "bounds": bounds,
            "captured_at": datetime.now(timezone.utc),
            "captured_by": captured_by,
        }
        self._baselines.append(rec)
        return rec["id"]

    async def get_baseline_snapshot(self, scenario_id, job_id):
        matches = [
            b for b in self._baselines
            if b["scenario_id"] == scenario_id and b["job_id"] == job_id
        ]
        if matches:
            return matches[-1]
        return None

    async def save_switch_event(self, scenario_id, job_id, trigger_metric, trigger_value, trigger_bound, action, reason=""):
        rec = {
            "id": f"se_{len(self._switch_events)}",
            "scenario_id": scenario_id,
            "job_id": job_id,
            "trigger_metric": trigger_metric,
            "trigger_value": trigger_value,
            "trigger_bound": trigger_bound,
            "action": action,
            "reason": reason,
            "occurred_at": datetime.now(timezone.utc),
            "resolved_at": None,
            "resolution": None,
        }
        self._switch_events.append(rec)
        return rec["id"]

    async def get_switch_events(self, scenario_id, limit=50):
        matches = [e for e in self._switch_events if e["scenario_id"] == scenario_id]
        return matches[:limit]

    async def save_decision_trace(self, actor, action, target_entity_id, rationale="",
                                   context_snapshot=None, policies_evaluated=None,
                                   alternatives=None, vfe_before=None, vfe_after=None,
                                   lineage=None):
        return "trace-id"

    async def get_decision_traces(self, target_entity_id=None, actor=None, limit=50):
        return []

    async def save_survey_response(self, survey_id, outcome_id, session_id,
                                    importance, satisfaction, opportunity_score):
        return "resp-id"

    async def get_survey_responses(self, survey_id, outcome_id=None, limit=500):
        return []

    async def get_survey_aggregates(self, survey_id):
        return []

    async def save_context_snapshot(self, entity_id, snapshot_data, source="system"):
        return "snap-id"

    async def get_context_snapshots(self, entity_id, limit=10):
        return []


# ─── Test Helpers ────────────────────────────────────────

def _setup_scenario_tree(graph: FakeGraphPort, db: FakeRelationalPort):
    """Create a minimal Scenario → T1 → T2 → T3 tree with metrics."""
    import asyncio

    async def _build():
        scenario = EntityBase(
            id="scn_001", name="Test Scenario", statement="Test",
            entity_type=EntityType.SCENARIO,
            properties={"slug": "test_scenario", "exit_criteria": "Agent triggers switch."},
        )
        await graph.save_entity(scenario)

        t1 = EntityBase(
            id="t1_001", name="Strategic Goal", statement="Achieve goal",
            entity_type=EntityType.JOB, properties={"hierarchy_tier": "T1_strategic"},
        )
        await graph.save_entity(t1)
        await graph.create_edge("scn_001", "t1_001", "TARGETS")

        t2 = EntityBase(
            id="t2_001", name="Core Outcome", statement="Deliver outcome",
            entity_type=EntityType.JOB, properties={"hierarchy_tier": "T2_core"},
        )
        await graph.save_entity(t2)
        await graph.create_edge("t1_001", "t2_001", "HIRES")

        t3 = EntityBase(
            id="t3_001", name="Execute Step", statement="Execute step one",
            entity_type=EntityType.JOB, properties={"hierarchy_tier": "T3_execution"},
        )
        await graph.save_entity(t3)
        await graph.create_edge("t2_001", "t3_001", "HIRES")

        # Add metrics to T3
        await db.insert_job_metric("t3_001", {"accuracy": 0.85, "speed": 100.0}, {"accuracy": [0.8, 1.0], "speed": [0, 200]})

    asyncio.get_event_loop().run_until_complete(_build())


@pytest.fixture
def graph():
    return FakeGraphPort()


@pytest.fixture
def db():
    return FakeRelationalPort()


@pytest.fixture
def svc(graph, db):
    return BaselineService(graph=graph, db=db)


# ─── Capture Tests ───────────────────────────────────────

class TestCaptureBaseline:
    @pytest.mark.asyncio
    async def test_capture_stores_snapshots(self, svc, graph, db):
        # Setup scenario tree
        scenario = EntityBase(
            id="scn_001", name="Test Scenario", statement="Test",
            entity_type=EntityType.SCENARIO,
            properties={"exit_criteria": "Agent triggers switch."},
        )
        await graph.save_entity(scenario)
        t1 = EntityBase(
            id="t1_001", statement="Achieve goal",
            entity_type=EntityType.JOB, properties={},
        )
        await graph.save_entity(t1)
        await graph.create_edge("scn_001", "t1_001", "TARGETS")

        result = await svc.capture_baseline("scn_001")
        assert result["total_jobs"] >= 1
        assert len(db._baselines) >= 1

    @pytest.mark.asyncio
    async def test_capture_traverses_tree(self, svc, graph, db):
        # Build a deeper tree
        scenario = EntityBase(
            id="scn_002", statement="S2",
            entity_type=EntityType.SCENARIO, properties={},
        )
        t1 = EntityBase(
            id="t1_002", statement="Root",
            entity_type=EntityType.JOB, properties={},
        )
        t2 = EntityBase(
            id="t2_002", statement="Child",
            entity_type=EntityType.JOB, properties={},
        )
        for e in [scenario, t1, t2]:
            await graph.save_entity(e)
        await graph.create_edge("scn_002", "t1_002", "TARGETS")
        await graph.create_edge("t1_002", "t2_002", "HIRES")

        result = await svc.capture_baseline("scn_002")
        assert result["total_jobs"] == 2

    @pytest.mark.asyncio
    async def test_capture_nonexistent_scenario_raises(self, svc):
        with pytest.raises(ValueError, match="not found"):
            await svc.capture_baseline("nonexistent")


# ─── Summary Tests ───────────────────────────────────────

class TestBaselineSummary:
    @pytest.mark.asyncio
    async def test_summary_delta(self, svc, graph, db):
        """Summary should show delta between baseline and current metrics."""
        scenario = EntityBase(
            id="scn_003", statement="S3",
            entity_type=EntityType.SCENARIO, properties={},
        )
        t1 = EntityBase(
            id="t1_003", statement="Root",
            entity_type=EntityType.JOB, properties={},
        )
        for e in [scenario, t1]:
            await graph.save_entity(e)
        await graph.create_edge("scn_003", "t1_003", "TARGETS")

        # Insert baseline-era metric
        await db.insert_job_metric("t1_003", {"accuracy": 0.80}, {"accuracy": [0.7, 1.0]})
        await svc.capture_baseline("scn_003")

        # Insert newer metric
        db._job_metrics = [{"job_id": "t1_003", "accuracy": 0.90, "bounds": {}}]

        summary = await svc.get_summary("scn_003")
        assert len(summary["comparisons"]) == 1
        delta = summary["comparisons"][0]["deltas"]["accuracy"]
        assert delta == pytest.approx(0.10)


# ─── Switch Event Tests ─────────────────────────────────

class TestSwitchEvents:
    @pytest.mark.asyncio
    async def test_record_switch_event(self, svc, graph, db):
        result = await svc.record_switch_event(
            scenario_id="scn_001",
            job_id="t3_001",
            trigger_metric="accuracy",
            trigger_value=0.75,
            trigger_bound="< 0.8",
            action="fire",
            reason="Below threshold",
        )
        assert result["action"] == "fire"
        assert len(db._switch_events) == 1

    @pytest.mark.asyncio
    async def test_get_switch_events(self, svc, graph, db):
        await svc.record_switch_event(
            scenario_id="scn_001", job_id="t3_001",
            trigger_metric="accuracy", trigger_value=0.75,
            trigger_bound="< 0.8", action="fire",
        )
        events = await svc.get_switch_events("scn_001")
        assert len(events) == 1


# ─── Phase Evaluation Tests ─────────────────────────────

class TestPhaseEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_no_criteria_inconclusive(self, svc, graph, db):
        """No exit criteria → inconclusive."""
        scenario = EntityBase(
            id="scn_noec", statement="S",
            entity_type=EntityType.SCENARIO,
            properties={},  # No exit_criteria
        )
        await graph.save_entity(scenario)
        result = await svc.evaluate_phase("scn_noec")
        assert result["verdict"] == "inconclusive"

    @pytest.mark.asyncio
    async def test_evaluate_go_with_fire_events(self, svc, graph, db):
        """Fire events triggered + no degradation → go."""
        scenario = EntityBase(
            id="scn_go", statement="S",
            entity_type=EntityType.SCENARIO,
            properties={"exit_criteria": "Agent triggers switch."},
        )
        t1 = EntityBase(
            id="t1_go", statement="Root",
            entity_type=EntityType.JOB, properties={},
        )
        for e in [scenario, t1]:
            await graph.save_entity(e)
        await graph.create_edge("scn_go", "t1_go", "TARGETS")

        # Record a fire event
        await svc.record_switch_event(
            scenario_id="scn_go", job_id="t1_go",
            trigger_metric="accuracy", trigger_value=0.75,
            trigger_bound="< 0.8", action="fire",
        )

        result = await svc.evaluate_phase("scn_go")
        assert result["verdict"] == "go"

    @pytest.mark.asyncio
    async def test_evaluate_inconclusive_no_data(self, svc, graph, db):
        """No metrics or switch events → inconclusive."""
        scenario = EntityBase(
            id="scn_inc", statement="S",
            entity_type=EntityType.SCENARIO,
            properties={"exit_criteria": "Something."},
        )
        await graph.save_entity(scenario)
        result = await svc.evaluate_phase("scn_inc")
        assert result["verdict"] == "inconclusive"
