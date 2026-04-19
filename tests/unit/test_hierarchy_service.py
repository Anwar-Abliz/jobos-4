"""Tests for HierarchyService — generation, functional T4 micro-jobs, persistence.

Covers:
- Template fallback generation (LLM disabled)
- T1 gets root_token='ROOT' and scope_id
- T4 Micro-Jobs are functional (action verbs, metrics, no :Experience label)
- GenerativeModel is computed per job (correct tier fields)
- Dimension B: job_metrics scaffold is written for T2+T3+T4 jobs
- HIRES edge topology: T1→T2, T2→T3, T3→T4
- Axiom 5: all statements start with action verb (including T4)
- to_tree_dict() builds full functional spine T1→T2→T3→T4
- Experience dimension is populated from Dimension A nodes (orthogonal, not a tier)
"""
from __future__ import annotations

from typing import Any

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.hierarchy import (
    HierarchyContext,
    HierarchyJob,
    HierarchyResult,
    JobTier,
    T3_STANDARD_STEPS,
)
from jobos.kernel.generative_model import GenerativeModel, map_tier_to_generative_model
from jobos.kernel.job_statement import validate_verb
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.hierarchy_service import HierarchyService


# ─── Fake Ports ──────────────────────────────────────────

class FakeGraphPort(GraphPort):
    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []
        self._labels: list[tuple[str, str]] = []

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
        if direction == "outgoing":
            neighbor_ids = [
                e["target_id"] for e in self._edges
                if e["source_id"] == entity_id
                and (edge_type is None or e["edge_type"] == edge_type)
            ]
        else:
            neighbor_ids = [
                e["source_id"] for e in self._edges
                if e["target_id"] == entity_id
                and (edge_type is None or e["edge_type"] == edge_type)
            ]
        return [self._entities[nid] for nid in neighbor_ids if nid in self._entities]

    async def get_edges(self, entity_id, edge_type=None, direction="outgoing"):
        return []

    async def get_job_subgraph(self, job_id, depth=3):
        return {}

    async def add_label(self, entity_id: str, label: str) -> bool:
        self._labels.append((entity_id, label))
        return True

    async def ensure_schema(self) -> int:
        return 0

    async def verify_connectivity(self) -> bool:
        return True


class FakeRelationalPort(RelationalPort):
    def __init__(self) -> None:
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

    async def insert_job_metric(self, job_id, metrics, bounds, **kwargs) -> str:
        self._job_metrics.append({
            "job_id": job_id, "metrics": metrics, "bounds": bounds, **kwargs
        })
        return f"mid_{job_id}"

    async def get_job_metrics(self, job_id, limit=50): return []
    async def verify_connectivity(self): return True
    async def save_experience_version(self, job_id, version, markers, source, confidence=None, created_by=None): return "ev_fake"
    async def get_experience_history(self, job_id, limit=50): return []
    async def save_baseline_snapshot(self, scenario_id, job_id, metrics, bounds, captured_by=None): return "bs_fake"
    async def get_baseline_snapshot(self, scenario_id, job_id): return None
    async def save_switch_event(self, scenario_id, job_id, trigger_metric, trigger_value, trigger_bound, action, reason=""): return "se_fake"
    async def get_switch_events(self, scenario_id, limit=50): return []


# ─── Fixtures ────────────────────────────────────────────

@pytest.fixture
def graph():
    return FakeGraphPort()


@pytest.fixture
def db():
    return FakeRelationalPort()


@pytest.fixture
def svc(graph, db):
    return HierarchyService(graph=graph, db=db)


def saas_context() -> HierarchyContext:
    return HierarchyContext(domain="b2b_saas", keywords=["saas"])


# ─── Basic generation ────────────────────────────────────

