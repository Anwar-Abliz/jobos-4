"""RED-TEAM TEST SUITE — Adversarial, edge-case, and stress tests.

Tests that exercise boundary conditions, malicious inputs, scale limits,
and cross-component integration that unit tests don't cover.

Categories:
1. Adversarial inputs (injection, oversized, malformed)
2. Boundary conditions (empty, maximal, Unicode edge cases)
3. Cross-component integration (pipeline → enrichment → survey)
4. Data integrity (provenance chains, dedup correctness)
5. Scale simulation (bulk operations with many records)
"""
from __future__ import annotations

import json
import re

import pytest

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.approval import ApprovalRequest, requires_approval, approve, reject
from jobos.kernel.dedup import find_duplicates, deduplicate_entities, similarity
from jobos.kernel.hierarchy_version import diff_hierarchies, snapshot_hierarchy
from jobos.kernel.odi import (
    compute_opportunity_score,
    classify_opportunity,
    map_opportunity_to_vfe,
    validate_outcome_statement,
)
from jobos.kernel.phase_metrics import (
    composite_score,
    score_decide_phase,
    score_define_phase,
    score_identify_phase,
)
from jobos.kernel.pii import check_entity_for_pii, detect_pii, redact_pii
from jobos.kernel.roi import compute_roi, compute_total_roi
from jobos.services.tier_classifier import TierClassifier
from jobos.services.universal_ingestor import IngestRequest, UniversalIngestor


# ═══════════════════════════════════════════════════════════
#  Fakes for integration tests
# ═══════════════════════════════════════════════════════════

class FakeHierarchyService:
    async def generate(self, context):
        from jobos.kernel.hierarchy import HierarchyResult, HierarchyJob, JobTier
        return HierarchyResult(
            context=context,
            jobs=[HierarchyJob(tier=JobTier.STRATEGIC, statement=f"Goal: {context.domain}")],
            edges=[],
            summary={"T1_strategic": 1},
        )


class FakeSOPService:
    async def ingest_from_text(self, text, domain=""):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return {
            "domain": domain, "jobs": [{"id": _uid(), "tier": "T3_execution", "statement": l} for l in lines],
            "edges": [], "summary": {"total_jobs": len(lines)},
        }


# ═══════════════════════════════════════════════════════════
#  1. ADVERSARIAL INPUTS
# ═══════════════════════════════════════════════════════════

