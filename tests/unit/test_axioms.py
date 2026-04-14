"""Tests for the Eight Axioms in JobOSAxioms.

Covers:
- Axiom 1: Hierarchy (parent/child reference)
- Axiom 2: Imperfection inherent (entropy residual creation)
- Axiom 3 (a): Duality — completed Job can serve as Capability
- Axiom 3 (b): Contextual variance — HUMAN jobs require context
- Axiom 4: Singularity — at most one root job
- Axiom 5: Linguistic — functional AND experiential branches
- Axiom 6: root_token uniqueness per scope_id
- Axiom 7: Switch (boolean gate — delegate to switch_evaluator for full logic)
- Axiom 8: Market topology scaffold stub
"""
from __future__ import annotations

import pytest

from jobos.kernel.axioms import AxiomViolation, JobOSAxioms
from jobos.kernel.entity import EntityBase, EntityType


# ─── Helpers ─────────────────────────────────────────────

def make_job(
    job_id: str = "job_001",
    statement: str = "Define the scope",
    level: int = 0,
    parent_id: str | None = None,
    executor_type: str | None = None,
    root_token: str | None = None,
    scope_id: str = "scope_a",
    job_type: str = "core_functional",
    context_id: str | None = None,
    **extra_props,
) -> EntityBase:
    props: dict = {
        "level": level,
        "job_type": job_type,
        "scope_id": scope_id,
    }
    if parent_id:
        props["parent_id"] = parent_id
    if executor_type:
        props["executor_type"] = executor_type
    if root_token:
        props["root_token"] = root_token
    if context_id:
        props["context_id"] = context_id
    props.update(extra_props)
    return EntityBase(id=job_id, statement=statement, entity_type=EntityType.JOB, properties=props)


def make_imperfection(imp_id: str = "imp_001") -> EntityBase:
    return EntityBase(
        id=imp_id,
        statement="Some pain point exists",
        entity_type=EntityType.IMPERFECTION,
        properties={"severity": 0.5, "frequency": 0.3},
    )


# ─── Axiom 1: Hierarchy ──────────────────────────────────

class TestAxiom1Hierarchy:
    def test_valid_parent_child_returns_true(self):
        parent = make_job("parent_1", "Define goals")
        child = make_job("child_1", "Define sub-goals", level=1, parent_id="parent_1")
        result = JobOSAxioms.validate_hierarchy(child, parent)
        assert result is True

    def test_mismatched_parent_id_raises(self):
        parent = make_job("parent_x", "Define goals")
        child = make_job("child_y", "Define sub-goals", parent_id="wrong_id")
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_hierarchy(child, parent)
        assert exc_info.value.axiom == 1

    def test_non_job_child_raises(self):
        parent = make_job("parent_1", "Define goals")
        non_job = EntityBase(id="cap_1", statement="Capability", entity_type=EntityType.CAPABILITY)
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_hierarchy(non_job, parent)
        assert exc_info.value.axiom == 1

    def test_non_job_parent_raises(self):
        child = make_job("child_1", "Execute task", parent_id="cap_1")
        non_job = EntityBase(id="cap_1", statement="Capability", entity_type=EntityType.CAPABILITY)
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_hierarchy(child, non_job)
        assert exc_info.value.axiom == 1


# ─── Axiom 2: Imperfection ───────────────────────────────

class TestAxiom2Imperfection:
    def test_existing_imperfections_returned_unchanged(self):
        job = make_job()
        imp = make_imperfection()
        result = JobOSAxioms.validate_imperfection_inherent(job, [imp])
        assert result == [imp]

    def test_empty_imperfections_creates_entropy_residual(self):
        job = make_job()
        result = JobOSAxioms.validate_imperfection_inherent(job, [])
        assert len(result) == 1
        assert result[0].entity_type == EntityType.IMPERFECTION
        assert "entropy" in result[0].name.lower()
        assert result[0].properties["entropy_risk"] == 0.3

    def test_non_job_entity_raises(self):
        non_job = EntityBase(id="cap_1", statement="Capability", entity_type=EntityType.CAPABILITY)
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_imperfection_inherent(non_job, [])
        assert exc_info.value.axiom == 2


# ─── Axiom 3a: Duality ───────────────────────────────────

class TestAxiom3Duality:
    def test_completed_job_returns_true(self):
        completed = make_job("j1", "Define the scope")
        completed.status = "completed"
        higher = make_job("j2", "Achieve the goal")
        assert JobOSAxioms.validate_duality(completed, higher) is True

    def test_resolved_job_returns_true(self):
        resolved = make_job("j1", "Define the scope")
        resolved.status = "resolved"
        higher = make_job("j2", "Achieve the goal")
        assert JobOSAxioms.validate_duality(resolved, higher) is True

    def test_active_job_raises_axiom_3(self):
        active = make_job("j1", "Define the scope")
        active.status = "active"
        higher = make_job("j2", "Achieve the goal")
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_duality(active, higher)
        assert exc_info.value.axiom == 3
        assert "active" in exc_info.value.description

    def test_non_job_entity_raises_axiom_3(self):
        cap = EntityBase(id="cap_1", statement="A capability", entity_type=EntityType.CAPABILITY)
        cap.status = "completed"
        higher = make_job("j2", "Achieve the goal")
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_duality(cap, higher)
        assert exc_info.value.axiom == 3


