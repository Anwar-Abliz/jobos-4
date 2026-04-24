"""Tests for CSV hierarchy parser.

Covers:
- detect_hierarchy_csv: header detection
- parse_hierarchy_csv: full parsing with tier columns
- Edge cases: empty, BOM, numbered prefixes, deduplication
"""
from __future__ import annotations

from jobos.adapters.extraction.csv_hierarchy_parser import (
    detect_hierarchy_csv,
    parse_hierarchy_csv,
)


SAMPLE_CSV = """Tier 1,Tier 2,Tier 3,Tier 4
Reduce customer churn,Improve onboarding experience,Design welcome sequence,1.1 Send welcome email
,,Collect user preferences,1.2 Build preference form
,Increase product stickiness,Add daily engagement hooks,2.1 Implement notification system
"""


class TestDetectHierarchyCSV:
    def test_valid_hierarchy_csv(self):
        assert detect_hierarchy_csv(SAMPLE_CSV) is True

    def test_missing_tier_1(self):
        csv = "Name,Tier 2,Tier 3\nfoo,bar,baz"
        assert detect_hierarchy_csv(csv) is False

    def test_missing_tier_2(self):
        csv = "Tier 1,Name,Tier 3\nfoo,bar,baz"
        assert detect_hierarchy_csv(csv) is False

    def test_case_insensitive(self):
        csv = "TIER 1,tier 2,Tier 3\nfoo,bar,baz"
        assert detect_hierarchy_csv(csv) is True

    def test_tier_with_spaces(self):
        csv = "tier  1,tier  2\nfoo,bar"
        assert detect_hierarchy_csv(csv) is True


class TestParseHierarchyCSV:
    def test_basic_parse(self):
        result = parse_hierarchy_csv(SAMPLE_CSV)
        assert result is not None
        assert len(result["jobs"]) > 0
        assert len(result["edges"]) > 0

    def test_domain_is_t1_statement(self):
        result = parse_hierarchy_csv(SAMPLE_CSV)
        assert result is not None
        assert result["domain"] == "Reduce customer churn"

    def test_tier_distribution(self):
        result = parse_hierarchy_csv(SAMPLE_CSV)
        assert result is not None
        summary = result["summary"]
        assert summary["T1_strategic"] >= 1
        assert summary["T2_core"] >= 1
        assert summary["T3_execution"] >= 1

    def test_edges_connect_parent_to_child(self):
        result = parse_hierarchy_csv(SAMPLE_CSV)
        assert result is not None
        for edge in result["edges"]:
            assert "parent_id" in edge
            assert "child_id" in edge
            assert edge["parent_id"] != edge["child_id"]

    def test_numbered_prefixes_stripped(self):
        result = parse_hierarchy_csv(SAMPLE_CSV)
        assert result is not None
        for job in result["jobs"]:
            assert not job["statement"].startswith("1.")
            assert not job["statement"].startswith("2.")

    def test_bom_handling(self):
        csv_with_bom = "﻿" + SAMPLE_CSV
        result = parse_hierarchy_csv(csv_with_bom)
        assert result is not None

    def test_empty_csv(self):
        assert parse_hierarchy_csv("") is None

    def test_no_tier_columns(self):
        csv = "Name,Value\nfoo,bar"
        assert parse_hierarchy_csv(csv) is None

    def test_deduplication(self):
        csv = """Tier 1,Tier 2
Goal,Sub-goal A
Goal,Sub-goal B
"""
        result = parse_hierarchy_csv(csv)
        assert result is not None
        t1_jobs = [j for j in result["jobs"] if j["tier"] == "T1_strategic"]
        assert len(t1_jobs) == 1

    def test_t4_marked_as_metric_outcome(self):
        result = parse_hierarchy_csv(SAMPLE_CSV)
        assert result is not None
        t4_jobs = [j for j in result["jobs"] if j["tier"] == "T4_micro"]
        for j in t4_jobs:
            assert j["category"] == "metric_outcome"