class TestHierarchyGeneration:
    @pytest.mark.asyncio
    async def test_generate_returns_hierarchy_result(self, svc):
        result = await svc.generate(saas_context())
        assert isinstance(result, HierarchyResult)
        assert result.id

    @pytest.mark.asyncio
    async def test_all_four_tiers_present(self, svc):
        result = await svc.generate(saas_context())
        tiers = {j.tier for j in result.jobs}
        assert JobTier.STRATEGIC in tiers
        assert JobTier.CORE_FUNCTIONAL in tiers
        assert JobTier.EXECUTION in tiers
        assert JobTier.MICRO_JOB in tiers

    @pytest.mark.asyncio
    async def test_t1_has_one_or_two_jobs(self, svc):
        result = await svc.generate(saas_context())
        t1 = result.jobs_at_tier(JobTier.STRATEGIC)
        assert 1 <= len(t1) <= 2

    @pytest.mark.asyncio
    async def test_all_statements_start_with_action_verb(self, svc):
        """All tiers including T4 must start with an action verb (Axiom 5)."""
        result = await svc.generate(saas_context())
        for job in result.jobs:
            assert validate_verb(job.statement), (
                f"Job missing action verb: {job.statement!r} (tier={job.tier.value})"
            )

    @pytest.mark.asyncio
    async def test_summary_has_correct_keys(self, svc):
        result = await svc.generate(saas_context())
        for key in ("T1_strategic", "T2_core", "T3_execution", "T4_micro",
                    "total_jobs", "total_edges"):
            assert key in result.summary

    @pytest.mark.asyncio
    async def test_template_fallback_for_unknown_domain(self, svc):
        ctx = HierarchyContext(domain="quantum_computing", keywords=[])
        result = await svc.generate(ctx)
        # Falls back to b2b_saas template — should still produce full hierarchy
        assert len(result.jobs) > 0
        tiers = {j.tier for j in result.jobs}
        assert JobTier.STRATEGIC in tiers


# ─── Axiom 6: T1 gets root_token ─────────────────────────

class TestT1RootToken:
    @pytest.mark.asyncio
    async def test_t1_jobs_have_root_token(self, svc):
        result = await svc.generate(saas_context())
        t1_jobs = result.jobs_at_tier(JobTier.STRATEGIC)
        for job in t1_jobs:
            assert job.root_token == "ROOT", f"T1 job missing root_token: {job.id}"

    @pytest.mark.asyncio
    async def test_t1_jobs_have_scope_id(self, svc):
        result = await svc.generate(saas_context())
        t1_jobs = result.jobs_at_tier(JobTier.STRATEGIC)
        for job in t1_jobs:
            assert job.scope_id, f"T1 job missing scope_id: {job.id}"

    @pytest.mark.asyncio
    async def test_t2_t3_t4_jobs_have_no_root_token(self, svc):
        result = await svc.generate(saas_context())
        for job in result.jobs:
            if job.tier in (JobTier.CORE_FUNCTIONAL, JobTier.EXECUTION, JobTier.MICRO_JOB):
                assert job.root_token is None

    @pytest.mark.asyncio
    async def test_t1_persisted_with_root_token_in_properties(self, svc, graph):
        result = await svc.generate(saas_context())
        t1_jobs = result.jobs_at_tier(JobTier.STRATEGIC)
        for job in t1_jobs:
            entity = graph._entities.get(job.id)
            assert entity is not None
            assert entity.properties.get("root_token") == "ROOT"
            assert entity.properties.get("scope_id")


# ─── T4 Micro-Jobs are functional ────────────────────────

class TestT4MicroJob:
    @pytest.mark.asyncio
    async def test_t4_jobs_have_functional_job_type(self, svc, graph):
        """T4 Micro-Jobs are functional, not emotional."""
        result = await svc.generate(saas_context())
        t4_jobs = result.jobs_at_tier(JobTier.MICRO_JOB)
        for job in t4_jobs:
            entity = graph._entities.get(job.id)
            assert entity is not None, f"T4 job {job.id} not persisted"
            assert entity.properties.get("job_type") == "core_functional", (
                f"T4 job {job.id!r} should have job_type='core_functional', "
                f"got {entity.properties.get('job_type')!r}"
            )

    @pytest.mark.asyncio
    async def test_t4_jobs_do_not_get_experience_label(self, svc, graph):
        """T4 is functional — no :Experience label."""
        result = await svc.generate(saas_context())
        labeled_ids = {eid for eid, lbl in graph._labels if lbl == "Experience"}
        t4_ids = {j.id for j in result.jobs_at_tier(JobTier.MICRO_JOB)}
        for jid in t4_ids:
            assert jid not in labeled_ids, (
                f"T4 Micro-Job {jid} should not receive :Experience label"
            )

    @pytest.mark.asyncio
    async def test_t4_statements_start_with_action_verb(self, svc):
        """T4 Micro-Jobs must start with an action verb like all functional tiers."""
        result = await svc.generate(saas_context())
        for job in result.jobs_at_tier(JobTier.MICRO_JOB):
            assert validate_verb(job.statement), (
                f"T4 Micro-Job missing action verb: {job.statement!r}"
            )

    @pytest.mark.asyncio
    async def test_t4_has_metrics_hint(self, svc):
        """T4 Micro-Jobs should carry metrics hints (they are measurable)."""
        result = await svc.generate(saas_context())
        for job in result.jobs_at_tier(JobTier.MICRO_JOB):
            assert len(job.metrics_hint) > 0, (
                f"T4 Micro-Job {job.id} should have at least one metric hint"
            )


