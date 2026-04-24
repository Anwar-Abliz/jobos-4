"""Tests for entity de-duplication.

Covers:
- similarity returns 1.0 for identical strings
- similarity returns 0.0 for empty strings
- find_duplicates detects near-duplicates
- find_duplicates threshold filtering
- deduplicate_entities removes duplicates
- deduplicate_entities preserves unique entities
"""
from __future__ import annotations

import pytest

from jobos.kernel.dedup import deduplicate_entities, find_duplicates, similarity
from jobos.kernel.entity import EntityBase, EntityType


class TestSimilarity:
    def test_identical_strings(self):
        assert similarity("Reduce processing time", "Reduce processing time") == 1.0

    def test_empty_strings(self):
        assert similarity("", "") == 0.0

    def test_one_empty_string(self):
        assert similarity("Reduce processing time", "") == 0.0
        assert similarity("", "Reduce processing time") == 0.0

    def test_case_insensitive(self):
        score = similarity("Reduce Errors", "reduce errors")
        assert score == 1.0

    def test_similar_strings_high_score(self):
        score = similarity(
            "Reduce processing time for orders",
            "Reduce processing time for order fulfillment",
        )
        assert score > 0.7

    def test_dissimilar_strings_low_score(self):
        score = similarity(
            "Reduce processing time",
            "Deploy monitoring dashboard",
        )
        assert score < 0.5


class TestFindDuplicates:
    def test_detects_near_duplicates(self):
        statements = [
            "Reduce order processing time",
            "Reduce order processing times",
            "Deploy the monitoring dashboard",
        ]
        pairs = find_duplicates(statements, threshold=0.85)

        assert len(pairs) >= 1
        # The first two should be paired
        assert pairs[0][0] == 0
        assert pairs[0][1] == 1
        assert pairs[0][2] >= 0.85

    def test_threshold_filtering(self):
        statements = [
            "Reduce order processing time",
            "Reduce order processing times",
            "Deploy the monitoring dashboard",
        ]
        # High threshold should still catch near-exact match
        pairs_high = find_duplicates(statements, threshold=0.90)
        # Very high threshold might filter it out
        pairs_extreme = find_duplicates(statements, threshold=0.99)

        assert len(pairs_high) >= len(pairs_extreme)

    def test_no_duplicates(self):
        statements = [
            "Reduce order processing time",
            "Deploy the monitoring dashboard",
            "Verify compliance status",
        ]
        pairs = find_duplicates(statements, threshold=0.85)
        assert pairs == []

    def test_empty_list(self):
        pairs = find_duplicates([], threshold=0.85)
        assert pairs == []


class TestDeduplicateEntities:
    def _make_entity(self, eid: str, statement: str) -> EntityBase:
        return EntityBase(
            id=eid,
            statement=statement,
            entity_type=EntityType.JOB,
        )

    def test_removes_duplicates(self):
        entities = [
            self._make_entity("e1", "Reduce order processing time"),
            self._make_entity("e2", "Reduce order processing times"),
            self._make_entity("e3", "Deploy the monitoring dashboard"),
        ]
        unique, merged = deduplicate_entities(entities, threshold=0.85)

        assert len(unique) == 2
        assert len(merged) == 1
        # e1 is kept, e2 is removed
        kept_ids = [e.id for e in unique]
        assert "e1" in kept_ids
        assert "e3" in kept_ids
        assert merged[0] == ("e1", "e2", merged[0][2])

    def test_preserves_unique_entities(self):
        entities = [
            self._make_entity("e1", "Reduce order processing time"),
            self._make_entity("e2", "Deploy the monitoring dashboard"),
            self._make_entity("e3", "Verify compliance status"),
        ]
        unique, merged = deduplicate_entities(entities, threshold=0.85)

        assert len(unique) == 3
        assert merged == []

    def test_empty_list(self):
        unique, merged = deduplicate_entities([], threshold=0.85)
        assert unique == []
        assert merged == []

    def test_single_entity(self):
        entities = [self._make_entity("e1", "Reduce processing time")]
        unique, merged = deduplicate_entities(entities, threshold=0.85)
        assert len(unique) == 1
        assert merged == []