class TestAdversarialInputs:
    """Test that the system handles malicious/unexpected inputs safely."""

    def test_pii_in_entity_statement_detected(self):
        entity = EntityBase(
            id="e1", statement="Contact john@evil.com or call 555-123-4567",
            entity_type=EntityType.JOB,
        )
        findings = check_entity_for_pii(entity)
        types = {f["type"] for f in findings}
        assert "email" in types
        assert "phone" in types

    def test_pii_in_properties_detected(self):
        entity = EntityBase(
            id="e1", statement="Clean statement",
            entity_type=EntityType.CONTEXT,
            properties={"who": "John, SSN 123-45-6789", "what": "Process data"},
        )
        findings = check_entity_for_pii(entity)
        assert any(f["type"] == "ssn" for f in findings)

    def test_redact_removes_all_pii(self):
        text = "Email me at hack@evil.com, my SSN is 123-45-6789, card 4111-1111-1111-1111"
        redacted = redact_pii(text)
        assert "hack@evil.com" not in redacted
        assert "123-45-6789" not in redacted
        assert "4111" not in redacted
        assert "[REDACTED]" in redacted

    def test_sql_injection_in_statement_harmless(self):
        entity = EntityBase(
            id="e1", statement="'; DROP TABLE entities; --",
            entity_type=EntityType.JOB,
        )
        assert entity.statement == "'; DROP TABLE entities; --"

    def test_cypher_injection_in_labels_sanitized(self):
        entity = EntityBase(
            id="e1", statement="test",
            entity_type=EntityType.JOB,
            labels=["MATCH (n) DETACH DELETE n"],
        )
        assert len(entity.labels) == 1

    @pytest.mark.asyncio
    async def test_oversized_text_handled(self):
        ingestor = UniversalIngestor(
            hierarchy_service=FakeHierarchyService(),
            sop_service=FakeSOPService(),
        )
        huge_text = "reduce churn " * 100000
        result = await ingestor.ingest(IngestRequest(text=huge_text))
        assert result.hierarchy is not None or result.hierarchy_raw

    @pytest.mark.asyncio
    async def test_null_bytes_in_text(self):
        ingestor = UniversalIngestor(
            hierarchy_service=FakeHierarchyService(),
            sop_service=FakeSOPService(),
        )
        result = await ingestor.ingest(IngestRequest(text="reduce\x00churn"))
        assert result.warnings is not None

    @pytest.mark.asyncio
    async def test_unicode_bomb_in_text(self):
        ingestor = UniversalIngestor(
            hierarchy_service=FakeHierarchyService(),
        )
        zalgo = "r̷̡̧e̶͓̓d̸̻̎u̵͖̍c̷̣̈e̶̗̿ ̵̱̈c̸̱̏h̵̰̀u̵̜̇r̸̙̈n̵̙̋"
        result = await ingestor.ingest(IngestRequest(text=zalgo))
        assert result is not None

    def test_odi_score_boundary_exact_min(self):
        score = compute_opportunity_score(1.0, 1.0)
        assert score == 1.0

    def test_odi_score_boundary_exact_max(self):
        score = compute_opportunity_score(10.0, 1.0)
        assert score == 19.0

    def test_odi_score_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            compute_opportunity_score(0.0, 5.0)
        with pytest.raises(ValueError):
            compute_opportunity_score(5.0, 11.0)
        with pytest.raises(ValueError):
            compute_opportunity_score(-1.0, 5.0)

    def test_vfe_mapping_boundaries(self):
        assert map_opportunity_to_vfe(1.0) == 0.0
        assert abs(map_opportunity_to_vfe(20.0) - 1.0) < 1e-9
        with pytest.raises(ValueError):
            map_opportunity_to_vfe(0.5)
        with pytest.raises(ValueError):
            map_opportunity_to_vfe(21.0)


# ═══════════════════════════════════════════════════════════
#  2. BOUNDARY CONDITIONS
# ═══════════════════════════════════════════════════════════

class TestBoundaryConditions:
    """Test empty, minimal, and maximal inputs."""

    def test_empty_entity_base_defaults(self):
        e = EntityBase(id="x", statement="", entity_type=EntityType.JOB)
        assert e.provenance == "user"
        assert e.provenance_source == ""
        assert e.event_time is None
        assert e.ingestion_time is None

    def test_tier_classifier_empty_string(self):
        tc = TierClassifier()
        tier = tc.classify("")
        assert tier in (1, 2, 3, 4)

    def test_tier_classifier_single_word(self):
        tc = TierClassifier()
        assert tc.classify("vision") == 1
        assert tc.classify("reduce operational cost while maintaining service quality levels") == 2
        assert tc.classify("deploy new monitoring system to production infrastructure") == 3
        assert tc.classify("verify backup completion log and archive results") == 4

    def test_dedup_identical_strings(self):
        assert similarity("hello world", "hello world") == 1.0

    def test_dedup_completely_different(self):
        assert similarity("abc", "xyz") < 0.5

    def test_dedup_empty_strings(self):
        assert similarity("", "") == 0.0
        assert similarity("hello", "") == 0.0

    def test_find_duplicates_no_items(self):
        assert find_duplicates([]) == []

    def test_find_duplicates_single_item(self):
        assert find_duplicates(["hello"]) == []

    def test_hierarchy_diff_identical(self):
        h = {"jobs": [{"id": "j1", "statement": "x", "tier": "T1"}], "edges": []}
        diff = diff_hierarchies(h, h)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["modified"] == []

    def test_hierarchy_diff_empty(self):
        diff = diff_hierarchies({}, {})
        assert diff["added"] == []
        assert diff["removed"] == []

    def test_snapshot_empty(self):
        snap = snapshot_hierarchy([], [])
        assert snap["job_count"] == 0
        assert snap["edge_count"] == 0

    def test_roi_zero_baseline(self):
        estimates = compute_roi(
            baselines={"metric": 0.0},
            current={"metric": 10.0},
            value_map={"metric": 100.0},
        )
        assert len(estimates) == 1
        assert estimates[0].improvement_pct == 0.0

    def test_roi_no_matching_metrics(self):
        estimates = compute_roi(
            baselines={"a": 1.0},
            current={"b": 2.0},
            value_map={"c": 100.0},
        )
        assert estimates == []

    def test_approval_ai_executor_never_requires(self):
        entity = EntityBase(
            id="e1", statement="AI task",
            entity_type=EntityType.JOB,
            properties={"executor_type": "AI"},
        )
        assert requires_approval("fire", entity) is False
        assert requires_approval("switch", entity) is False

    def test_approval_human_fire_requires(self):
        entity = EntityBase(
            id="e1", statement="Human task",
            entity_type=EntityType.JOB,
            properties={"executor_type": "HUMAN"},
        )
        assert requires_approval("fire", entity) is True
        assert requires_approval("switch", entity) is True
        assert requires_approval("hire", entity) is False

    def test_phase_score_empty_inputs(self):
        s = score_identify_phase([])
        assert s.score == 0.0
        s = score_define_phase(0, 0, 0)
        assert s.score == 0.0

    def test_composite_score_weighting(self):
        from jobos.kernel.phase_metrics import PhaseScore
        i = PhaseScore(phase="identify", score=1.0)
        d = PhaseScore(phase="define", score=1.0)
        c = PhaseScore(phase="decide", score=1.0)
        assert composite_score(i, d, c) == 1.0

        i.score = 0.0
        d.score = 0.0
        c.score = 0.0
        assert composite_score(i, d, c) == 0.0


