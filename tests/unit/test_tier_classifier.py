"""Tests for tier classification.

Covers:
- T1 classification for strategic statements
- T2 for functional outcome statements
- T3 for execution statements
- T4 for micro-task statements
- Ambiguous statement defaults to T3
- classify_batch
"""
from __future__ import annotations

import pytest

from jobos.services.tier_classifier import TierClassifier


@pytest.fixture
def classifier() -> TierClassifier:
    return TierClassifier(llm=None)


class TestTierClassification:
    def test_t1_strategic_statement(self, classifier: TierClassifier):
        result = classifier.classify("Achieve strategic vision for long-term growth")
        assert result == 1

    def test_t1_short_broad_statement(self, classifier: TierClassifier):
        result = classifier.classify("Achieve overarching purpose")
        assert result == 1

    def test_t2_functional_outcome(self, classifier: TierClassifier):
        result = classifier.classify("Reduce processing time and improve throughput")
        assert result == 2

    def test_t2_ensure_outcome(self, classifier: TierClassifier):
        result = classifier.classify("Ensure compliance with quality standards and maximize output")
        assert result == 2

    def test_t3_execution_statement(self, classifier: TierClassifier):
        result = classifier.classify("Implement the data pipeline and deploy to production server")
        assert result == 3

    def test_t3_build_statement(self, classifier: TierClassifier):
        result = classifier.classify("Build and configure the reporting dashboard module")
        assert result == 3

    def test_t4_micro_task(self, classifier: TierClassifier):
        result = classifier.classify(
            "Verify all configuration parameters and validate schema before cleanup"
        )
        assert result == 4

    def test_t4_check_and_log(self, classifier: TierClassifier):
        result = classifier.classify("Check the log files and confirm the document record entries")
        assert result == 4

    def test_ambiguous_defaults_to_t3(self, classifier: TierClassifier):
        result = classifier.classify("Something completely unrelated to any tier signals")
        assert result == 3

    def test_empty_string_gets_t1_due_to_short_boost(self, classifier: TierClassifier):
        # Empty string has 0 words (<= 6), so the short/broad T1 boost fires
        result = classifier.classify("")
        assert result == 1


class TestClassifyBatch:
    def test_batch_returns_list_of_tiers(self, classifier: TierClassifier):
        statements = [
            "Achieve strategic vision",
            "Reduce error rate",
            "Deploy the service",
            "Verify the configuration",
        ]
        results = classifier.classify_batch(statements)

        assert len(results) == 4
        assert all(isinstance(t, int) for t in results)
        assert all(1 <= t <= 4 for t in results)

    def test_batch_empty_list(self, classifier: TierClassifier):
        results = classifier.classify_batch([])
        assert results == []
