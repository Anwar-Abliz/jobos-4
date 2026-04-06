"""JobOS 4.0 — PostgreSQL Repository (RelationalPort implementation).

Implements all time-series and audit operations against PostgreSQL.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, desc

from jobos.kernel.entity import (
    MetricReading,
    VFEReading,
    HiringEvent,
    ExperimentRecord,
    HiringEventType,
    ExperimentDecision,
)
from jobos.ports.relational_port import RelationalPort
from jobos.adapters.postgres.connection import PostgresConnection
from jobos.adapters.postgres.models import (
    MetricReadingRow,
    VFEReadingRow,
    HiringEventRow,
    ExperimentRow,
)

logger = logging.getLogger(__name__)


class PostgresRepo(RelationalPort):
    """PostgreSQL implementation of the RelationalPort."""

    def __init__(self, conn: PostgresConnection) -> None:
        self._conn = conn

    # ── Metric Readings ──────────────────────────────────

    async def save_metric_reading(self, reading: MetricReading) -> str:
        async with self._conn.session() as session:
            row = MetricReadingRow(
                id=reading.id,
                entity_id=reading.entity_id,
                metric_id=reading.metric_id,
                value=reading.value,
                unit=reading.unit,
                source=reading.source,
                confidence=reading.confidence,
                observed_at=reading.observed_at,
            )
            session.add(row)
            await session.commit()
            return reading.id

    async def get_metric_readings(
        self,
        metric_id: str,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[MetricReading]:
        async with self._conn.session() as session:
            stmt = (
                select(MetricReadingRow)
                .where(MetricReadingRow.metric_id == metric_id)
                .order_by(desc(MetricReadingRow.observed_at))
                .limit(limit)
            )
            if since:
                stmt = stmt.where(MetricReadingRow.observed_at >= since)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_metric_reading(r) for r in rows]

    async def get_latest_reading(self, metric_id: str) -> MetricReading | None:
        readings = await self.get_metric_readings(metric_id, limit=1)
        return readings[0] if readings else None

    # ── VFE Readings ─────────────────────────────────────

    async def save_vfe_reading(self, reading: VFEReading) -> str:
        async with self._conn.session() as session:
            row = VFEReadingRow(
                id=reading.id,
                job_id=reading.job_id,
                vfe_value=reading.vfe_value,
                efe_value=reading.efe_value,
                policy_id=reading.policy_id,
                measured_at=reading.measured_at,
            )
            session.add(row)
            await session.commit()
            return reading.id

    async def get_vfe_history(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[VFEReading]:
        async with self._conn.session() as session:
            stmt = (
                select(VFEReadingRow)
                .where(VFEReadingRow.job_id == job_id)
                .order_by(desc(VFEReadingRow.measured_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_vfe_reading(r) for r in rows]

    # ── Hiring Events ────────────────────────────────────

    async def save_hiring_event(self, event: HiringEvent) -> str:
        async with self._conn.session() as session:
            row = HiringEventRow(
                id=event.id,
                hirer_id=event.hirer_id,
                hiree_id=event.hiree_id,
                context_id=event.context_id,
                event_type=event.event_type.value,
                reason=event.reason,
                policy_snapshot=event.policy_snapshot,
                causal_estimate=event.causal_estimate,
                occurred_at=event.occurred_at,
            )
            session.add(row)
            await session.commit()
            return event.id

    async def get_hiring_events(
        self,
        entity_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[HiringEvent]:
        async with self._conn.session() as session:
            stmt = (
                select(HiringEventRow)
                .order_by(desc(HiringEventRow.occurred_at))
                .limit(limit)
            )
            if entity_id:
                stmt = stmt.where(
                    (HiringEventRow.hirer_id == entity_id)
                    | (HiringEventRow.hiree_id == entity_id)
                )
            if event_type:
                stmt = stmt.where(HiringEventRow.event_type == event_type)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_hiring_event(r) for r in rows]

    # ── Experiments ───────────────────────────────────────

    async def save_experiment(self, experiment: ExperimentRecord) -> str:
        async with self._conn.session() as session:
            row = ExperimentRow(
                id=experiment.id,
                assumption_id=experiment.assumption_id,
                method=experiment.method,
                hypothesis=experiment.hypothesis,
                success_criteria=experiment.success_criteria,
                failure_criteria=experiment.failure_criteria,
                results=experiment.results,
                decision=experiment.decision.value if experiment.decision else None,
                started_at=experiment.started_at,
                completed_at=experiment.completed_at,
            )
            session.add(row)
            await session.commit()
            return experiment.id

    async def get_experiments(
        self,
        assumption_id: str | None = None,
        limit: int = 50,
    ) -> list[ExperimentRecord]:
        async with self._conn.session() as session:
            stmt = select(ExperimentRow).limit(limit)
            if assumption_id:
                stmt = stmt.where(ExperimentRow.assumption_id == assumption_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_experiment(r) for r in rows]

    # ── Health ───────────────────────────────────────────

    async def verify_connectivity(self) -> bool:
        return await self._conn.verify_connectivity()

    # ── Row Mappers ──────────────────────────────────────

    @staticmethod
    def _row_to_metric_reading(row: MetricReadingRow) -> MetricReading:
        return MetricReading(
            id=row.id,
            entity_id=row.entity_id,
            metric_id=row.metric_id,
            value=row.value,
            unit=row.unit or "",
            source=row.source or "user",
            confidence=row.confidence or 1.0,
            observed_at=row.observed_at,
        )

    @staticmethod
    def _row_to_vfe_reading(row: VFEReadingRow) -> VFEReading:
        return VFEReading(
            id=row.id,
            job_id=row.job_id,
            vfe_value=row.vfe_value,
            efe_value=row.efe_value,
            policy_id=row.policy_id,
            measured_at=row.measured_at,
        )

    @staticmethod
    def _row_to_hiring_event(row: HiringEventRow) -> HiringEvent:
        return HiringEvent(
            id=row.id,
            hirer_id=row.hirer_id,
            hiree_id=row.hiree_id,
            context_id=row.context_id,
            event_type=HiringEventType(row.event_type),
            reason=row.reason or "",
            policy_snapshot=row.policy_snapshot or {},
            causal_estimate=row.causal_estimate or {},
            occurred_at=row.occurred_at,
        )

    @staticmethod
    def _row_to_experiment(row: ExperimentRow) -> ExperimentRecord:
        return ExperimentRecord(
            id=row.id,
            assumption_id=row.assumption_id,
            method=row.method,
            hypothesis=row.hypothesis,
            success_criteria=row.success_criteria or {},
            failure_criteria=row.failure_criteria or {},
            results=row.results or {},
            decision=ExperimentDecision(row.decision) if row.decision else None,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