# ─── Dimension B: job_metrics scaffold ───────────────────

class TestDimensionBJobMetrics:
    @pytest.mark.asyncio
    async def test_job_metrics_written_for_t2_jobs(self, svc, db):
        result = await svc.generate(saas_context())
        t2_ids = {j.id for j in result.jobs_at_tier(JobTier.CORE_FUNCTIONAL)}
        written_ids = {m["job_id"] for m in db._job_metrics}
        for jid in t2_ids:
            assert jid in written_ids, f"T2 job {jid} missing job_metrics scaffold"

    @pytest.mark.asyncio
    async def test_job_metrics_written_for_t3_jobs(self, svc, db):
        result = await svc.generate(saas_context())
        t3_ids = {j.id for j in result.jobs_at_tier(JobTier.EXECUTION)}
        written_ids = {m["job_id"] for m in db._job_metrics}
        for jid in t3_ids:
            assert jid in written_ids, f"T3 job {jid} missing job_metrics scaffold"

    @pytest.mark.asyncio
    async def test_job_metrics_written_for_t4_jobs(self, svc, db):
        """T4 Micro-Jobs are functional and get job_metrics scaffold."""
        result = await svc.generate(saas_context())
        t4_ids = {j.id for j in result.jobs_at_tier(JobTier.MICRO_JOB)}
        written_ids = {m["job_id"] for m in db._job_metrics}
        for jid in t4_ids:
            assert jid in written_ids, (
                f"T4 Micro-Job {jid} should get job_metrics scaffold (it's functional)"
            )

    @pytest.mark.asyncio
    async def test_job_metrics_have_bounds(self, svc, db):
        await svc.generate(saas_context())
        for entry in db._job_metrics:
            assert "bounds" in entry
            assert isinstance(entry["bounds"], dict)


# ─── GenerativeModel integration ─────────────────────────

class TestGenerativeModelIntegration:
    @pytest.mark.asyncio
    async def test_result_carries_generative_models(self, svc):
        result = await svc.generate(saas_context())
        assert hasattr(result, "generative_models"), (
            "HierarchyResult should carry a generative_models dict"
        )

    @pytest.mark.asyncio
    async def test_t1_generative_model_has_prior_aspiration(self, svc):
        result = await svc.generate(saas_context())
        for job in result.jobs_at_tier(JobTier.STRATEGIC):
            gm = result.generative_models.get(job.id)
            assert gm is not None, f"No GenerativeModel for T1 job {job.id}"
            assert gm.prior_aspiration == job.statement
            assert gm.primary_goal == ""

    @pytest.mark.asyncio
    async def test_t2_generative_model_has_primary_goal(self, svc):
        result = await svc.generate(saas_context())
        for job in result.jobs_at_tier(JobTier.CORE_FUNCTIONAL):
            gm = result.generative_models.get(job.id)
            assert gm is not None
            assert gm.primary_goal == job.statement
            assert gm.prior_aspiration == ""

    @pytest.mark.asyncio
    async def test_t3_generative_model_has_execution_steps(self, svc):
        result = await svc.generate(saas_context())
        for job in result.jobs_at_tier(JobTier.EXECUTION):
            gm = result.generative_models.get(job.id)
            assert gm is not None
            assert gm.execution_steps == T3_STANDARD_STEPS
            assert len(gm.execution_steps) == 8

    @pytest.mark.asyncio
    async def test_t4_generative_model_has_primary_goal(self, svc):
        """T4 Micro-Job sets primary_goal (functional), not prior_aspiration."""
        result = await svc.generate(saas_context())
        for job in result.jobs_at_tier(JobTier.MICRO_JOB):
            gm = result.generative_models.get(job.id)
            assert gm is not None
            assert gm.primary_goal == job.statement
            assert gm.micro_actions == []


# ─── Edge topology ────────────────────────────────────────

