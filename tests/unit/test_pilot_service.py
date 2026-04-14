"""Tests for PilotService — parse, seed, idempotency, edge creation.

Uses a lightweight FakeGraphPort so no live Neo4j required.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.pilot import PilotDefinition, PilotMetric, PilotRisk, parse_pilot_file
from jobos.ports.graph_port import GraphPort
from jobos.services.pilot_service import PilotService


# ─── Fake Graph Port ─────────────────────────────────────

class FakeGraphPort(GraphPort):
    """In-memory graph for unit tests."""

    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []
        self._added_labels: list[tuple[str, str]] = []

    async def save_entity(self, entity: EntityBase) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self._entities.get(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    async def list_entities(
        self,
        entity_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityBase]:
        result = list(self._entities.values())
        if entity_type:
            result = [e for e in result if e.entity_type.value == entity_type]
        if status:
            result = [e for e in result if e.status == status]
        return result[offset : offset + limit]

    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        self._edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type.upper(),
            "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id: str, target_id: str, edge_type: str) -> bool:
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (e["source_id"] == source_id and e["target_id"] == target_id
                    and e["edge_type"] == edge_type.upper())
        ]
        return len(self._edges) < before

    async def get_neighbors(
        self, entity_id: str, edge_type: str | None = None, direction: str = "outgoing",
    ) -> list[EntityBase]:
        return []

    async def get_edges(
        self, entity_id: str, edge_type: str | None = None, direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        return []

    async def get_job_subgraph(self, job_id: str, depth: int = 3) -> dict[str, Any]:
        return {}

    async def add_label(self, entity_id: str, label: str) -> bool:
        self._added_labels.append((entity_id, label))
        return True

    async def ensure_schema(self) -> int:
        return 0

    async def verify_connectivity(self) -> bool:
        return True


# ─── Fixtures ────────────────────────────────────────────

def _make_pilot(**overrides) -> PilotDefinition:
    defaults = {
        "pilot_id": "PILOT_001",
        "segment": "Product Translation Pipeline",
        "status": "Draft",
        "tier_1_strategic": "Accelerate global market penetration.",
        "tier_2_core": "Localize software release assets.",
        "tier3_steps": [
            "Define localization scope and target languages.",
            "Locate source strings and translation memory.",
            "Prepare linguistic assets and style guides.",
            "Execute machine translation and human review.",
            "Monitor QA scores and formatting.",
            "Modify translations failing QA checks.",
            "Conclude and push localized assets to production.",
        ],
        "dimension_b_metrics": [
            PilotMetric(
                name="Translation Error Rate",
                description="Frequency of translation errors",
                target="Minimize error rate.",
                switch_trigger_threshold="> 2.0%",
            ),
        ],
        "dimension_a_config": {
            "human_executor": [
                "Feel confident in linguistic accuracy.",
                "To be perceived as a cultural bridge.",
            ],
        },
        "hypothesis": "Automating T4 will maximize throughput.",
        "exit_criteria": "Agent triggers Switch when error threshold breached.",
        "risks": [PilotRisk(risk="AI hallucinates", mitigation="QA thresholds")],
    }
    defaults.update(overrides)
    return PilotDefinition(**defaults)


@pytest.fixture
def graph() -> FakeGraphPort:
    return FakeGraphPort()


@pytest.fixture
def svc(graph: FakeGraphPort) -> PilotService:
    return PilotService(graph)


@pytest.fixture
def pilot() -> PilotDefinition:
    return _make_pilot()


# ─── Parse Tests ─────────────────────────────────────────

class TestParsePilotFile:
    def test_parse_yaml(self, tmp_path: Path):
        content = """
metadata:
  pilot_id: "TEST_001"
  segment: "Test Segment"
  status: "Draft"
job_hierarchy:
  tier_1_strategic_why: "Achieve test goal."
  tier_2_core_what: "Deliver test outcome."
tier3_steps:
  - step_1: "Define test scope."
  - step_2: "Execute test action."