# ─── Axiom 3b: Contextual Variance ───────────────────────

class TestAxiom3ContextualVariance:
    def test_human_job_with_context_id_passes(self):
        job = make_job(executor_type="HUMAN", context_id="ctx_001")
        assert JobOSAxioms.validate_contextual_variance(job) is True

    def test_human_job_with_who_field_passes(self):
        job = make_job(executor_type="HUMAN", who="sales rep")
        assert JobOSAxioms.validate_contextual_variance(job) is True

    def test_human_job_without_context_raises_axiom_3(self):
        job = make_job(executor_type="HUMAN")
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_contextual_variance(job)
        assert exc_info.value.axiom == 3
        assert "HUMAN" in exc_info.value.description

    def test_ai_job_without_context_passes(self):
        job = make_job(executor_type="AI")
        assert JobOSAxioms.validate_contextual_variance(job) is True

    def test_unset_executor_type_passes(self):
        job = make_job()  # executor_type not set
        assert JobOSAxioms.validate_contextual_variance(job) is True


# ─── Axiom 4: Singularity ───────────────────────────────

class TestAxiom4Singularity:
    def test_single_root_passes(self):
        root = make_job("root_1", "Achieve growth")
        child = make_job("child_1", "Define metrics", level=1, parent_id="root_1")
        assert JobOSAxioms.validate_singularity([root, child]) is True

    def test_no_jobs_passes(self):
        assert JobOSAxioms.validate_singularity([]) is True

    def test_multiple_root_jobs_raises(self):
        root1 = make_job("root_1", "Achieve growth")
        root2 = make_job("root_2", "Drive revenue")
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_singularity([root1, root2])
        assert exc_info.value.axiom == 4

    def test_two_non_root_jobs_passes(self):
        j1 = make_job("j1", "Define scope", level=1, parent_id="p1")
        j2 = make_job("j2", "Execute plan", level=1, parent_id="p1")
        assert JobOSAxioms.validate_singularity([j1, j2]) is True


# ─── Axiom 5: Linguistic ─────────────────────────────────

