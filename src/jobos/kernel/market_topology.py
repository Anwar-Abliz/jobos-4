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
    """Axiom 8 Phase 1: Discover market clusters from unmet outcome patterns.

    Args:
        jobs:             All Job entities to analyze.
        imperfection_map: job_id → list of Imperfection entities associated with it.
                          If None, clustering is done without imperfection context.

    Returns:
        List of cluster dicts. Each cluster has:
            cluster_id:   Unique cluster identifier.
            job_ids:      List of job entity IDs in this cluster.
            pattern:      Human-readable description of the shared outcome pattern.
            centroid:     IPS vector centroid (Phase 2; None in Phase 1).
            size:         Number of jobs in this cluster.

    Phase 1 behaviour:
        Returns a single cluster containing all jobs. This is the correct
        degenerate case: we have insufficient data to distinguish segments.

    Phase 2 implementation plan:
        1. Compute VFE vector for each job:
           VFE = 3*Blocker + 2*Severity + Frequency + EntropyRisk + (1-Fixability)
        2. Normalize vectors to unit length.
        3. Apply KMeans(k=sqrt(n)) on the VFE vectors.
        4. Label each cluster with the dominant imperfection pattern.

    Phase 3 implementation plan:
        1. Build imperfection co-occurrence graph in Neo4j.
        2. Run Louvain / label propagation community detection.
        3. Map communities back to job clusters.
    """
    job_ids = [j.id for j in jobs if j.entity_type == EntityType.JOB]
    if not job_ids:
        return []

    return [
        {
            "cluster_id": "stub_cluster_0",
            "job_ids": job_ids,
            "pattern": "unimplemented — Phase 2 will use VFE vector clustering",
            "centroid": None,
            "size": len(job_ids),
        }
    ]


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

    blocker_count = sum(1 for i in imperfections if i.properties.get("is_blocker", False))
    severity_mean = sum(i.properties.get("severity", 0.0) for i in imperfections) / len(imperfections)
    frequency_mean = sum(i.properties.get("frequency", 0.0) for i in imperfections) / len(imperfections)
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
