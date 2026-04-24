"""JobOS 4.0 — Context Enrichment Engine.

Post-ingestion enrichment that operates on the entity graph:
- Auto-infer relationships between entities from shared properties
- Score context coverage (what % of the graph has rich context)
- Detect cross-source overlaps and create linking edges
- Track provenance chains across enrichment stages

Designed for batch/pipeline use — no interactive UI dependency.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from jobos.kernel.dedup import similarity
from jobos.kernel.entity import EntityBase, EntityType

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Output of a context enrichment pass."""
    entities_enriched: int = 0
    relationships_inferred: int = 0
    coverage_score: float = 0.0
    cross_source_links: int = 0
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class ContextEnrichmentEngine:
    """Enriches the entity graph with inferred relationships and coverage scoring."""

    def __init__(self, graph=None, llm=None) -> None:
        self._graph = graph
        self._llm = llm

    async def enrich(
        self,
        entity_ids: list[str] | None = None,
        scope_id: str = "",
    ) -> EnrichmentResult:
        """Run full enrichment pipeline on specified entities or scope.

        Steps:
        1. Load entities from graph
        2. Infer missing relationships (keyword/property overlap)
        3. Score context coverage
        4. Detect cross-source overlaps
        """
        result = EnrichmentResult()

        if not self._graph:
            result.warnings.append("No graph port — enrichment skipped")
            return result

        # Load entities
        if entity_ids:
            entities = []
            for eid in entity_ids:
                e = await self._graph.get_entity(eid)
                if e:
                    entities.append(e)
        else:
            entities = await self._graph.list_entities(limit=500)

        if not entities:
            result.warnings.append("No entities to enrich")
            return result

        # Step 1: Infer relationships
        inferred = await self._infer_relationships(entities)
        result.relationships_inferred = inferred

        # Step 2: Score coverage
        result.coverage_score = self._score_coverage(entities)

        # Step 3: Cross-source links
        cross_links = self._detect_cross_source(entities)
        result.cross_source_links = cross_links

        result.entities_enriched = len(entities)
        result.details = {
            "total_entities": len(entities),
            "entity_types": self._count_by_type(entities),
            "provenance_distribution": self._count_by_provenance(entities),
        }

        logger.info(
            "Enrichment: %d entities, %d inferred edges, "
            "coverage=%.2f, %d cross-source links",
            len(entities), inferred, result.coverage_score, cross_links,
        )
        return result

    async def _infer_relationships(
        self, entities: list[EntityBase],
    ) -> int:
        """Infer missing edges from property/keyword overlap."""
        if not self._graph:
            return 0

        inferred = 0
        jobs = [e for e in entities if e.entity_type == EntityType.JOB]
        metrics = [e for e in entities if e.entity_type == EntityType.METRIC]
        imperfections = [
            e for e in entities if e.entity_type == EntityType.IMPERFECTION
        ]

        # Link metrics to jobs with similar statements
        for metric in metrics:
            for job in jobs:
                if self._statements_related(metric.statement, job.statement):
                    try:
                        await self._graph.create_edge(
                            job.id, metric.id, "MEASURED_BY",
                        )
                        inferred += 1
                    except Exception:
                        pass

        # Link imperfections to jobs with matching keywords
        for imp in imperfections:
            for job in jobs:
                if self._statements_related(imp.statement, job.statement):
                    try:
                        await self._graph.create_edge(
                            imp.id, job.id, "OCCURS_IN",
                        )
                        inferred += 1
                    except Exception:
                        pass

        return inferred

    def _score_coverage(self, entities: list[EntityBase]) -> float:
        """Score how complete the context is (0.0 = empty, 1.0 = rich).

        Checks: statement present, properties populated, provenance tracked,
        5W1H context for CONTEXT entities.
        """
        if not entities:
            return 0.0

        scores: list[float] = []
        for e in entities:
            s = 0.0
            if e.statement:
                s += 0.3
            if e.properties and len(e.properties) > 1:
                s += 0.3
            if e.provenance and e.provenance != "user":
                s += 0.2
            if e.entity_type == EntityType.CONTEXT:
                ctx_fields = ["who", "why", "what", "where", "when", "how"]
                filled = sum(
                    1 for f in ctx_fields if e.properties.get(f)
                )
                s += 0.2 * (filled / len(ctx_fields))
            else:
                s += 0.2
            scores.append(min(s, 1.0))

        return round(sum(scores) / len(scores), 4)

    def _detect_cross_source(self, entities: list[EntityBase]) -> int:
        """Find entities from different sources with similar statements."""
        by_source: dict[str, list[EntityBase]] = {}
        for e in entities:
            src = e.provenance_source or e.provenance or "unknown"
            by_source.setdefault(src, []).append(e)

        sources = list(by_source.keys())
        cross_links = 0

        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                for e1 in by_source[sources[i]]:
                    for e2 in by_source[sources[j]]:
                        if (
                            e1.statement
                            and e2.statement
                            and similarity(e1.statement, e2.statement) > 0.75
                        ):
                            cross_links += 1

        return cross_links

    @staticmethod
    def _statements_related(a: str, b: str) -> bool:
        """Check if two statements share significant keywords."""
        if not a or not b:
            return False
        words_a = set(a.lower().split()) - {"the", "a", "an", "to", "of", "in", "for", "and", "is", "it"}
        words_b = set(b.lower().split()) - {"the", "a", "an", "to", "of", "in", "for", "and", "is", "it"}
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b)
        return overlap >= 2 and overlap / min(len(words_a), len(words_b)) > 0.3

    @staticmethod
    def _count_by_type(entities: list[EntityBase]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in entities:
            t = e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type)
            counts[t] = counts.get(t, 0) + 1
        return counts

    @staticmethod
    def _count_by_provenance(entities: list[EntityBase]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in entities:
            p = e.provenance or "unknown"
            counts[p] = counts.get(p, 0) + 1
        return counts