class TestAxiom5Linguistic:
    # Functional (experiential=False)
    def test_valid_action_verb_returns_true(self):
        assert JobOSAxioms.validate_linguistic_structure("Define success criteria") is True

    def test_invalid_verb_raises(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("Success is everything")
        assert exc_info.value.axiom == 5

    def test_empty_statement_raises(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("")
        assert exc_info.value.axiom == 5

    def test_whitespace_only_raises(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("   ")
        assert exc_info.value.axiom == 5

    def test_multiple_valid_verbs(self):
        statements = [
            "Build the feature",
            "Deploy the service",
            "Analyze customer data",
            "Measure impact",
            "Optimize the pipeline",
        ]
        for stmt in statements:
            assert JobOSAxioms.validate_linguistic_structure(stmt) is True

    # Experiential (experiential=True)
    def test_to_be_prefix_valid_experiential(self):
        assert JobOSAxioms.validate_linguistic_structure(
            "To Be seen as a trusted advisor", experiential=True
        ) is True

    def test_feel_prefix_valid_experiential(self):
        assert JobOSAxioms.validate_linguistic_structure(
            "Feel confident in production deploys", experiential=True
        ) is True

    def test_lowercase_feel_valid_experiential(self):
        assert JobOSAxioms.validate_linguistic_structure(
            "feel connected to the mission", experiential=True
        ) is True

    def test_functional_verb_rejected_as_experiential(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("Define confidence", experiential=True)
        assert exc_info.value.axiom == 5
        assert "To Be" in exc_info.value.description or "Feel" in exc_info.value.description

    def test_empty_experiential_raises(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("", experiential=True)
        assert exc_info.value.axiom == 5


# ─── Axiom 6: root_token Singularity ────────────────────

class TestAxiom6RootToken:
    def test_single_root_per_scope_passes(self):
        root = make_job("root_1", root_token="ROOT", scope_id="scope_a")
        child = make_job("child_1", level=1, scope_id="scope_a")
        assert JobOSAxioms.validate_root_token([root, child], "scope_a") is True

    def test_two_roots_same_scope_raises(self):
        root1 = make_job("root_1", root_token="ROOT", scope_id="scope_a")
        root2 = make_job("root_2", root_token="ROOT", scope_id="scope_a")
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_root_token([root1, root2], "scope_a")
        assert exc_info.value.axiom == 6
        assert "scope_a" in exc_info.value.description

    def test_two_roots_different_scopes_passes(self):
        root1 = make_job("root_1", root_token="ROOT", scope_id="scope_a")
        root2 = make_job("root_2", root_token="ROOT", scope_id="scope_b")
        # For scope_a: only root1 has scope_a — passes
        assert JobOSAxioms.validate_root_token([root1, root2], "scope_a") is True
        # For scope_b: only root2 has scope_b — passes
        assert JobOSAxioms.validate_root_token([root1, root2], "scope_b") is True

    def test_no_roots_passes(self):
        j1 = make_job("j1", scope_id="scope_a")
        assert JobOSAxioms.validate_root_token([j1], "scope_a") is True

    def test_empty_list_passes(self):
        assert JobOSAxioms.validate_root_token([], "scope_a") is True


# ─── Axiom 7: Switch ─────────────────────────────────────

class TestAxiom7Switch:
    def test_both_false_returns_false(self):
        assert JobOSAxioms.validate_switch(False, False) is False

    def test_context_changed_returns_true(self):
        assert JobOSAxioms.validate_switch(True, False) is True

    def test_metric_breached_returns_true(self):
        assert JobOSAxioms.validate_switch(False, True) is True

    def test_both_true_returns_true(self):
        assert JobOSAxioms.validate_switch(True, True) is True


# ─── Axiom 8: Market Topology Scaffold ──────────────────

class TestAxiom8MarketTopology:
    def test_returns_list(self):
        jobs = [make_job("j1"), make_job("j2"), make_job("j3")]
        result = JobOSAxioms.discover_market_clusters(jobs)
        assert isinstance(result, list)

    def test_empty_jobs_returns_empty(self):
        result = JobOSAxioms.discover_market_clusters([])
        assert result == []

    def test_cluster_has_required_keys(self):
        jobs = [make_job("j1"), make_job("j2")]
        result = JobOSAxioms.discover_market_clusters(jobs)
        assert len(result) >= 1
        cluster = result[0]
        assert "cluster_id" in cluster
        assert "job_ids" in cluster
        assert "pattern" in cluster

    def test_all_job_ids_present_in_stub_cluster(self):
        jobs = [make_job("j1"), make_job("j2"), make_job("j3")]
        result = JobOSAxioms.discover_market_clusters(jobs)
        all_ids = {jid for c in result for jid in c["job_ids"]}
        assert "j1" in all_ids
        assert "j2" in all_ids
        assert "j3" in all_ids

    def test_non_job_entities_excluded(self):
        jobs = [make_job("j1")]
        cap = EntityBase(id="cap_1", statement="Some capability", entity_type=EntityType.CAPABILITY)
        result = JobOSAxioms.discover_market_clusters([*jobs, cap])
        all_ids = {jid for c in result for jid in c["job_ids"]}
        assert "j1" in all_ids
        assert "cap_1" not in all_ids


# ─── validate_all integration ───────────────────────────

class TestValidateAll:
    def test_valid_job_returns_all_true(self):
        job = make_job("j1", statement="Define the scope")
        results = JobOSAxioms.validate_all(job, [make_imperfection()])
        assert results["axiom_1_hierarchy"] is None  # no parent
        assert isinstance(results["axiom_2_imperfections"], list)
        assert results["axiom_3_contextual_variance"] is True
        assert results["axiom_4_singularity"] is None  # no all_jobs
        assert results["axiom_5_linguistic"] is True
        assert results["axiom_6_root_token"] is None  # no scope_id

    def test_invalid_linguistic_captured_in_results(self):
        job = make_job("j1", statement="Success is defined")
        results = JobOSAxioms.validate_all(job, [make_imperfection()])
        assert isinstance(results["axiom_5_linguistic"], str)
        assert "Axiom 5" in results["axiom_5_linguistic"]

    def test_validate_all_with_all_jobs_checks_axiom_4(self):
        root = make_job("root_1", "Achieve growth")
        child = make_job("child_1", "Define metrics", level=1, parent_id="root_1")
        results = JobOSAxioms.validate_all(root, [], all_jobs=[root, child])
        assert results["axiom_4_singularity"] is True

    def test_validate_all_with_multiple_roots_fails_axiom_4(self):
        root1 = make_job("root_1", "Achieve growth")
        root2 = make_job("root_2", "Drive revenue")
        results = JobOSAxioms.validate_all(root1, [], all_jobs=[root1, root2])
        assert isinstance(results["axiom_4_singularity"], str)
        assert "Axiom 4" in results["axiom_4_singularity"]

    def test_validate_all_with_scope_id_checks_axiom_6(self):
        root = make_job("root_1", root_token="ROOT", scope_id="scope_a")
        results = JobOSAxioms.validate_all(
            root, [], all_jobs=[root], scope_id="scope_a"
        )
        assert results["axiom_6_root_token"] is True

    def test_validate_all_with_duplicate_root_token_fails_axiom_6(self):
        root1 = make_job("root_1", root_token="ROOT", scope_id="scope_a")
        root2 = make_job("root_2", root_token="ROOT", scope_id="scope_a")
        results = JobOSAxioms.validate_all(
            root1, [], all_jobs=[root1, root2], scope_id="scope_a"
        )
        assert isinstance(results["axiom_6_root_token"], str)
        assert "Axiom 6" in results["axiom_6_root_token"]
