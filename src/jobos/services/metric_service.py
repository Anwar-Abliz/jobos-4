"""JobOS 4.0 — Metric Service.

Reads/writes metric time-series to PostgreSQL.
Syncs summary stats to Neo4j Entity:Metric nodes (application-level write-through).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from jobos.kernel.entity import MetricReading, VFEReading
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


class MetricService:
    """Metric time-series management.

    PostgreSQL is the source of truth for readings.
    Neo4j Entity:Metric.current_value is updated on each write
    (application-level write-through per CTO Decision 3).
    """

    def __init__(self, graph: GraphPort, db: RelationalPort) -> None:
        self._graph = graph
        self._db = db

    async def record_reading(self, reading: MetricReading) -> MetricReading:
        """Record a metric observation.

        1. Write to PostgreSQL (source of truth)
        2. Update Entity:Metric.current_value in Neo4j (write-through)
        """
        await self._db.save_metric_reading(reading)

        # Write-through: update the graph entity
        entity = await self._graph.get_entity(reading.metric_id)
        if entity:
            entity.properties["current_value"] = reading.value
            entity.updated_at = datetime.now(timezone.utc)
            await self._graph.save_entity(entity)

        logger.debug(
            "Recorded metric reading: %s = %s for %s",
            reading.metric_id, reading.value, reading.entity_id,
        )
        return reading

    async def get_history(
        self,
        metric_id: str,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[MetricReading]:
        """Get metric time-series (most recent first)."""
        return await self._db.get_metric_readings(
            metric_id, limit=limit, since=since
        )

    async def get_latest(self, metric_id: str) -> MetricReading | None:
        """Get the most recent reading for a metric."""
        return await self._db.get_latest_reading(metric_id)

    async def record_vfe(self, reading: VFEReading) -> VFEReading:
        """Record a VFE snapshot for a Job."""
        await self._db.save_vfe_reading(reading)

        # Also update the Job entity's vfe_current
        job = await self._graph.get_entity(reading.job_id)
        if job:
            job.properties["vfe_current"] = reading.vfe_value
            job.updated_at = datetime.now(timezone.utc)
            await self._graph.save_entity(job)

        return reading

    async def get_vfe_history(
        self, job_id: str, limit: int = 50
    ) -> list[VFEReading]:
        """Get VFE time-series for a Job."""
        return await self._db.get_vfe_history(job_id, limit=limit)
