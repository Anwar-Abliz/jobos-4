"""Tests for context freshness engine."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from jobos.engines.context_freshness import (
    compute_freshness,
    compute_decay_risk,
    recommend_refresh,
)
from jobos.kernel.entity import EntityBase, EntityType


def _entity(name: str = "test") -> EntityBase:
    return EntityBase(id="e1", name=name, entity_type=EntityType.SAP_PROCESS)


class TestComputeFreshness:
    def test_no_snapshot(self):
        assert compute_freshness(_entity(), None) == "stale"

    def test_live(self):
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        assert compute_freshness(_entity(), recent) == "live"

    def test_snapshot(self):
        hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        assert compute_freshness(_entity(), hours_ago) == "snapshot"

    def test_stale(self):
        days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        assert compute_freshness(_entity(), days_ago) == "stale"


class TestComputeDecayRisk:
    def test_no_snapshot(self):
        assert compute_decay_risk(_entity(), None) == 1.0

    def test_fresh(self):
        now = datetime.now(timezone.utc)
        risk = compute_decay_risk(_entity(), now, max_age_hours=168.0)
        assert risk < 0.01

    def test_half_life(self):
        half = datetime.now(timezone.utc) - timedelta(hours=84)
        risk = compute_decay_risk(_entity(), half, max_age_hours=168.0)
        assert abs(risk - 0.5) < 0.01

    def test_capped_at_1(self):
        old = datetime.now(timezone.utc) - timedelta(days=30)
        assert compute_decay_risk(_entity(), old) == 1.0


class TestRecommendRefresh:
    def test_empty(self):
        assert recommend_refresh([]) == []

    def test_filters_below_threshold(self):
        recent = datetime.now(timezone.utc)
        result = recommend_refresh(
            [(_entity("fresh"), recent)],
            threshold=0.5,
        )
        assert len(result) == 0

    def test_includes_stale(self):
        old = datetime.now(timezone.utc) - timedelta(days=10)
        result = recommend_refresh(
            [(_entity("stale"), old)],
            threshold=0.5,
        )
        assert len(result) == 1
        assert result[0]["decay_risk"] >= 0.5

    def test_sorted_by_risk(self):
        now = datetime.now(timezone.utc)
        e1 = (_entity("a"), now - timedelta(days=7))
        e2 = (_entity("b"), now - timedelta(days=1))
        e3 = (_entity("c"), None)

        result = recommend_refresh([e1, e2, e3], threshold=0.0)
        risks = [r["decay_risk"] for r in result]
        assert risks == sorted(risks, reverse=True)
