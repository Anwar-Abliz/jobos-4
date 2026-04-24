"""Tests for hierarchy versioning and diffing.

Covers:
- snapshot_hierarchy serializes jobs and edges
- diff_hierarchies detects added, removed, modified jobs
- diff with identical hierarchies returns empty diff
- diff with edge changes
- HierarchySnapshot model creation
"""
from __future__ import annotations

import pytest

from jobos.kernel.hierarchy_version import (
    HierarchySnapshot,
    diff_hierarchies,
    snapshot_hierarchy,
)


def _make_jobs(*specs):
    """Helper: create job dicts from (id, tier, statement) tuples."""
    return [
        {"id": s[0], "tier": s[1], "statement": s[2], "category": "", "executor_type": "HUMAN"}
        for s in specs
    ]


def _make_edges(*pairs):
    """Helper: create edge dicts from (parent_id, child_id) tuples."""
    return [{"parent_id": p, "child_id": c} for p, c in pairs]


class TestSnapshotHierarchy:
    def test_serializes_jobs_and_edges(self):
        jobs = _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors"))
        edges = _make_edges(("j1", "j2"))

        snap = snapshot_hierarchy(jobs, edges)

        assert snap["job_count"] == 2
        assert snap["edge_count"] == 1
        assert len(snap["jobs"]) == 2
        assert snap["jobs"][0]["id"] == "j1"
        assert snap["edges"][0]["parent_id"] == "j1"
        assert snap["edges"][0]["child_id"] == "j2"

    def test_empty_hierarchy(self):
        snap = snapshot_hierarchy([], [])
        assert snap["job_count"] == 0
        assert snap["edge_count"] == 0
        assert snap["jobs"] == []
        assert snap["edges"] == []


class TestDiffHierarchies:
    def test_detects_added_jobs(self):
        old = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth")),
            [],
        )
        new = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors")),
            [],
        )

        diff = diff_hierarchies(old, new)

        assert len(diff["added"]) == 1
        assert diff["added"][0]["id"] == "j2"
        assert len(diff["removed"]) == 0

    def test_detects_removed_jobs(self):
        old = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors")),
            [],
        )
        new = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth")),
            [],
        )

        diff = diff_hierarchies(old, new)

        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["id"] == "j2"
        assert len(diff["added"]) == 0

    def test_detects_modified_jobs(self):
        old = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth")),
            [],
        )
        new = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve sustainable growth")),
            [],
        )

        diff = diff_hierarchies(old, new)

        assert len(diff["modified"]) == 1
        assert diff["modified"][0]["id"] == "j1"
        assert diff["modified"][0]["old_statement"] == "Achieve growth"
        assert diff["modified"][0]["new_statement"] == "Achieve sustainable growth"

    def test_identical_hierarchies_returns_empty_diff(self):
        jobs = _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors"))
        edges = _make_edges(("j1", "j2"))

        snap = snapshot_hierarchy(jobs, edges)
        diff = diff_hierarchies(snap, snap)

        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["modified"] == []
        assert diff["edges_added"] == 0
        assert diff["edges_removed"] == 0

    def test_detects_edge_changes(self):
        old = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors")),
            _make_edges(("j1", "j2")),
        )
        new = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors"),
                       ("j3", "T3", "Deploy fix")),
            _make_edges(("j1", "j2"), ("j2", "j3")),
        )

        diff = diff_hierarchies(old, new)

        assert diff["edges_added"] == 1
        assert diff["edges_removed"] == 0

    def test_summary_string(self):
        old = snapshot_hierarchy(_make_jobs(("j1", "T1", "Achieve growth")), [])
        new = snapshot_hierarchy(
            _make_jobs(("j1", "T1", "Achieve growth"), ("j2", "T2", "Reduce errors")),
            [],
        )
        diff = diff_hierarchies(old, new)
        assert "+1 jobs" in diff["summary"]


class TestHierarchySnapshotModel:
    def test_creation_with_defaults(self):
        snap = HierarchySnapshot()
        assert snap.version == 1
        assert snap.scope_id == ""
        assert snap.created_by == "system"
        assert snap.snapshot == {}
        assert snap.diff_from_previous == {}

    def test_creation_with_values(self):
        snap = HierarchySnapshot(
            version=3,
            scope_id="pilot_alpha",
            created_by="admin",
            snapshot={"jobs": [], "edges": []},
        )
        assert snap.version == 3
        assert snap.scope_id == "pilot_alpha"
        assert snap.created_at is not None
