"""Tests for Market Topology (Axiom 8) clustering.

Covers:
- discover_market_clusters: groups jobs by dominant imperfection dimension
- compute_vfe_vector: VFE vector computation from imperfections
- Edge cases: no jobs, no imperfections, single job
"""
from __future__ import annotations

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.market_topology import (
    compute_vfe_vector,
    discover_market_clusters,
)


def make_job(job_id: str = "j1") -> EntityBase:
    return EntityBase(
        id=job_id, statement="Test job",
        entity_type=EntityType.JOB, properties={"level": 0},
    )


def make_imp(
    imp_id: str = "i1",
    severity: float = 0.5,
    frequency: float = 0.3,
    entropy_risk: float = 0.1,
    fixability: float = 0.8,
    is_blocker: bool = False,
) -> EntityBase:
    return EntityBase(
        id=imp_id, statement="Imperfection",
        entity_type=EntityType.IMPERFECTION,
        properties={
            "severity": severity,
            "frequency": frequency,
            "entropy_risk": entropy_risk,
            "fixability": fixability,
            "is_blocker": is_blocker,
        },
    )


class TestComputeVFEVector:
    def test_no_imperfections_returns_zero(self):
        job = make_job()
        vec = compute_vfe_vector(job, [])
        assert vec["vfe_total"] == 0.0
        assert vec["blocker_count"] == 0

    def test_single_imperfection(self):
        job = make_job()
        imp = make_imp(severity=0.8, frequency=0.5, entropy_risk=0.2, fixability=0.6)
        vec = compute_vfe_vector(job, [imp])
        assert vec["vfe_total"] > 0
        assert vec["severity_mean"] == 0.8
        assert vec["frequency_mean"] == 0.5

    def test_blocker_weighted_heavily(self):
        job = make_job()
        blocker = make_imp(is_blocker=True, severity=0.5)
        non_blocker = make_imp(imp_id="i2", is_blocker=False, severity=0.5)
        vec_b = compute_vfe_vector(job, [blocker])
        vec_nb = compute_vfe_vector(job, [non_blocker])
        assert vec_b["vfe_total"] > vec_nb["vfe_total"]

    def test_multiple_imperfections_averaged(self):
        job = make_job()
        imps = [
            make_imp("i1", severity=0.2),
            make_imp("i2", severity=0.8),
        ]
        vec = compute_vfe_vector(job, imps)
        assert abs(vec["severity_mean"] - 0.5) < 1e-4


class TestDiscoverMarketClusters:
    def test_no_jobs_returns_empty(self):
        assert discover_market_clusters([]) == []

    def test_non_job_entities_excluded(self):
        cap = EntityBase(
            id="c1", statement="Cap", entity_type=EntityType.CAPABILITY,
        )
        assert discover_market_clusters([cap]) == []

    def test_single_job_no_imperfections(self):
        job = make_job()
        clusters = discover_market_clusters([job])
        assert len(clusters) == 1
        assert clusters[0]["size"] == 1
        assert clusters[0]["job_ids"] == ["j1"]
        assert "no measured imperfections" in clusters[0]["pattern"].lower()

    def test_jobs_with_same_dominant_dimension_cluster_together(self):
        j1 = make_job("j1")
        j2 = make_job("j2")
        # Both have high severity as dominant dimension
        imp_map = {
            "j1": [make_imp("i1", severity=0.9, frequency=0.1)],
            "j2": [make_imp("i2", severity=0.8, frequency=0.1)],
        }
        clusters = discover_market_clusters([j1, j2], imp_map)
        # Both should end up in the same cluster (severity-dominated)
        assert any(c["size"] == 2 for c in clusters)

    def test_jobs_with_different_dimensions_split(self):
        j1 = make_job("j1")
        j2 = make_job("j2")
        # j1: high severity, j2: high frequency
        imp_map = {
            "j1": [make_imp("i1", severity=0.9, frequency=0.0, fixability=1.0, entropy_risk=0.0)],
            "j2": [make_imp("i2", severity=0.0, frequency=0.9, fixability=1.0, entropy_risk=0.0)],
        }
        clusters = discover_market_clusters([j1, j2], imp_map)
        assert len(clusters) == 2
        assert all(c["size"] == 1 for c in clusters)

    def test_clusters_have_centroids(self):
        j1 = make_job("j1")
        imp_map = {"j1": [make_imp("i1", severity=0.5)]}
        clusters = discover_market_clusters([j1], imp_map)
        assert clusters[0]["centroid"] is not None
        assert "vfe_total" in clusters[0]["centroid"]

    def test_cluster_pattern_is_human_readable(self):
        j1 = make_job("j1")
        imp_map = {"j1": [make_imp("i1", severity=0.9)]}
        clusters = discover_market_clusters([j1], imp_map)
        assert len(clusters[0]["pattern"]) > 10

    def test_blocker_dominated_jobs(self):
        j1 = make_job("j1")
        imp_map = {"j1": [make_imp("i1", is_blocker=True, severity=0.1)]}
        clusters = discover_market_clusters([j1], imp_map)
        assert "blocker" in clusters[0]["pattern"].lower() or "impediment" in clusters[0]["pattern"].lower()