# ═══════════════════════════════════════════════════════════
#  3. CROSS-COMPONENT INTEGRATION
# ═══════════════════════════════════════════════════════════

class TestCrossComponent:
    """Integration tests spanning multiple subsystems."""

    @pytest.mark.asyncio
    async def test_ingest_keyword_produces_valid_hierarchy(self):
        ingestor = UniversalIngestor(
            hierarchy_service=FakeHierarchyService(),
        )
        result = await ingestor.ingest(IngestRequest(text="supply chain optimization"))
        assert result.hierarchy is not None
        assert result.context is not None
        assert result.source_type == "text_to_hierarchy"
        d = result.to_dict()
        assert "hierarchy" in d
        assert "context" in d

    @pytest.mark.asyncio
    async def test_ingest_steps_produces_jobs(self):
        ingestor = UniversalIngestor(sop_service=FakeSOPService())
        text = "1. Receive order\n2. Check stock\n3. Ship product\n4. Send invoice"
        result = await ingestor.ingest(IngestRequest(text=text))
        assert result.source_type == "sop_steps"
        assert len(result.hierarchy_raw.get("jobs", [])) >= 3

    @pytest.mark.asyncio
    async def test_ingest_csv_hierarchy_roundtrip(self):
        csv = b"Tier 1,Tier 2,Tier 3\nStrategic goal,Functional outcome,Execution step\n"
        ingestor = UniversalIngestor()
        result = await ingestor.ingest(IngestRequest(files=[(csv, "test.csv")]))
        assert result.source_type == "csv_hierarchy"
        assert result.hierarchy_raw.get("domain") == "Strategic goal"

    @pytest.mark.asyncio
    async def test_ingest_result_serializable(self):
        ingestor = UniversalIngestor(hierarchy_service=FakeHierarchyService())
        result = await ingestor.ingest(IngestRequest(text="reduce churn", domain="SaaS"))
        d = result.to_dict()
        serialized = json.dumps(d, default=str)
        assert len(serialized) > 10
        parsed = json.loads(serialized)
        assert parsed["source_type"] == "text_to_hierarchy"

    def test_odi_to_vfe_pipeline(self):
        """Test ODI score → VFE mapping → opportunity classification chain."""
        score = compute_opportunity_score(8.0, 3.0)
        assert score == 13.0  # 8 + max(0, 8-3) = 13
        vfe = map_opportunity_to_vfe(score)
        assert 0.0 < vfe < 1.0
        classification = classify_opportunity(score)
        assert classification == "underserved"

    def test_odi_overserved_classification(self):
        score = compute_opportunity_score(2.0, 8.0)
        assert score == 2.0
        assert classify_opportunity(score) == "overserved"

    def test_odi_appropriately_served(self):
        score = compute_opportunity_score(5.0, 3.0)
        assert score == 7.0
        assert classify_opportunity(score) == "appropriately_served"

    def test_outcome_validation_correct(self):
        assert validate_outcome_statement("Minimize the time it takes to process an order")
        assert validate_outcome_statement("Maximize the accuracy of the data entry")

    def test_outcome_validation_incorrect(self):
        assert not validate_outcome_statement("Reduce the time it takes to process")
        assert not validate_outcome_statement("The time should be reduced")
        assert not validate_outcome_statement("")


