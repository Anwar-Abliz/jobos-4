"""Integration tests for the pilot lifecycle.

End-to-end: seed → verify tree → capture baseline → insert metric →
record switch → get summary → evaluate phase.

Uses lightweight fakes — no live databases required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.pilot import PilotDefinition, PilotMetric, PilotRisk
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.pilot_service import PilotService
from jobos.services.experience_service import ExperienceService
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
        if status:
            result = [e for e in result if e.status == status]
        return result[offset:offset + limit]

    async def create_edge(self, source_id, target_id, edge_type, properties=None) -> bool:
        self._edges.append({
            "source_id": source_id, "target_id": target_id,
            "edge_type": edge_type.upper(), "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id, target_id, edge_type) -> bool:
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (e["source_id"] == source_id and e["target_id"] == target_id
                    and e["edge_type"] == edge_type.upper())
        ]
        return len(self._edges) < before

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
        self._experience_versions: list[dict] = []

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

    async def insert_job_metric(self, job_id, metrics, bounds, **kwargs) -> str:
        row = {"job_id": job_id, **metrics, "bounds": bounds}
        self._job_metrics.append(row)
        return "jm_fake"

    async def get_job_metrics(self, job_id, limit=50):
        return [m for m in self._job_metrics if m["job_id"] == job_id][:limit]

    async def save_experience_version(self, job_id, version, markers, source, confidence=None, created_by=None):
        rec = {
            "id": f"ev_{len(self._experience_versions)}",
            "job_id": job_id, "version": version, "markers": markers,
            "source": source, "confidence": confidence, "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        self._experience_versions.append(rec)
        return rec["id"]

    async def get_experience_history(self, job_id, limit=50):
        history = [r for r in self._experience_versions if r["job_id"] == job_id]
        history.sort(key=lambda r: r["version"], reverse=True)
        return history[:limit]

    async def save_baseline_snapshot(self, scenario_id, job_id, metrics, bounds, captured_by=None):
        rec = {
            "id": f"bs_{len(self._baselines)}",
            "scenario_id": scenario_id, "job_id": job_id,
            "metrics": metrics, "bounds": bounds,
            "captured_at": datetime.now(timezone.utc), "captured_by": captured_by,
        }
        self._baselines.append(rec)
        return rec["id"]

    async def get_baseline_snapshot(self, scenario_id, job_id):
        matches = [
            b for b in self._baselines
            if b["scenario_id"] == scenario_id and b["job_id"] == job_id
        ]
        return matches[-1] if matches else None

    async def save_switch_event(self, scenario_id, job_id, trigger_metric, trigger_value, trigger_bound, action, reason=""):
        rec = {
            "id": f"se_{len(self._switch_events)}",
            "scenario_id": scenario_id, "job_id": job_id,
            "trigger_metric": trigger_metric, "trigger_value": trigger_value,
            "trigger_bound": trigger_bound, "action": action, "reason": reason,
            "occurred_at": datetime.now(timezone.utc), "resolved_at": None, "resolution": None,
        }
        self._switch_events.append(rec)
        return rec["id"]

    async def get_switch_events(self, scenario_id, limit=50):
        return [e for e in self._switch_events if e["scenario_id"] == scenario_id][:limit]

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


# ─── Helpers ─────────────────────────────────────────────

def _make_pilot(**overrides) -> PilotDefinition:
    defaults = {
        "pilot_id": "PILOT_INT",
        "segment": "Integration Test Segment",
        "tier_1_strategic": "Accelerate integration testing.",
        "tier_2_core": "Validate end-to-end pilot lifecycle.",
        "tier3_steps": [
            "Define test scope.",
            "Locate test dependencies.",
            "Prepare test environment.",
            "Execute test suite.",
            "Monitor test outcomes.",
            "Modify failing assertions.",
            "Conclude and report results.",
        ],
        "dimension_b_metrics": [
            PilotMetric(name="Pass Rate", description="Test pass rate", target="100%", switch_trigger_threshold="< 90%"),
        ],
        "hypothesis": "End-to-end lifecycle works correctly.",
        "exit_criteria": "All lifecycle steps complete successfully.",
        "risks": [PilotRisk(risk="Flaky tests", mitigation="Retry logic")],
    }
    defaults.update(overrides)
    return PilotDefinition(**defaults)


@pytest.fixture
def graph():
    return FakeGraphPort()


@pytest.fixture
def db():
    return FakeRelationalPort()


# ─── Full Lifecycle Test ─────────────────────────────────

class TestPilotLifecycle:
    @pytest.mark.asyncio
    async def test_seed_verify_baseline_switch_evaluate(self, graph, db):
        """Full lifecycle: seed → verify → baseline → metric → switch → evaluate."""
        pilot = _make_pilot()
        pilot_svc = PilotService(graph=graph)
        baseline_svc = BaselineService(graph=graph, db=db)

        # 1. Seed the pilot
        seed_result = await pilot_svc.seed_pilot(pilot)
        assert seed_result["total_entities"] == 39  # 1seg + 1scn + 1T1 + 1T2 + 7T3 + 28T4

        # 2. Verify tree structure
        scenario_id = seed_result["scenario_id"]
        t1_id = seed_result["t1_id"]

        # Verify TARGETS edge exists
        targets_edges = [
            e for e in graph._edges
            if e["source_id"] == scenario_id and e["edge_type"] == "TARGETS"
        ]
        assert len(targets_edges) == 1
        assert targets_edges[0]["target_id"] == t1_id

        # 3. Insert metric for a T3 job
        t3_jobs = [
            e for e in graph._entities.values()
            if e.entity_type == EntityType.JOB
            and e.properties.get("hierarchy_tier") == "T3_execution"
        ]
        assert len(t3_jobs) == 7
        t3_id = t3_jobs[0].id
        await db.insert_job_metric(t3_id, {"accuracy": 0.85, "speed": 100.0}, {"accuracy": [0.8, 1.0]})

        # 4. Capture baseline
        baseline_result = await baseline_svc.capture_baseline(scenario_id)
        assert baseline_result["total_jobs"] >= 1

        # 5. Update metric (simulate improvement)
        db._job_metrics = [m for m in db._job_metrics if m["job_id"] != t3_id]
        await db.insert_job_metric(t3_id, {"accuracy": 0.92, "speed": 120.0}, {"accuracy": [0.8, 1.0]})

        # 6. Get summary — should show delta
        summary = await baseline_svc.get_summary(scenario_id)
        assert summary["total_compared"] >= 1

        # 7. Record a switch event
        await baseline_svc.record_switch_event(
            scenario_id=scenario_id,
            job_id=t3_id,
            trigger_metric="accuracy",
            trigger_value=0.75,
            trigger_bound="< 0.8",
            action="fire",
            reason="Below threshold",
        )

        # 8. Get switch events
        events = await baseline_svc.get_switch_events(scenario_id)
        assert len(events) == 1

        # 9. Evaluate phase
        evaluation = await baseline_svc.evaluate_phase(scenario_id)
        assert evaluation["verdict"] in ("go", "no_go", "inconclusive")
        assert evaluation["switch_events_count"] == 1


class TestSeedIdempotency:
    @pytest.mark.asyncio
    async def test_double_seed_no_duplicates(self, graph, db):
        """Seeding the same pilot twice should not create duplicates."""
        pilot = _make_pilot()
        svc = PilotService(graph=graph)

        r1 = await svc.seed_pilot(pilot)
        entity_count_1 = len(graph._entities)

        r2 = await svc.seed_pilot(pilot)
        entity_count_2 = len(graph._entities)

        assert r1["segment_id"] == r2["segment_id"]
        assert r1["scenario_id"] == r2["scenario_id"]
        assert entity_count_1 == entity_count_2


class TestExperienceLifecycle:
    @pytest.mark.asyncio
    async def test_generate_then_edit(self, graph, db):
        """Generate experience, then edit with human override."""
        # Create a job first
        job = EntityBase(
            id="job_exp_test",
            name="Test Job",
            statement="Execute test action",
            entity_type=EntityType.JOB,
            properties={"scope_id": "test", "hierarchy_tier": "T3_execution"},
        )
        await graph.save_entity(job)

        exp_svc = ExperienceService(graph=graph, db=db, llm=None)

        # Generate (template fallback)
        gen_result = await exp_svc.generate(job_id="job_exp_test")
        assert gen_result["version"] == 1
        assert gen_result["source"] == "manual"

        # Edit with override
        edit_result = await exp_svc.edit(
            job_id="job_exp_test",
            markers={
                "feel_markers": ["Feel confident in the process"],
                "to_be_markers": ["To be seen as thorough"],
            },
        )
        assert edit_result["version"] == 2
        assert edit_result["source"] == "override"

        # Check history
        history = await exp_svc.get_history("job_exp_test")
        assert len(history) == 2
        assert history[0]["version"] == 2


class TestEmptyDimensionBGraceful:
    @pytest.mark.asyncio
    async def test_seed_with_no_metrics(self, graph, db):
        """Pilot with empty dimension B metrics should seed without errors."""
        pilot = _make_pilot(dimension_b_metrics=[])
        svc = PilotService(graph=graph)
        result = await svc.seed_pilot(pilot)
        assert result["total_entities"] == 39

        scenario = graph._entities[result["scenario_id"]]
        assert scenario.properties["dimension_b_metrics"] == []


class TestTreeVerification:
    @pytest.mark.asyncio
    async def test_t3_has_correct_step_numbers(self, graph, db):
        """T3 jobs should have step_number 1-7."""
        pilot = _make_pilot()
        svc = PilotService(graph=graph)
        await svc.seed_pilot(pilot)

        t3_jobs = [
            e for e in graph._entities.values()
            if e.entity_type == EntityType.JOB
            and e.properties.get("hierarchy_tier") == "T3_execution"
        ]
        step_numbers = sorted([e.properties.get("step_number", 0) for e in t3_jobs])
        assert step_numbers == [1, 2, 3, 4, 5, 6, 7]

    @pytest.mark.asyncio
    async def test_each_t3_has_4_t4_children(self, graph, db):
        """Each T3 should have exactly 4 T4 micro-job children."""
        pilot = _make_pilot()
        svc = PilotService(graph=graph)
        await svc.seed_pilot(pilot)

        t3_jobs = [
            e for e in graph._entities.values()
            if e.entity_type == EntityType.JOB
            and e.properties.get("hierarchy_tier") == "T3_execution"
        ]
        for t3 in t3_jobs:
            children_edges = [
                e for e in graph._edges
                if e["source_id"] == t3.id and e["edge_type"] == "HIRES"
            ]
            assert len(children_edges) == 4, (
                f"T3 {t3.id} (step {t3.properties.get('step_number')}) "
                f"has {len(children_edges)} T4 children, expected 4"
            )


class TestScenarioGraph:
    @pytest.mark.asyncio
    async def test_segment_contains_scenario(self, graph, db):
        """CONTAINS edge should link Segment to Scenario."""
        pilot = _make_pilot()
        svc = PilotService(graph=graph)
        result = await svc.seed_pilot(pilot)

        contains = [
            e for e in graph._edges
            if e["edge_type"] == "CONTAINS"
            and e["source_id"] == result["segment_id"]
            and e["target_id"] == result["scenario_id"]
        ]
        assert len(contains) >= 1

    @pytest.mark.asyncio
    async def test_scenario_targets_t1(self, graph, db):
        """TARGETS edge should link Scenario to T1."""
        pilot = _make_pilot()
        svc = PilotService(graph=graph)
        result = await svc.seed_pilot(pilot)

        targets = [
            e for e in graph._edges
            if e["edge_type"] == "TARGETS"
            and e["source_id"] == result["scenario_id"]
            and e["target_id"] == result["t1_id"]
        ]
        assert len(targets) >= 1