class TestEdgeTopology:
    @pytest.mark.asyncio
    async def test_t1_hires_t2(self, svc):
        result = await svc.generate(saas_context())
        t1_ids = {j.id for j in result.jobs_at_tier(JobTier.STRATEGIC)}
        t2_ids = {j.id for j in result.jobs_at_tier(JobTier.CORE_FUNCTIONAL)}
        t1_to_t2 = [
            e for e in result.edges
            if e.parent_id in t1_ids and e.child_id in t2_ids
        ]
        assert len(t1_to_t2) > 0

    @pytest.mark.asyncio
    async def test_t2_hires_t3(self, svc):
        result = await svc.generate(saas_context())
        t2_ids = {j.id for j in result.jobs_at_tier(JobTier.CORE_FUNCTIONAL)}
        t3_ids = {j.id for j in result.jobs_at_tier(JobTier.EXECUTION)}
        t2_to_t3 = [
            e for e in result.edges
            if e.parent_id in t2_ids and e.child_id in t3_ids
        ]
        assert len(t2_to_t3) > 0

    @pytest.mark.asyncio
    async def test_t3_hires_t4(self, svc):
        """T3→T4: Execution jobs hire Micro-Jobs as children."""
        result = await svc.generate(saas_context())
        t3_ids = {j.id for j in result.jobs_at_tier(JobTier.EXECUTION)}
        t4_ids = {j.id for j in result.jobs_at_tier(JobTier.MICRO_JOB)}
        t3_to_t4 = [
            e for e in result.edges
            if e.parent_id in t3_ids and e.child_id in t4_ids
        ]
        assert len(t3_to_t4) > 0, "T3 Execution should HIRE T4 Micro-Jobs"

    @pytest.mark.asyncio
    async def test_t2_does_not_hire_t4_directly(self, svc):
        """T4 Micro-Jobs are children of T3, not T2."""
        result = await svc.generate(saas_context())
        t2_ids = {j.id for j in result.jobs_at_tier(JobTier.CORE_FUNCTIONAL)}
        t4_ids = {j.id for j in result.jobs_at_tier(JobTier.MICRO_JOB)}
        t2_to_t4 = [
            e for e in result.edges
            if e.parent_id in t2_ids and e.child_id in t4_ids
        ]
        assert len(t2_to_t4) == 0, "T4 Micro-Jobs must not be direct children of T2"

    @pytest.mark.asyncio
    async def test_t4_edges_have_full_strength(self, svc):
        """T3→T4 edges are functional and at full strength (1.0)."""
        result = await svc.generate(saas_context())
        t3_ids = {j.id for j in result.jobs_at_tier(JobTier.EXECUTION)}
        t4_ids = {j.id for j in result.jobs_at_tier(JobTier.MICRO_JOB)}
        for edge in result.edges:
            if edge.parent_id in t3_ids and edge.child_id in t4_ids:
                assert edge.strength == 1.0, "T3→T4 edges should have full strength"


# ─── Tree dict — functional spine includes T4 ────────────

class TestTreeDictFunctionalSpine:
    @pytest.mark.asyncio
    async def test_to_tree_dict_has_functional_and_experience_keys(self, svc):
        result = await svc.generate(saas_context())
        tree = result.to_tree_dict()
        assert "functional_spine" in tree
        assert "experience_dimension" in tree

    @pytest.mark.asyncio
    async def test_functional_spine_contains_all_four_tiers(self, svc):
        """T4 Micro-Jobs are part of the functional spine, not experience dimension."""
        result = await svc.generate(saas_context())
        tree = result.to_tree_dict()
        spine = tree["functional_spine"]
        spine_tiers = set()
        def collect(node):
            spine_tiers.add(node.get("tier"))
            for child in node.get("children", []):
                collect(child)
        for root_node in spine:
            collect(root_node)
        assert "T1_strategic" in spine_tiers
        assert "T2_core" in spine_tiers
        assert "T3_execution" in spine_tiers
        assert "T4_micro" in spine_tiers

    @pytest.mark.asyncio
    async def test_experience_dimension_is_empty_by_default(self, svc):
        """Experience dimension is populated from Dimension A nodes, not tier filtering."""
        result = await svc.generate(saas_context())
        tree = result.to_tree_dict()
        assert tree["experience_dimension"] == []


# ─── Executor type ──────────────────────────────────────