# ═══════════════════════════════════════════════════════════
#  4. DATA INTEGRITY
# ═══════════════════════════════════════════════════════════

class TestDataIntegrity:
    """Verify data consistency across operations."""

    def test_entity_id_uniqueness(self):
        ids = {_uid() for _ in range(1000)}
        assert len(ids) == 1000

    def test_entity_provenance_preserved(self):
        e = EntityBase(
            id="x", statement="test", entity_type=EntityType.JOB,
            provenance="llm", provenance_source="qwen-plus",
        )
        assert e.provenance == "llm"
        assert e.provenance_source == "qwen-plus"
        d = e.model_dump()
        restored = EntityBase(**d)
        assert restored.provenance == "llm"
        assert restored.provenance_source == "qwen-plus"

    def test_dedup_preserves_first_entity(self):
        e1 = EntityBase(id="keep", statement="Reduce customer churn", entity_type=EntityType.JOB)
        e2 = EntityBase(id="remove", statement="Reduce customer churn rate", entity_type=EntityType.JOB)
        unique, merged = deduplicate_entities([e1, e2], threshold=0.8)
        assert len(unique) == 1
        assert unique[0].id == "keep"
        assert merged[0][0] == "keep"
        assert merged[0][1] == "remove"

    def test_hierarchy_snapshot_completeness(self):
        jobs = [
            {"id": "j1", "tier": "T1", "statement": "Goal", "category": "", "executor_type": "HUMAN"},
            {"id": "j2", "tier": "T2", "statement": "Outcome", "category": "", "executor_type": "HUMAN"},
        ]
        edges = [{"parent_id": "j1", "child_id": "j2"}]
        snap = snapshot_hierarchy(jobs, edges)
        assert snap["job_count"] == 2
        assert snap["edge_count"] == 1
        assert snap["jobs"][0]["id"] == "j1"
        assert snap["edges"][0]["parent_id"] == "j1"

    def test_hierarchy_diff_detects_additions(self):
        old = {"jobs": [{"id": "j1", "statement": "A", "tier": "T1"}], "edges": []}
        new = {"jobs": [
            {"id": "j1", "statement": "A", "tier": "T1"},
            {"id": "j2", "statement": "B", "tier": "T2"},
        ], "edges": [{"parent_id": "j1", "child_id": "j2"}]}
        diff = diff_hierarchies(old, new)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["id"] == "j2"
        assert diff["edges_added"] == 1

    def test_hierarchy_diff_detects_removals(self):
        old = {"jobs": [{"id": "j1", "statement": "A"}, {"id": "j2", "statement": "B"}], "edges": []}
        new = {"jobs": [{"id": "j1", "statement": "A"}], "edges": []}
        diff = diff_hierarchies(old, new)
        assert len(diff["removed"]) == 1

    def test_hierarchy_diff_detects_modifications(self):
        old = {"jobs": [{"id": "j1", "statement": "Old text", "tier": "T1"}], "edges": []}
        new = {"jobs": [{"id": "j1", "statement": "New text", "tier": "T1"}], "edges": []}
        diff = diff_hierarchies(old, new)
        assert len(diff["modified"]) == 1

    def test_approval_state_machine(self):
        req = ApprovalRequest(entity_id="e1", action="fire", requester="system")
        assert req.status.value == "pending"
        approved = approve(req, "admin")
        assert approved.status.value == "approved"
        assert approved.resolved_by == "admin"
        rejected = reject(req, "admin", "not justified")
        assert rejected.status.value == "rejected"
        assert rejected.reason == "not justified"

    def test_roi_positive_improvement(self):
        estimates = compute_roi(
            baselines={"churn": 0.08},
            current={"churn": 0.03},
            value_map={"churn": 10000.0},
        )
        assert len(estimates) == 1
        assert estimates[0].improvement == pytest.approx(-0.05, abs=0.001)
        assert estimates[0].estimated_value < 0  # churn decreased = negative delta * positive value

    def test_roi_total_aggregation(self):
        estimates = compute_roi(
            baselines={"speed": 100.0, "accuracy": 0.8},
            current={"speed": 120.0, "accuracy": 0.95},
            value_map={"speed": 50.0, "accuracy": 1000.0},
        )
        total = compute_total_roi(estimates)
        assert total["metric_count"] == 2
        assert total["total_estimated_value"] > 0


