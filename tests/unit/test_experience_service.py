"""Tests for ExperienceService — generation, validation, versioning, graph commit.

Uses lightweight fakes so no live Neo4j or PostgreSQL required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.axioms import AxiomViolation
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.experience_service import ExperienceService


# ─── Fake Graph Port ─────────────────────────────────────

class FakeGraphPort(GraphPort):
    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []
        self._added_labels: list[tuple[str, str]] = []

    async def save_entity(self, entity: EntityBase) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self._entities.get(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        return self._entities.pop(entity_id, None) is not None

    async def list_entities(
        self, entity_type: str | None = None, status: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[EntityBase]:
        result = list(self._entities.values())
        if entity_type:
            result = [e for e in result if e.entity_type.value == entity_type]
        return result[offset:offset + limit]

    async def create_edge(
        self, source_id: str, target_id: str, edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        self._edges.append({
            "source_id": source_id, "target_id": target_id,
            "edge_type": edge_type.upper(), "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id: str, target_id: str, edge_type: str) -> bool:
        return False

    async def get_neighbors(self, entity_id: str, edge_type: str | None = None,
                            direction: str = "outgoing") -> list[EntityBase]:
        return []

    async def get_edges(self, entity_id: str, edge_type: str | None = None,
                        direction: str = "outgoing") -> list[dict[str, Any]]:
        return []

    async def get_job_subgraph(self, job_id: str, depth: int = 3) -> dict[str, Any]:
        return {}

    async def add_label(self, entity_id: str, label: str) -> bool:
        self._added_labels.append((entity_id, label))
        return True

    async def ensure_schema(self) -> int:
        return 0

    async def verify_connectivity(self) -> bool:
        return True


# ─── Fake Relational Port ────────────────────────────────

class FakeRelationalPort(RelationalPort):
    def __init__(self) -> None:
        self._experience_versions: list[dict[str, Any]] = []

    async def save_metric_reading(self, reading) -> str:
        return reading.id

    async def get_metric_readings(self, metric_id, limit=100, since=None):
        return []

    async def get_latest_reading(self, metric_id):
        return None

    async def save_vfe_reading(self, reading) -> str:
        return reading.id

    async def get_vfe_history(self, job_id, limit=50):
        return []

    async def save_hiring_event(self, event) -> str:
        return event.id

    async def get_hiring_events(self, entity_id=None, event_type=None, limit=100):
        return []

    async def save_experiment(self, experiment) -> str:
        return experiment.id

    async def get_experiments(self, assumption_id=None, limit=50):
        return []

    async def insert_job_metric(self, job_id, metrics, bounds, **kwargs) -> str:
        return "fake_id"

    async def get_job_metrics(self, job_id, limit=50):
        return []

    async def verify_connectivity(self) -> bool:
        return True

    async def save_experience_version(
        self, job_id, version, markers, source,
        confidence=None, created_by=None,
    ) -> str:
        rec = {
            "id": f"ev_{len(self._experience_versions)}",
            "job_id": job_id,
            "version": version,
            "markers": markers,
            "source": source,
            "confidence": confidence,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        self._experience_versions.append(rec)
        return rec["id"]

    async def get_experience_history(self, job_id, limit=50):
        history = [
            r for r in self._experience_versions if r["job_id"] == job_id
        ]
        history.sort(key=lambda r: r["version"], reverse=True)
        return history[:limit]

    async def save_baseline_snapshot(self, scenario_id, job_id, metrics, bounds, captured_by=None):
        return "bs_fake"

    async def get_baseline_snapshot(self, scenario_id, job_id):
        return None

    async def save_switch_event(self, scenario_id, job_id, trigger_metric, trigger_value, trigger_bound, action, reason=""):
        return "se_fake"

    async def get_switch_events(self, scenario_id, limit=50):
        return []


# ─── Fixtures ────────────────────────────────────────────

def _make_job(job_id="job_001", statement="Define the scope", scope_id="test") -> EntityBase:
    return EntityBase(
        id=job_id,
        name=statement[:80],
        statement=statement,
        entity_type=EntityType.JOB,
        properties={
            "job_type": "core_functional",
            "scope_id": scope_id,
            "hierarchy_tier": "T3_execution",
        },
    )


@pytest.fixture
def graph() -> FakeGraphPort:
    return FakeGraphPort()


@pytest.fixture
def db() -> FakeRelationalPort:
    return FakeRelationalPort()


@pytest.fixture
def svc(graph: FakeGraphPort, db: FakeRelationalPort) -> ExperienceService:
    return ExperienceService(graph=graph, db=db, llm=None)


# ─── Generate Tests ──────────────────────────────────────

class TestExperienceGenerate:
    @pytest.mark.asyncio
    async def test_generate_template_fallback(self, svc, graph, db):
        """Without LLM, should use template fallback."""
        job = _make_job()
        await graph.save_entity(job)
        result = await svc.generate(job_id=job.id)
        assert result["source"] == "manual"
        assert len(result["markers"]["feel_markers"]) == 3
        assert len(result["markers"]["to_be_markers"]) == 3
        assert result["version"] == 1

    @pytest.mark.asyncio
    async def test_generate_creates_experience_entity(self, svc, graph, db):
        """Generate should create an :Experience entity in the graph."""
        job = _make_job()
        await graph.save_entity(job)
        result = await svc.generate(job_id=job.id)
        exp_id = result["experience_id"]
        exp = graph._entities.get(exp_id)
        assert exp is not None
        assert "Experience" in exp.labels

    @pytest.mark.asyncio
    async def test_generate_creates_experience_of_edge(self, svc, graph, db):
        """Generate should create an EXPERIENCE_OF edge."""
        job = _make_job()
        await graph.save_entity(job)
        result = await svc.generate(job_id=job.id)
        exp_of_edges = [
            e for e in graph._edges if e["edge_type"] == "EXPERIENCE_OF"
        ]
        assert len(exp_of_edges) == 1
        assert exp_of_edges[0]["target_id"] == job.id

    @pytest.mark.asyncio
    async def test_generate_saves_version_to_db(self, svc, graph, db):
        """Generate should persist a version record."""
        job = _make_job()
        await graph.save_entity(job)
        await svc.generate(job_id=job.id)
        assert len(db._experience_versions) == 1
        assert db._experience_versions[0]["version"] == 1

    @pytest.mark.asyncio
    async def test_generate_nonexistent_job_raises(self, svc):
        """Generating for nonexistent job should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await svc.generate(job_id="nonexistent")