class TestExecutorType:
    @pytest.mark.asyncio
    async def test_all_jobs_have_non_null_executor_type(self, svc):
        """Every job should have a non-null executor_type after generation."""
        result = await svc.generate(saas_context())
        for job in result.jobs:
            assert job.executor_type is not None, (
                f"Job {job.id} ({job.tier.value}) has null executor_type"
            )
            assert job.executor_type in ("HUMAN", "AI"), (
                f"Job {job.id} has invalid executor_type: {job.executor_type!r}"
            )

    @pytest.mark.asyncio
    async def test_executor_type_persisted_to_graph(self, svc, graph):
        """executor_type should be stored in Neo4j entity properties."""
        result = await svc.generate(saas_context())
        for job in result.jobs:
            entity = graph._entities.get(job.id)
            assert entity is not None
            assert entity.properties.get("executor_type") in ("HUMAN", "AI"), (
                f"Job {job.id} missing executor_type in graph properties"
            )

    @pytest.mark.asyncio
    async def test_backward_compat_missing_executor_type_defaults_human(self, svc):
        """If a raw dict omits executor_type, it should default to HUMAN."""
        raw = {
            "strategic": [
                {"statement": "achieve growth", "rationale": "test", "metrics_hint": ["MRR"]}
            ],
            "core_functional": [],
            "execution": [],
            "micro_job": [],
        }
        ctx = HierarchyContext(domain="test")
        result = svc._build_hierarchy(raw, ctx)
        assert result.jobs[0].executor_type == "HUMAN"

    @pytest.mark.asyncio
    async def test_tree_dict_includes_executor_type(self, svc):
        """to_tree_dict() should include executor_type on each node."""
        result = await svc.generate(saas_context())
        tree = result.to_tree_dict()
        def check_node(node):
            assert "executor_type" in node, (
                f"Node {node.get('id')} missing executor_type in tree dict"
            )
            assert node["executor_type"] in ("HUMAN", "AI")
            for child in node.get("children", []):
                check_node(child)
        for root in tree["functional_spine"]:
            check_node(root)


# ─── Related jobs ────────────────────────────────────────

class TestRelatedJobs:
    @pytest.mark.asyncio
    async def test_related_jobs_in_result(self, svc):
        """Template should produce related_jobs in the result."""
        result = await svc.generate(saas_context())
        assert len(result.related_jobs) > 0

    @pytest.mark.asyncio
    async def test_related_jobs_are_t2_tier(self, svc):
        """Related jobs should have CORE_FUNCTIONAL tier."""
        result = await svc.generate(saas_context())
        for rj in result.related_jobs:
            assert rj.tier == JobTier.CORE_FUNCTIONAL

    @pytest.mark.asyncio
    async def test_related_jobs_have_related_category(self, svc):
        """Related jobs should have category 'related'."""
        result = await svc.generate(saas_context())
        for rj in result.related_jobs:
            assert rj.category == "related"

    @pytest.mark.asyncio
    async def test_related_jobs_persisted_to_graph(self, svc, graph):
        """Related jobs should be persisted as entities with is_related_job flag."""
        result = await svc.generate(saas_context())
        for rj in result.related_jobs:
            entity = graph._entities.get(rj.id)
            assert entity is not None, f"Related job {rj.id} not persisted"
            assert entity.properties.get("is_related_job") is True

    @pytest.mark.asyncio
    async def test_related_jobs_have_supports_edges(self, svc, graph):
        """Related jobs should have SUPPORTS edges to T2 jobs."""
        result = await svc.generate(saas_context())
        supports_edges = [
            e for e in graph._edges if e["edge_type"] == "SUPPORTS"
        ]
        assert len(supports_edges) > 0

    @pytest.mark.asyncio
    async def test_related_jobs_in_summary(self, svc):
        """Summary should include related_jobs count."""
        result = await svc.generate(saas_context())
        assert "related_jobs" in result.summary
        assert result.summary["related_jobs"] == len(result.related_jobs)

    @pytest.mark.asyncio
    async def test_related_jobs_in_tree_dict(self, svc):
        """to_tree_dict() should include related_jobs."""
        result = await svc.generate(saas_context())
        tree = result.to_tree_dict()
        assert "related_jobs" in tree
        assert len(tree["related_jobs"]) == len(result.related_jobs)


# ─── Consumption category ────────────────────────────────

class TestConsumptionCategory:
    @pytest.mark.asyncio
    async def test_consumption_jobs_generated(self, svc):
        """B2B SaaS template should include consumption category T3 jobs."""
        result = await svc.generate(saas_context())
        consumption_jobs = [
            j for j in result.jobs
            if j.tier == JobTier.EXECUTION and j.category == "consumption"
        ]
        assert len(consumption_jobs) > 0, "No consumption category T3 jobs found"

    @pytest.mark.asyncio
    async def test_consumption_count_in_summary(self, svc):
        """Summary should include T3_consumption count."""
        result = await svc.generate(saas_context())
        assert "T3_consumption" in result.summary
        assert result.summary["T3_consumption"] > 0
