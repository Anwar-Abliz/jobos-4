"""JobOS 4.0 — Market Topology Scaffold (Axiom 8).

Axiom 8: "Jobs cluster by unmet outcome patterns — this is the market."

Phase 1 (current): Function signatures only. Returns a stub cluster.
Phase 2: KMeans clustering on VFE vectors from Dimension B (job_metrics table).
Phase 3: Graph community detection on imperfection co-occurrence in Neo4j.

Architectural intent: The Market Topology engine eventually enables JobOS to
discover distinct customer segments by grouping Jobs with similar unresolved
Imperfections. Jobs in the same cluster likely share the same underserved
outcome — a product opportunity.

Grounding: Ulwick's "Outcome-Driven Innovation" § Market Segmentation,
           and Moesta's "Demand-Side Sales" § Forces of Progress.
"""
from __future__ import annotations

from typing import Any

from jobos.kernel.entity import EntityBase, EntityType


# ─── Cluster Result Type ─────────────────────────────────

def discover_market_clusters(
    jobs: list[EntityBase],
    imperfection_map: dict[str, list[EntityBase]] | None = None,
) -> list[dict[str, Any]]:
    """Axiom 8: Discover market clusters from unmet outcome patterns.

    Args:
        jobs:             All Job entities to analyze.
        imperfection_map: job_id -> list of Imperfection entities associated with it.
                          If None, clustering is done without imperfection context.

    Returns:
        List of cluster dicts. Each cluster has:
            cluster_id:   Unique cluster identifier.
            job_ids:      List of job entity IDs in this cluster.
            pattern:      Human-readable description of the shared outcome pattern.
            centroid:     VFE vector centroid (mean of per-job VFE vectors).
            size:         Number of jobs in this cluster.

    Phase 1: VFE-vector-based clustering using simple distance grouping.
             Groups jobs by dominant imperfection dimension (highest VFE component).
    Phase 2: KMeans on normalized VFE vectors.
    Phase 3: Louvain community detection on imperfection co-occurrence graph.
    """
    job_ids = [j.id for j in jobs if j.entity_type == EntityType.JOB]
    if not job_ids:
        return []

    imp_map = imperfection_map or {}

    # Compute VFE vectors for all jobs
    vectors: dict[str, dict[str, float]] = {}
    for job in jobs:
        if job.entity_type != EntityType.JOB:
            continue
        imps = imp_map.get(job.id, [])
        vectors[job.id] = compute_vfe_vector(job, imps)

    # Group by dominant imperfection dimension
    dimension_groups: dict[str, list[str]] = {}
    for job_id, vec in vectors.items():
        dominant = _dominant_dimension(vec)
        dimension_groups.setdefault(dominant, []).append(job_id)

    clusters: list[dict[str, Any]] = []
    for idx, (dimension, jids) in enumerate(sorted(dimension_groups.items())):
        # Compute centroid for this cluster
        centroid = _compute_centroid([vectors[jid] for jid in jids])
        clusters.append({
            "cluster_id": f"cluster_{idx}",
            "job_ids": jids,
            "pattern": _dimension_to_pattern(dimension),
            "centroid": centroid,
            "size": len(jids),
        })

    return clusters


_DIMENSION_PATTERNS: dict[str, str] = {
    "blocker": "Jobs blocked by critical impediments requiring immediate resolution",
    "severity": "Jobs with high-severity imperfections degrading outcomes",
    "frequency": "Jobs with frequently recurring imperfections (high friction)",
    "entropy_risk": "Jobs with high entropy risk (unpredictable failure modes)",
    "fixability": "Jobs with low fixability (systemic/structural issues)",
    "none": "Jobs with no measured imperfections (potentially underspecified)",
}


def _dominant_dimension(vec: dict[str, float]) -> str:
    """Determine which imperfection dimension dominates a VFE vector."""
    if vec.get("vfe_total", 0.0) == 0.0:
        return "none"

    dimension_scores = {
        "blocker": vec.get("blocker_count", 0) * 3.0,
        "severity": vec.get("severity_mean", 0.0) * 2.0,
        "frequency": vec.get("frequency_mean", 0.0),
        "entropy_risk": vec.get("entropy_risk_mean", 0.0),
        "fixability": 1.0 - vec.get("fixability_mean", 1.0),
    }
    return max(dimension_scores, key=lambda k: dimension_scores[k])


def _dimension_to_pattern(dimension: str) -> str:
    """Map a dominant dimension to a human-readable pattern description."""
    return _DIMENSION_PATTERNS.get(dimension, f"Shared {dimension} pattern")


def _compute_centroid(vectors: list[dict[str, float]]) -> dict[str, float]:
    """Compute the mean VFE vector for a cluster."""
    if not vectors:
        return {}
    keys = ["vfe_total", "blocker_count", "severity_mean",
            "frequency_mean", "entropy_risk_mean", "fixability_mean"]
    centroid: dict[str, float] = {}
    for key in keys:
        vals = [v.get(key, 0.0) for v in vectors]
        centroid[key] = round(sum(vals) / len(vals), 4)
    return centroid


def compute_vfe_vector(
    job: EntityBase,
    imperfections: list[EntityBase],
) -> dict[str, float]:
    """Compute the VFE (Variational Free Energy) vector for a Job.

    VFE formula (equivalent to legacy IPS):
        VFE = 3*Blocker + 2*Severity + Frequency + EntropyRisk + (1 - Fixability)

    Phase 1: Returns aggregate VFE. Phase 2: Returns per-imperfection vectors
    suitable for KMeans clustering.

    Args:
        job:           The Job entity.
        imperfections: List of Imperfection entities linked to this job.

    Returns:
        Dict with 'vfe_total', 'blocker_count', 'severity_mean',
        'frequency_mean', 'entropy_risk_mean', 'fixability_mean'.
    """
    if not imperfections:
        return {
            "vfe_total": 0.0,
            "blocker_count": 0,
            "severity_mean": 0.0,
            "frequency_mean": 0.0,
            "entropy_risk_mean": 0.0,
            "fixability_mean": 1.0,
        }

    blocker_count = sum(
        1 for i in imperfections if i.properties.get("is_blocker", False)
    )
    severity_mean = (
        sum(i.properties.get("severity", 0.0) for i in imperfections)
        / len(imperfections)
    )
    frequency_mean = (
        sum(i.properties.get("frequency", 0.0) for i in imperfections)
        / len(imperfections)
    )
    entropy_risk_mean = sum(
        i.properties.get("entropy_risk", 0.0) for i in imperfections
    ) / len(imperfections)
    fixability_mean = sum(
        i.properties.get("fixability", 1.0) for i in imperfections
    ) / len(imperfections)

    vfe_total = (
        3 * blocker_count
        + 2 * severity_mean
        + frequency_mean
        + entropy_risk_mean
        + (1 - fixability_mean)
    )

    return {
        "vfe_total": round(vfe_total, 4),
        "blocker_count": blocker_count,
        "severity_mean": round(severity_mean, 4),
        "frequency_mean": round(frequency_mean, 4),
        "entropy_risk_mean": round(entropy_risk_mean, 4),
        "fixability_mean": round(fixability_mean, 4),
    }