# ─── Edit Tests ──────────────────────────────────────────

class TestExperienceEdit:
    @pytest.mark.asyncio
    async def test_edit_valid_markers(self, svc, graph, db):
        """Edit with valid markers should create new version."""
        job = _make_job()
        await graph.save_entity(job)
        # First generate
        await svc.generate(job_id=job.id)
        # Then edit
        result = await svc.edit(
            job_id=job.id,
            markers={
                "feel_markers": ["Feel confident in accuracy"],
                "to_be_markers": ["To be seen as reliable"],
            },
        )
        assert result["version"] == 2
        assert result["source"] == "override"
        assert result["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_edit_invalid_marker_raises_axiom_5(self, svc, graph, db):
        """Edit with non-experiential marker should raise AxiomViolation."""
        job = _make_job()
        await graph.save_entity(job)
        with pytest.raises(AxiomViolation) as exc_info:
            await svc.edit(
                job_id=job.id,
                markers={
                    "feel_markers": ["Define the roadmap"],  # Not experiential
                    "to_be_markers": [],
                },
            )
        assert exc_info.value.axiom == 5

    @pytest.mark.asyncio
    async def test_edit_creates_new_version(self, svc, graph, db):
        """Edit should increment version number."""
        job = _make_job()
        await graph.save_entity(job)
        await svc.generate(job_id=job.id)
        await svc.edit(
            job_id=job.id,
            markers={"feel_markers": ["Feel empowered"], "to_be_markers": []},
        )
        assert len(db._experience_versions) == 2
        assert db._experience_versions[-1]["version"] == 2


# ─── Reconciliation Tests ───────────────────────────────

class TestExperienceReconciliation:
    @pytest.mark.asyncio
    async def test_reconciliation_with_t1(self, svc, graph, db):
        """Reconciliation should return a score based on keyword overlap."""
        # Create T1 root
        t1 = EntityBase(
            id="t1_root",
            name="Accelerate market penetration",
            statement="Accelerate global market penetration",
            entity_type=EntityType.JOB,
            properties={
                "root_token": "ROOT",
                "scope_id": "test",
                "hierarchy_tier": "T1_strategic",
            },
        )
        await graph.save_entity(t1)
        # Create T3 job in same scope
        job = _make_job(scope_id="test")
        await graph.save_entity(job)
        result = await svc.generate(job_id=job.id)
        assert "reconciliation_score" in result
        # Score should be a float >= 0
        assert isinstance(result["reconciliation_score"], float)
        assert result["reconciliation_score"] >= 0.0


# ─── History Tests ───────────────────────────────────────

class TestExperienceHistory:
    @pytest.mark.asyncio
    async def test_history_ordered_by_version_desc(self, svc, graph, db):
        """History should return versions in descending order."""
        job = _make_job()
        await graph.save_entity(job)
        await svc.generate(job_id=job.id)
        await svc.edit(
            job_id=job.id,
            markers={"feel_markers": ["Feel confident"], "to_be_markers": []},
        )
        history = await svc.get_history(job.id)
        assert len(history) == 2
        assert history[0]["version"] > history[1]["version"]