dimension_b_metrics: []
dimension_a_experience_markers: {}
hypothesis_under_test: "Testing hypothesis."
exit_criteria_for_phase_1: "Exit when done."
risks_and_mitigations: []
"""
        f = tmp_path / "test.yaml"
        f.write_text(content, encoding="utf-8")
        pilot = parse_pilot_file(f)
        assert pilot.pilot_id == "TEST_001"
        assert pilot.segment == "Test Segment"
        assert len(pilot.tier3_steps) == 2
        assert pilot.tier3_steps[0] == "Define test scope."

    def test_parse_json(self, tmp_path: Path):
        data = {
            "metadata": {"pilot_id": "TEST_002", "segment": "JSON Seg", "status": "Draft"},
            "job_hierarchy": {
                "tier_1_strategic_why": "Optimize allocation.",
                "tier_2_core_what": "Process requests.",
            },
            "tier3_steps": {
                "step_1": "Define requirements.",
                "step_2": "Locate budget.",
                "step_3": "Prepare projection.",
            },
            "dimension_b_metrics": {},
            "dimension_a_experience_markers": {"human_executor": "", "ai_executor": ""},
            "hypothesis_under_test": "Hypothesis here.",
            "exit_criteria_for_phase_1": "Done when 5 requests.",
            "risks_and_mitigations": [
                {"risk": "Exceeds limits.", "mitigation": "Constrain agent."}
            ],
        }
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        pilot = parse_pilot_file(f)
        assert pilot.pilot_id == "TEST_002"
        assert len(pilot.tier3_steps) == 3
        assert len(pilot.risks) == 1
        # Empty dim A markers should not be included
        assert len(pilot.dimension_a_config) == 0

    def test_parse_json_empty_dim_b(self, tmp_path: Path):
        """Dimension B as empty dict should parse gracefully."""
        data = {
            "metadata": {"pilot_id": "T3", "segment": "S", "status": "Draft"},
            "job_hierarchy": {"tier_1_strategic_why": "G.", "tier_2_core_what": "W."},
            "tier3_steps": [],
            "dimension_b_metrics": {},
            "dimension_a_experience_markers": {},
            "hypothesis_under_test": "",
            "exit_criteria_for_phase_1": "",
            "risks_and_mitigations": [],
        }
        f = tmp_path / "t.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        pilot = parse_pilot_file(f)
        assert pilot.dimension_b_metrics == []


# ─── Seed Tests ──────────────────────────────────────────

class TestPilotServiceSeed:
    @pytest.mark.asyncio
    async def test_seed_creates_segment(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        segment_id = result["segment_id"]
        seg = graph._entities[segment_id]
        assert seg.entity_type == EntityType.SEGMENT
        assert seg.properties["slug"] == "product_translation_pipeline"

    @pytest.mark.asyncio
    async def test_seed_creates_scenario(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        scenario_id = result["scenario_id"]
        scenario = graph._entities[scenario_id]
        assert scenario.entity_type == EntityType.SCENARIO
        assert scenario.properties["pilot_id"] == "PILOT_001"
        assert scenario.properties["hypothesis"] == pilot.hypothesis

    @pytest.mark.asyncio
    async def test_seed_creates_t1_t2(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        t1 = graph._entities[result["t1_id"]]
        t2 = graph._entities[result["t2_id"]]
        assert t1.entity_type == EntityType.JOB
        assert t1.properties["hierarchy_tier"] == "T1_strategic"
        assert t1.properties["root_token"] == "ROOT"
        assert t2.properties["hierarchy_tier"] == "T2_core"

    @pytest.mark.asyncio
    async def test_seed_creates_7_t3_steps(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        assert result["t3_count"] == 7
        t3_jobs = [
            e for e in graph._entities.values()
            if e.entity_type == EntityType.JOB
            and e.properties.get("hierarchy_tier") == "T3_execution"
        ]
        assert len(t3_jobs) == 7

    @pytest.mark.asyncio
    async def test_seed_creates_4_t4_per_t3(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        assert result["t4_count"] == 28  # 7 T3 * 4 T4 each
        t4_jobs = [
            e for e in graph._entities.values()
            if e.entity_type == EntityType.JOB
            and e.properties.get("hierarchy_tier") == "T4_micro"
        ]
        assert len(t4_jobs) == 28
        # Check categories
        categories = {e.properties.get("hierarchy_category") for e in t4_jobs}
        assert categories == {"setup", "act", "verify", "cleanup"}

    @pytest.mark.asyncio
    async def test_seed_creates_hires_edges(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        hires = [e for e in graph._edges if e["edge_type"] == "HIRES"]
        # T1->T2 (1) + T2->T3 (7) + T3->T4 (28) = 36
        assert len(hires) == 36

    @pytest.mark.asyncio
    async def test_seed_creates_contains_targets_edges(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        contains = [e for e in graph._edges if e["edge_type"] == "CONTAINS"]
        targets = [e for e in graph._edges if e["edge_type"] == "TARGETS"]
        assert len(contains) == 1  # Segment -> Scenario
        assert len(targets) == 1  # Scenario -> T1

    @pytest.mark.asyncio
    async def test_seed_total_entities(self, svc, graph, pilot):
        result = await svc.seed_pilot(pilot)
        # 1 segment + 1 scenario + 1 T1 + 1 T2 + 7 T3 + 28 T4 = 39
        assert result["total_entities"] == 39
        assert len(graph._entities) == 39

    @pytest.mark.asyncio
    async def test_seed_idempotent(self, svc, graph, pilot):
        """Running seed twice should not duplicate entities."""
        result1 = await svc.seed_pilot(pilot)
        result2 = await svc.seed_pilot(pilot)
        # Same IDs returned
        assert result1["segment_id"] == result2["segment_id"]
        assert result1["scenario_id"] == result2["scenario_id"]
        assert result1["t1_id"] == result2["t1_id"]
        # Same entity count — no duplicates
        assert len(graph._entities) == 39

    @pytest.mark.asyncio
    async def test_seed_empty_dimension_a_graceful(self, svc, graph):
        """Pilot with empty Dimension A should seed without errors."""
        pilot = _make_pilot(dimension_a_config={})
        result = await svc.seed_pilot(pilot)
        scenario = graph._entities[result["scenario_id"]]
        assert scenario.properties["dimension_a_config"] == {}

    @pytest.mark.asyncio
    async def test_seed_statements_start_with_verb(self, svc, graph, pilot):
        """All job statements should start with action verbs."""
        from jobos.kernel.job_statement import validate_verb

        await svc.seed_pilot(pilot)
        jobs = [
            e for e in graph._entities.values()
            if e.entity_type == EntityType.JOB
        ]
        for job in jobs:
            if job.statement:
                assert validate_verb(job.statement), (
                    f"Job statement does not start with verb: '{job.statement}'"
                )
