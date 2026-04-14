"""JobOS 4.0 — Pilot Seeding Service.

Seeds the graph from parsed PilotDefinition files:
    Segment → Scenario → T1 → T2 → 7×T3 → 4×T4 per T3

Idempotent by slug: re-running with the same pilot file
updates existing entities rather than creating duplicates.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.hierarchy import JobTier, MicroJobCategory
from jobos.kernel.pilot import PilotDefinition
from jobos.ports.graph_port import GraphPort

logger = logging.getLogger(__name__)


class PilotService:
    """Seeds pilot definitions into the Neo4j graph."""

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph

    async def seed_pilot(self, pilot: PilotDefinition) -> dict[str, Any]:
        """Seed a complete pilot into the graph.

        Creates or updates:
        - 1 Segment entity
        - 1 Scenario entity
        - 1 T1 strategic job
        - 1 T2 core functional job
        - N T3 execution jobs (from pilot's steps, typically 7)
        - 4 T4 micro-jobs per T3 (setup, act, verify, cleanup)
        - Edges: CONTAINS, TARGETS, HIRES

        Returns a summary dict with entity counts and IDs.
        """
        scope_id = f"pilot_{pilot.pilot_id}"

        # 1. Segment
        segment_slug = _slugify(pilot.segment)
        segment = await self._upsert_by_slug(
            slug=segment_slug,
            entity_type=EntityType.SEGMENT,
            name=pilot.segment,
            statement=f"Segment: {pilot.segment}",
            properties={
                "slug": segment_slug,
                "description": pilot.segment,
                "root_job_ids": [],
                "tags": [],
            },
        )

        # 2. Scenario
        scenario_slug = _slugify(f"{pilot.pilot_id}_{pilot.segment}")
        scenario = await self._upsert_by_slug(
            slug=scenario_slug,
            entity_type=EntityType.SCENARIO,
            name=f"{pilot.pilot_id} — {pilot.segment}",
            statement=pilot.hypothesis or f"Scenario for {pilot.segment}",
            properties={
                "slug": scenario_slug,
                "segment_id": segment.id,
                "pilot_id": pilot.pilot_id,
                "hypothesis": pilot.hypothesis,
                "exit_criteria": pilot.exit_criteria,
                "risks": [r.model_dump() for r in pilot.risks],
                "dimension_b_metrics": [m.model_dump() for m in pilot.dimension_b_metrics],
                "dimension_a_config": pilot.dimension_a_config,
                "status": pilot.status,
                "phase": "phase_1",
            },
        )

        # Segment -[:CONTAINS]-> Scenario
        await self._graph.create_edge(segment.id, scenario.id, "CONTAINS")

        # 3. T1 Strategic
        t1_slug = _slugify(f"{pilot.pilot_id}_t1")
        t1_stmt = pilot.tier_1_strategic or "Achieve strategic objective"
        t1_stmt = _ensure_verb(t1_stmt)
        t1 = await self._upsert_by_slug(
            slug=t1_slug,
            entity_type=EntityType.JOB,
            name=t1_stmt[:80],
            statement=t1_stmt,
            properties={
                "slug": t1_slug,
                "job_type": "core_functional",
                "job_nature": "project",
                "level": 0,
                "hierarchy_tier": JobTier.STRATEGIC.value,
                "vfe_current": 0.0,
                "root_token": "ROOT",
                "scope_id": scope_id,
                "tier": 1,
            },
        )

        # Scenario -[:TARGETS]-> T1
        await self._graph.create_edge(scenario.id, t1.id, "TARGETS")

        # Update Segment root_job_ids
        seg_props = segment.properties.copy()
        if t1.id not in seg_props.get("root_job_ids", []):
            seg_props.setdefault("root_job_ids", []).append(t1.id)
            segment.properties = seg_props
            await self._graph.save_entity(segment)

        # 4. T2 Core Functional
        t2_slug = _slugify(f"{pilot.pilot_id}_t2")
        t2_stmt = pilot.tier_2_core or "Deliver core functional outcome"
        t2_stmt = _ensure_verb(t2_stmt)
        t2 = await self._upsert_by_slug(
            slug=t2_slug,
            entity_type=EntityType.JOB,
            name=t2_stmt[:80],
            statement=t2_stmt,
            properties={
                "slug": t2_slug,
                "job_type": "core_functional",
                "job_nature": "project",
                "level": 1,
                "hierarchy_tier": JobTier.CORE_FUNCTIONAL.value,
                "vfe_current": 0.0,
                "scope_id": scope_id,
                "tier": 2,
            },
        )

        # T1 -[:HIRES]-> T2
        await self._graph.create_edge(t1.id, t2.id, "HIRES", {"source": "pilot_seed"})

        # 5. T3 Execution steps (pilot's 7 steps)
        t3_entities: list[EntityBase] = []
        for i, step_text in enumerate(pilot.tier3_steps):
            t3_slug = _slugify(f"{pilot.pilot_id}_t3_step{i + 1}")
            step_stmt = _ensure_verb(step_text)
            t3 = await self._upsert_by_slug(
                slug=t3_slug,
                entity_type=EntityType.JOB,
                name=step_stmt[:80],
                statement=step_stmt,
                properties={
                    "slug": t3_slug,
                    "job_type": "core_functional",
                    "job_nature": "project",
                    "level": 2,
                    "hierarchy_tier": JobTier.EXECUTION.value,
                    "hierarchy_category": "operation",
                    "vfe_current": 0.0,
                    "scope_id": scope_id,
                    "tier": 3,
                    "step_number": i + 1,
                },
            )
            t3_entities.append(t3)
            # T2 -[:HIRES]-> T3
            await self._graph.create_edge(t2.id, t3.id, "HIRES", {"source": "pilot_seed"})

        # 6. T4 Micro-Jobs: 4 per T3 (setup, act, verify, cleanup)
        t4_entities: list[EntityBase] = []
        categories = [
            MicroJobCategory.SETUP,
            MicroJobCategory.ACT,
            MicroJobCategory.VERIFY,
            MicroJobCategory.CLEANUP,
        ]
        for t3 in t3_entities:
            t3_name = t3.statement[:40]
            for cat in categories:
                t4_slug = _slugify(
                    f"{pilot.pilot_id}_t4_{t3.properties.get('step_number', 0)}_{cat.value}"
                )
                t4_stmt = _micro_job_statement(cat, t3_name)
                t4 = await self._upsert_by_slug(
                    slug=t4_slug,
                    entity_type=EntityType.JOB,
                    name=t4_stmt[:80],
                    statement=t4_stmt,
                    properties={
                        "slug": t4_slug,
                        "job_type": "core_functional",
                        "job_nature": "project",
                        "level": 3,
                        "hierarchy_tier": JobTier.MICRO_JOB.value,
                        "hierarchy_category": cat.value,
                        "vfe_current": 0.0,
                        "scope_id": scope_id,
                        "tier": 4,
                    },
                )
                t4_entities.append(t4)
                # T3 -[:HIRES]-> T4
                await self._graph.create_edge(
                    t3.id, t4.id, "HIRES", {"source": "pilot_seed"}
                )

        summary = {
            "segment_id": segment.id,
            "scenario_id": scenario.id,
            "t1_id": t1.id,
            "t2_id": t2.id,
            "t3_count": len(t3_entities),
            "t4_count": len(t4_entities),
            "total_entities": 2 + 2 + len(t3_entities) + len(t4_entities),
            "pilot_id": pilot.pilot_id,
        }
        logger.info("Seeded pilot %s: %s", pilot.pilot_id, summary)
        return summary

    async def _upsert_by_slug(
        self,
        slug: str,
        entity_type: EntityType,
        name: str,
        statement: str,
        properties: dict[str, Any],
    ) -> EntityBase:
        """Find existing entity by slug or create new one."""
        existing = await self._find_by_slug(slug, entity_type.value)
        if existing:
            existing.name = name
            existing.statement = statement
            existing.properties.update(properties)
            await self._graph.save_entity(existing)
            return existing

        type_label = entity_type.value.capitalize()
        entity = EntityBase(
            id=_uid(),
            name=name,
            statement=statement,
            entity_type=entity_type,
            status="active",
            labels=[type_label],
            properties=properties,
        )
        await self._graph.save_entity(entity)
        return entity

    async def _find_by_slug(
        self, slug: str, entity_type: str
    ) -> EntityBase | None:
        """Find an entity by its slug property."""
        entities = await self._graph.list_entities(
            entity_type=entity_type, limit=200
        )
        for e in entities:
            if e.properties.get("slug") == slug:
                return e
        return None


def _slugify(text: str) -> str:
    """Create a URL/ID-safe slug from text."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:80]


def _ensure_verb(statement: str) -> str:
    """Ensure statement starts with an action verb."""
    from jobos.kernel.job_statement import validate_verb

    if not statement:
        return "achieve unspecified goal"
    if validate_verb(statement):
        return statement
    # Prepend a generic verb
    lower = statement.lower().strip()
    if lower.startswith(("the ", "a ", "an ")):
        return f"achieve {statement}"
    return f"execute {statement}"


def _micro_job_statement(category: MicroJobCategory, parent_desc: str) -> str:
    """Generate a T4 micro-job statement from its category and parent."""
    templates = {
        MicroJobCategory.SETUP: f"prepare inputs and environment for {parent_desc}",
        MicroJobCategory.ACT: f"execute core action for {parent_desc}",
        MicroJobCategory.VERIFY: f"verify outcome against expected results for {parent_desc}",
        MicroJobCategory.CLEANUP: f"release resources and hand off after {parent_desc}",
    }
    return templates.get(category, f"perform {category.value} for {parent_desc}")