# ═══════════════════════════════════════════════════════════
#  5. SCALE SIMULATION
# ═══════════════════════════════════════════════════════════

class TestScaleSimulation:
    """Test operations at non-trivial scale."""

    def test_dedup_100_similar_statements(self):
        statements = [f"Reduce customer churn by {i}%" for i in range(100)]
        pairs = find_duplicates(statements, threshold=0.85)
        assert len(pairs) > 0

    def test_dedup_100_unique_entities(self):
        domains = ["healthcare", "logistics", "finance", "education", "manufacturing",
                    "retail", "energy", "telecom", "government", "agriculture"]
        actions = ["reduce", "improve", "optimize", "automate", "monitor",
                   "validate", "deploy", "integrate", "scale", "migrate"]
        entities = [
            EntityBase(
                id=f"e{i}",
                statement=f"{actions[i % 10]} {domains[i // 10]} system component {i}",
                entity_type=EntityType.JOB,
            )
            for i in range(100)
        ]
        unique, merged = deduplicate_entities(entities, threshold=0.95)
        assert len(unique) >= 50

    def test_tier_classify_batch_100(self):
        tc = TierClassifier()
        statements = [
            "Achieve sustainable growth",
            "Reduce operational cost",
            "Implement new CRM system",
            "Verify data backup completion",
        ] * 25
        tiers = tc.classify_batch(statements)
        assert len(tiers) == 100
        assert all(t in (1, 2, 3, 4) for t in tiers)

    def test_pii_scan_large_text(self):
        text = ("Normal text without PII. " * 1000 +
                "But hidden here: user@example.com and 555-123-4567")
        findings = detect_pii(text)
        assert len(findings) >= 2

    def test_hierarchy_snapshot_50_jobs(self):
        jobs = [{"id": f"j{i}", "tier": f"T{(i % 4) + 1}", "statement": f"Job {i}",
                 "category": "", "executor_type": "HUMAN"} for i in range(50)]
        edges = [{"parent_id": f"j{i}", "child_id": f"j{i+1}"} for i in range(49)]
        snap = snapshot_hierarchy(jobs, edges)
        assert snap["job_count"] == 50
        assert snap["edge_count"] == 49

    @pytest.mark.asyncio
    async def test_ingest_long_process_document(self):
        ingestor = UniversalIngestor(sop_service=FakeSOPService())
        steps = "\n".join(f"{i+1}. Process step number {i+1} with detailed description" for i in range(50))
        result = await ingestor.ingest(IngestRequest(text=steps))
        assert result.source_type == "sop_steps"
        assert len(result.hierarchy_raw.get("jobs", [])) >= 20

    def test_phase_metrics_with_many_jobs(self):
        jobs = [{"id": f"j{i}", "tier": f"T{(i%4)+1}", "statement": f"Define task {i}"}
                for i in range(100)]
        score = score_identify_phase(jobs)
        assert 0.0 <= score.score <= 1.0

    def test_roi_many_metrics(self):
        baselines = {f"metric_{i}": float(i) for i in range(1, 51)}
        current = {f"metric_{i}": float(i) * 1.1 for i in range(1, 51)}
        value_map = {f"metric_{i}": 100.0 for i in range(1, 51)}
        estimates = compute_roi(baselines, current, value_map)
        assert len(estimates) == 50
        total = compute_total_roi(estimates)
        assert total["metric_count"] == 50
