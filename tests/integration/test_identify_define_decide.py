"""Quick integration test: Identify → Define → Decide loop.

Exercises the full Phase 1→2→3 workflow with both HUMAN and AI
executor jobs, verifying:
  - Hierarchy generation with executor_type, related jobs, consumption chain
  - Dimension A (Experience) gated by executor_type
  - Dimension B (Metrics) with conditional switch thresholds
  - Preliminary recommendation uses executor_type-aware factors
  - Backward compatibility (missing executor_type → HUMAN default)
"""
from __future__ import annotations

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.hierarchy import (
    HierarchyContext,
    HierarchyResult,
    HierarchyJob,
    JobTier,
    ExecutionCategory,
    CONSUMPTION_CHAIN_STEPS,
)
from jobos.kernel.job_statement import validate_verb
from jobos.services.hierarchy_service import HierarchyService
from jobos.services.experience_service import ExperienceService


# ─── Lightweight fakes (no Neo4j / PostgreSQL needed) ─────

class FakeGraph:
    def __init__(self):
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []

    async def save_entity(self, entity):
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, eid):
        return self._entities.get(eid)

    async def delete_entity(self, eid):
        return self._entities.pop(eid, None) is not None

    async def list_entities(self, entity_type=None, status=None, limit=100, offset=0):
        r = list(self._entities.values())
        if entity_type:
            r = [e for e in r if e.entity_type.value == entity_type]
        return r[offset:offset + limit]

    async def create_edge(self, source_id, target_id, edge_type, properties=None):
        self._edges.append({
            "source_id": source_id, "target_id": target_id,
            "edge_type": edge_type, "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id, target_id, edge_type):
        return False

    async def get_neighbors(self, eid, edge_type=None, direction="outgoing"):
        if direction == "outgoing":
            ids = [e["target_id"] for e in self._edges
                   if e["source_id"] == eid
                   and (edge_type is None or e["edge_type"] == edge_type)]
        else:
            ids = [e["source_id"] for e in self._edges
                   if e["target_id"] == eid
                   and (edge_type is None or e["edge_type"] == edge_type)]
        return [self._entities[i] for i in ids if i in self._entities]

    async def get_edges(self, eid, edge_type=None, direction="outgoing"):
        return []

    async def get_job_subgraph(self, job_id, depth=3):
        return {}

    async def add_label(self, eid, label):
        return True

    async def ensure_schema(self):
        return 0

    async def verify_connectivity(self):
        return True


class FakeDB:
    def __init__(self):
        self._metrics: list[dict] = []
        self._versions: list[dict] = []

    async def save_metric_reading(self, r): return r.id
    async def get_metric_readings(self, mid, limit=100, since=None): return []
    async def get_latest_reading(self, mid): return None
    async def save_vfe_reading(self, r): return r.id
    async def get_vfe_history(self, jid, limit=50): return []
    async def save_hiring_event(self, e): return e.id
    async def get_hiring_events(self, **kw): return []
    async def save_experiment(self, e): return e.id
    async def get_experiments(self, **kw): return []

    async def insert_job_metric(self, job_id, metrics, bounds, **kw):
        self._metrics.append({"job_id": job_id, "metrics": metrics, "bounds": bounds})
        return f"mid_{job_id}"

    async def get_job_metrics(self, jid, limit=50): return []
    async def verify_connectivity(self): return True

    async def save_experience_version(self, job_id, version, markers,
                                       source, confidence=None, created_by=None):
        rec = {"job_id": job_id, "version": version, "markers": markers,
               "source": source, "confidence": confidence}
        self._versions.append(rec)
        return f"ev_{len(self._versions)}"

    async def get_experience_history(self, jid, limit=50):
        h = [r for r in self._versions if r["job_id"] == jid]
        h.sort(key=lambda r: r["version"], reverse=True)
        return h[:limit]

    async def save_baseline_snapshot(self, *a, **kw): return "bs"
    async def get_baseline_snapshot(self, *a, **kw): return None
    async def save_switch_event(self, *a, **kw): return "se"
    async def get_switch_events(self, *a, **kw): return []


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def graph():
    return FakeGraph()


@pytest.fixture
def db():
    return FakeDB()


@pytest.fixture
def hierarchy_svc(graph, db):
    return HierarchyService(graph=graph, db=db)


@pytest.fixture
def experience_svc(graph, db):
    return ExperienceService(graph=graph, db=db)


# ═══════════════════════════════════════════════════════════
#  PHASE 1 — IDENTIFY
# ═══════════════════════════════════════════════════════════

class TestPhase1Identify:
    """Generate a hierarchy, verify structure, executor types, and new features."""

    @pytest.mark.asyncio
    async def test_full_hierarchy_generated(self, hierarchy_svc):
        ctx = HierarchyContext(domain="b2b_saas", keywords=["saas"])
        result = await hierarchy_svc.generate(ctx)

        # All 4 tiers present
        tiers = {j.tier for j in result.jobs}
        assert tiers == {
            JobTier.STRATEGIC, JobTier.CORE_FUNCTIONAL,
            JobTier.EXECUTION, JobTier.MICRO_JOB,
        }

    @pytest.mark.asyncio
    async def test_every_job_has_executor_type(self, hierarchy_svc):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        for job in result.jobs:
            assert job.executor_type in ("HUMAN", "AI"), (
                f"{job.statement!r} missing executor_type"
            )

    @pytest.mark.asyncio
    async def test_mix_of_human_and_ai_jobs(self, hierarchy_svc):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        types = {j.executor_type for j in result.jobs}
        assert "HUMAN" in types, "Expected at least one HUMAN job"
        assert "AI" in types, "Expected at least one AI job"

    @pytest.mark.asyncio
    async def test_consumption_chain_jobs_exist(self, hierarchy_svc):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        consumption = [
            j for j in result.jobs
            if j.tier == JobTier.EXECUTION and j.category == "consumption"
        ]
        assert len(consumption) >= 1

    @pytest.mark.asyncio
    async def test_related_jobs_generated(self, hierarchy_svc):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        assert len(result.related_jobs) >= 2
        for rj in result.related_jobs:
            assert rj.category == "related"
            assert rj.tier == JobTier.CORE_FUNCTIONAL

    @pytest.mark.asyncio
    async def test_related_jobs_have_supports_edges(self, hierarchy_svc, graph):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        supports = [e for e in graph._edges if e["edge_type"] == "SUPPORTS"]
        t2_ids = {j.id for j in result.jobs if j.tier == JobTier.CORE_FUNCTIONAL}
        for edge in supports:
            assert edge["target_id"] in t2_ids

    @pytest.mark.asyncio
    async def test_executor_type_in_tree_dict(self, hierarchy_svc):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        tree = result.to_tree_dict()

        def walk(node):
            assert "executor_type" in node
            assert node["executor_type"] in ("HUMAN", "AI")
            for child in node.get("children", []):
                walk(child)

        for root in tree["functional_spine"]:
            walk(root)
        for rj in tree["related_jobs"]:
            assert rj["executor_type"] in ("HUMAN", "AI")

    @pytest.mark.asyncio
    async def test_executor_type_persisted_to_neo4j(self, hierarchy_svc, graph):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        for job in result.jobs:
            entity = graph._entities[job.id]
            assert entity.properties["executor_type"] == job.executor_type


# ═══════════════════════════════════════════════════════════
#  PHASE 2 — DEFINE (Dimension A + B)
# ═══════════════════════════════════════════════════════════

class TestPhase2Define:
    """Lock a target job, verify dimension routing by executor_type."""

    # ── Dimension A: Experience (HUMAN only) ──────────────

    @pytest.mark.asyncio
    async def test_human_job_gets_experience_markers(
        self, hierarchy_svc, experience_svc, graph,
    ):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        human_job = next(
            j for j in result.jobs if j.executor_type == "HUMAN"
        )
        exp = await experience_svc.generate(job_id=human_job.id)
        assert len(exp["markers"]["feel_markers"]) > 0
        assert len(exp["markers"]["to_be_markers"]) > 0

    @pytest.mark.asyncio
    async def test_ai_job_blocked_from_experience(
        self, hierarchy_svc, experience_svc, graph,
    ):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        ai_job = next(j for j in result.jobs if j.executor_type == "AI")

        with pytest.raises(ValueError, match="not applicable to AI"):
            await experience_svc.generate(job_id=ai_job.id)

    @pytest.mark.asyncio
    async def test_ai_job_blocked_from_experience_edit(
        self, hierarchy_svc, experience_svc, graph,
    ):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        ai_job = next(j for j in result.jobs if j.executor_type == "AI")

        with pytest.raises(ValueError, match="not applicable to AI"):
            await experience_svc.edit(
                job_id=ai_job.id,
                markers={"feel_markers": ["Feel empowered"], "to_be_markers": []},
            )

    # ── Dimension B: Metrics (both HUMAN and AI) ─────────

    @pytest.mark.asyncio
    async def test_all_jobs_get_metrics_scaffold(
        self, hierarchy_svc, db,
    ):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        scaffolded_ids = {m["job_id"] for m in db._metrics}
        # T2, T3, T4 all get metrics (T1 does not)
        for job in result.jobs:
            if job.tier != JobTier.STRATEGIC:
                assert job.id in scaffolded_ids, (
                    f"Missing metrics scaffold for {job.tier.value} job"
                )


# ═══════════════════════════════════════════════════════════
#  PHASE 3 — DECIDE (Recommendation heuristic)
# ═══════════════════════════════════════════════════════════

class TestPhase3Decide:
    """Verify the heuristic recommendation is executor_type-aware."""

    @pytest.mark.asyncio
    async def test_ai_execution_job_favors_switch(self, hierarchy_svc, graph):
        """An AI-designated T3 job with metrics should lean toward switch_to_ai."""
        from jobos.api.routes.recommendation import (
            _template_recommendation, RecommendationRequest, OutcomesIn,
        )
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        ai_job = next(
            j for j in result.jobs
            if j.executor_type == "AI" and j.tier == JobTier.EXECUTION
        )
        entity = graph._entities[ai_job.id]
        # Patch "tier" key to match what recommendation route reads
        entity.properties["tier"] = entity.properties["hierarchy_tier"]

        req = RecommendationRequest(
            job_id=ai_job.id,
            outcomes=OutcomesIn(
                metrics=[{"statement": "Minimize time to detect", "target": "< 1 min"}],
            ),
        )
        resp = _template_recommendation(req, entity, [])

        # Should lean positive (AI + low tier + metrics)
        pos = sum(f.weight for f in resp.factors if f.impact == "positive")
        neg = sum(f.weight for f in resp.factors if f.impact == "negative")
        assert pos > neg, "AI execution job should lean toward switch"
        assert resp.recommendation == "switch_to_ai"

    @pytest.mark.asyncio
    async def test_human_strategic_job_favors_keep(self, hierarchy_svc, graph):
        """A HUMAN T1 job with experience markers should lean toward keep_human."""
        from jobos.api.routes.recommendation import (
            _template_recommendation, RecommendationRequest, OutcomesIn,
        )
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        human_t1 = next(
            j for j in result.jobs
            if j.executor_type == "HUMAN" and j.tier == JobTier.STRATEGIC
        )
        entity = graph._entities[human_t1.id]
        # Patch "tier" key to match what recommendation route reads
        # (persisted as "hierarchy_tier"; recommendation reads "tier")
        entity.properties["tier"] = entity.properties["hierarchy_tier"]

        req = RecommendationRequest(
            job_id=human_t1.id,
            outcomes=OutcomesIn(
                experience_markers={
                    "feel_markers": ["Feel confident in strategic direction"],
                    "to_be_markers": ["To be seen as visionary leader"],
                },
                metrics=[{"statement": "Increase PMF score", "target": "> 0.4"}],
            ),
        )
        resp = _template_recommendation(req, entity, [])

        neg = sum(f.weight for f in resp.factors if f.impact == "negative")
        pos = sum(f.weight for f in resp.factors if f.impact == "positive")
        assert neg > pos, "Strategic HUMAN job should lean toward keep"
        assert resp.recommendation == "keep_human"


# ═══════════════════════════════════════════════════════════
#  BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Jobs without executor_type should default to HUMAN."""

    @pytest.mark.asyncio
    async def test_missing_executor_type_defaults_human(self, hierarchy_svc):
        raw = {
            "strategic": [
                {"statement": "achieve growth", "rationale": "", "metrics_hint": []},
            ],
            "core_functional": [
                {"statement": "reduce cost", "rationale": "", "metrics_hint": []},
            ],
            "execution": [],
            "micro_job": [],
        }
        ctx = HierarchyContext(domain="legacy")
        result = hierarchy_svc._build_hierarchy(raw, ctx)
        for job in result.jobs:
            assert job.executor_type == "HUMAN"

    @pytest.mark.asyncio
    async def test_empty_related_jobs_no_error(self, hierarchy_svc, graph):
        raw = {
            "strategic": [
                {"statement": "achieve growth", "rationale": "", "metrics_hint": []},
            ],
            "core_functional": [],
            "execution": [],
            "micro_job": [],
        }
        ctx = HierarchyContext(domain="minimal")
        result = hierarchy_svc._build_hierarchy(raw, ctx)
        assert result.related_jobs == []
        tree = result.to_tree_dict()
        assert tree["related_jobs"] == []


# ═══════════════════════════════════════════════════════════
#  CONSUMPTION CHAIN
# ═══════════════════════════════════════════════════════════

class TestConsumptionChain:
    """Verify the consumption chain constant and jobs."""

    def test_chain_has_seven_steps(self):
        assert len(CONSUMPTION_CHAIN_STEPS) == 7
        assert CONSUMPTION_CHAIN_STEPS[0] == "Purchase"
        assert CONSUMPTION_CHAIN_STEPS[-1] == "Upgrade/Dispose"

    def test_consumption_is_valid_execution_category(self):
        assert ExecutionCategory.CONSUMPTION.value == "consumption"

    @pytest.mark.asyncio
    async def test_consumption_jobs_have_action_verbs(self, hierarchy_svc):
        result = await hierarchy_svc.generate(
            HierarchyContext(domain="b2b_saas"),
        )
        for job in result.jobs:
            if job.category == "consumption":
                assert validate_verb(job.statement), (
                    f"Consumption job fails Axiom 5: {job.statement!r}"
                )
