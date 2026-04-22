"""JobOS 4.0 — Context Ingestion Pipeline.

5-stage pipeline: EXTRACT → TRANSFORM → ENRICH → VALIDATE → PERSIST.
Processes data from various sources into the entity graph.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


class PipelineStage:
    """Result of a single pipeline stage."""

    def __init__(self, name: str, data: Any = None, errors: list[str] | None = None):
        self.name = name
        self.data = data
        self.errors = errors or []
        self.timestamp = datetime.now(UTC)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class ContextIngestionPipeline:
    """5-stage context ingestion pipeline."""

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort,
        llm: Any | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._llm = llm

    async def run(
        self,
        source_data: dict[str, Any],
        source_type: str = "mock",
    ) -> dict[str, Any]:
        """Execute the full pipeline."""
        stages: list[PipelineStage] = []

        # Stage 1: EXTRACT
        extract_result = await self._extract(source_data, source_type)
        stages.append(extract_result)
        if not extract_result.success:
            return self._build_result(stages)

        # Stage 2: TRANSFORM
        transform_result = await self._transform(extract_result.data)
        stages.append(transform_result)
        if not transform_result.success:
            return self._build_result(stages)

        # Stage 3: ENRICH
        enrich_result = await self._enrich(transform_result.data)
        stages.append(enrich_result)
        if not enrich_result.success:
            return self._build_result(stages)

        # Stage 4: VALIDATE
        validate_result = await self._validate(enrich_result.data)
        stages.append(validate_result)
        if not validate_result.success:
            return self._build_result(stages)

        # Stage 5: PERSIST
        persist_result = await self._persist(validate_result.data)
        stages.append(persist_result)

        return self._build_result(stages)

    async def _extract(
        self,
        source_data: dict[str, Any],
        source_type: str,
    ) -> PipelineStage:
        """Stage 1: Extract raw data from source."""
        try:
            entities_raw = source_data.get("entities", [])
            edges_raw = source_data.get("edges", [])

            return PipelineStage(
                name="EXTRACT",
                data={"entities": entities_raw, "edges": edges_raw, "source_type": source_type},
            )
        except Exception as e:
            return PipelineStage(name="EXTRACT", errors=[str(e)])

    async def _transform(self, data: dict[str, Any]) -> PipelineStage:
        """Stage 2: Transform raw data into EntityBase models."""
        try:
            entities = []
            for raw in data.get("entities", []):
                entity = EntityBase(
                    id=raw.get("id", _uid()),
                    name=raw.get("name", ""),
                    statement=raw.get("statement", ""),
                    entity_type=EntityType(raw.get("entity_type", "context")),
                    properties=raw.get("properties", {}),
                )
                entities.append(entity)

            return PipelineStage(
                name="TRANSFORM",
                data={"entities": entities, "edges": data.get("edges", [])},
            )
        except Exception as e:
            return PipelineStage(name="TRANSFORM", errors=[str(e)])

    async def _enrich(self, data: dict[str, Any]) -> PipelineStage:
        """Stage 3: Enrich entities with additional context."""
        entities = data.get("entities", [])
        for entity in entities:
            # Add ingestion metadata
            entity.ingestion_time = datetime.now(UTC)
            if not entity.event_time:
                entity.event_time = entity.created_at

        return PipelineStage(name="ENRICH", data=data)

    async def _validate(self, data: dict[str, Any]) -> PipelineStage:
        """Stage 4: Validate entities against schemas."""
        errors = []
        valid_entities = []

        for entity in data.get("entities", []):
            try:
                from jobos.kernel.entity import validate_entity
                validate_entity(entity)
                valid_entities.append(entity)
            except Exception as e:
                errors.append(f"Validation failed for {entity.id}: {e}")

        data["entities"] = valid_entities
        return PipelineStage(
            name="VALIDATE",
            data=data,
            errors=errors if errors else None,
        )

    async def _persist(self, data: dict[str, Any]) -> PipelineStage:
        """Stage 5: Persist validated entities and edges to graph."""
        try:
            persisted_ids = []
            for entity in data.get("entities", []):
                entity_id = await self._graph.save_entity(entity)
                persisted_ids.append(entity_id)

            for edge in data.get("edges", []):
                await self._graph.create_edge(
                    source_id=edge["source_id"],
                    target_id=edge["target_id"],
                    edge_type=edge["edge_type"],
                    properties=edge.get("properties"),
                )

            return PipelineStage(
                name="PERSIST",
                data={"persisted_ids": persisted_ids, "edge_count": len(data.get("edges", []))},
            )
        except Exception as e:
            return PipelineStage(name="PERSIST", errors=[str(e)])

    def _build_result(self, stages: list[PipelineStage]) -> dict[str, Any]:
        """Build final pipeline result."""
        return {
            "success": all(s.success for s in stages),
            "stages": [
                {
                    "name": s.name,
                    "success": s.success,
                    "errors": s.errors,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in stages
            ],
            "final_data": stages[-1].data if stages else None,
        }
