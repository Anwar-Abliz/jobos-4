"""JobOS 4.0 — Hierarchy Versioning and Diffing.

Captures point-in-time snapshots of job hierarchies and computes
structural diffs between versions.  Supports auditing how hierarchies
evolve over time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class HierarchySnapshot(BaseModel):
    """A point-in-time capture of a hierarchy tree."""
    version: int = 1
    scope_id: str = ""
    snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    created_by: str = "system"
    diff_from_previous: dict[str, Any] = Field(default_factory=dict)


def snapshot_hierarchy(
    jobs: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a hierarchy into a JSON-safe snapshot dict."""
    return {
        "jobs": [
            {
                "id": j.get("id", ""),
                "tier": j.get("tier", ""),
                "statement": j.get("statement", ""),
                "category": j.get("category", ""),
                "executor_type": j.get("executor_type", "HUMAN"),
            }
            for j in jobs
        ],
        "edges": [
            {
                "parent_id": e.get("parent_id", ""),
                "child_id": e.get("child_id", ""),
            }
            for e in edges
        ],
        "job_count": len(jobs),
        "edge_count": len(edges),
    }


def diff_hierarchies(
    old: dict[str, Any],
    new: dict[str, Any],
) -> dict[str, Any]:
    """Compute structural diff between two hierarchy snapshots.

    Returns:
        {added: [...], removed: [...], modified: [...], summary: str}
    """
    old_jobs = {j["id"]: j for j in old.get("jobs", [])}
    new_jobs = {j["id"]: j for j in new.get("jobs", [])}

    old_ids = set(old_jobs.keys())
    new_ids = set(new_jobs.keys())

    added = [new_jobs[jid] for jid in (new_ids - old_ids)]
    removed = [old_jobs[jid] for jid in (old_ids - new_ids)]

    modified = []
    for jid in old_ids & new_ids:
        if old_jobs[jid].get("statement") != new_jobs[jid].get("statement"):
            modified.append({
                "id": jid,
                "old_statement": old_jobs[jid].get("statement", ""),
                "new_statement": new_jobs[jid].get("statement", ""),
            })
        elif old_jobs[jid].get("tier") != new_jobs[jid].get("tier"):
            modified.append({
                "id": jid,
                "old_tier": old_jobs[jid].get("tier", ""),
                "new_tier": new_jobs[jid].get("tier", ""),
            })

    old_edges = {(e["parent_id"], e["child_id"]) for e in old.get("edges", [])}
    new_edges = {(e["parent_id"], e["child_id"]) for e in new.get("edges", [])}
    edges_added = len(new_edges - old_edges)
    edges_removed = len(old_edges - new_edges)

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "edges_added": edges_added,
        "edges_removed": edges_removed,
        "summary": (
            f"+{len(added)} jobs, -{len(removed)} jobs, "
            f"~{len(modified)} modified, "
            f"+{edges_added}/-{edges_removed} edges"
        ),
    }
