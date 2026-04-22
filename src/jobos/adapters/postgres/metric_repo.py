"""JobOS 4.0 — PostgreSQL Repository (RelationalPort implementation).

Implements all time-series and audit operations against PostgreSQL.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select

from jobos.adapters.postgres.connection import PostgresConnection
from jobos.adapters.postgres.models import (
    BaselineSnapshotRow,
    ContextSnapshotRow,
    DecisionTraceRow,
    ExperienceVersionRow,
    ExperimentRow,
    HiringEventRow,
    JobMetricsRow,
    MetricReadingRow,
    SurveyResponseRow,
    SwitchEventRow,
    VFEReadingRow,
)
from jobos.kernel.entity import (
    ExperimentDecision,
    ExperimentRecord,
    HiringEvent,
    HiringEventType,
    MetricReading,
    VFEReading,
)
from jobos.ports.relational_port import RelationalPort

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

    # ── Job Metrics (Dimension B) ─────────────────────────

    async def insert_job_metric(
        self,
        job_id: str,
        metrics: dict[str, float],
        bounds: dict[str, list[float | None]],
        *,
        context_hash: str | None = None,
        context_vector_ref: str | None = None,
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = JobMetricsRow(
                id=row_id,
                job_id=job_id,
                accuracy=metrics.get("accuracy"),
                speed=metrics.get("speed"),
                throughput=metrics.get("throughput"),
                bounds=bounds,
                context_hash=context_hash,
                context_vector_ref=context_vector_ref,
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_job_metrics(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with self._conn.session() as session:
            stmt = (
                select(JobMetricsRow)
                .where(JobMetricsRow.job_id == job_id)
                .order_by(desc(JobMetricsRow.timestamp))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "job_id": r.job_id,
                    "timestamp": r.timestamp,
                    "accuracy": r.accuracy,
                    "speed": r.speed,
                    "throughput": r.throughput,
                    "bounds": r.bounds,
                    "context_hash": r.context_hash,
                    "context_vector_ref": r.context_vector_ref,
                }
                for r in rows
            ]

    # ── Experience Versions (Dimension A) ─────────────────

    async def save_experience_version(
        self,
        job_id: str,
        version: int,
        markers: dict[str, Any],
        source: str,
        confidence: float | None = None,
        created_by: str | None = None,
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = ExperienceVersionRow(
                id=row_id,
                job_id=job_id,
                version=version,
                markers=markers,
                source=source,
                confidence=confidence,
                created_by=created_by,
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_experience_history(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with self._conn.session() as session:
            stmt = (
                select(ExperienceVersionRow)
                .where(ExperienceVersionRow.job_id == job_id)
                .order_by(desc(ExperienceVersionRow.version))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "job_id": r.job_id,
                    "version": r.version,
                    "markers": r.markers,
                    "source": r.source,
                    "confidence": r.confidence,
                    "created_by": r.created_by,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    # ── Baseline Snapshots ─────────────────────────────────

    async def save_baseline_snapshot(
        self,
        scenario_id: str,
        job_id: str,
        metrics: dict[str, Any],
        bounds: dict[str, Any],
        captured_by: str | None = None,
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = BaselineSnapshotRow(
                id=row_id,
                scenario_id=scenario_id,
                job_id=job_id,
                metrics=metrics,
                bounds=bounds,
                captured_by=captured_by,
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_baseline_snapshot(
        self,
        scenario_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        async with self._conn.session() as session:
            stmt = (
                select(BaselineSnapshotRow)
                .where(BaselineSnapshotRow.scenario_id == scenario_id)
                .where(BaselineSnapshotRow.job_id == job_id)
                .order_by(desc(BaselineSnapshotRow.captured_at))
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {
                "id": row.id,
                "scenario_id": row.scenario_id,
                "job_id": row.job_id,
                "metrics": row.metrics,
                "bounds": row.bounds,
                "captured_at": row.captured_at,
                "captured_by": row.captured_by,
            }

    # ── Switch Events ──────────────────────────────────────

    async def save_switch_event(
        self,
        scenario_id: str,
        job_id: str,
        trigger_metric: str,
        trigger_value: float,
        trigger_bound: str,
        action: str,
        reason: str = "",
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = SwitchEventRow(
                id=row_id,
                scenario_id=scenario_id,
                job_id=job_id,
                trigger_metric=trigger_metric,
                trigger_value=trigger_value,
                trigger_bound=trigger_bound,
                action=action,
                reason=reason,
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_switch_events(
        self,
        scenario_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with self._conn.session() as session:
            stmt = (
                select(SwitchEventRow)
                .where(SwitchEventRow.scenario_id == scenario_id)
                .order_by(desc(SwitchEventRow.occurred_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "scenario_id": r.scenario_id,
                    "job_id": r.job_id,
                    "trigger_metric": r.trigger_metric,
                    "trigger_value": r.trigger_value,
                    "trigger_bound": r.trigger_bound,
                    "action": r.action,
                    "reason": r.reason,
                    "occurred_at": r.occurred_at,
                    "resolved_at": r.resolved_at,
                    "resolution": r.resolution,
                }
                for r in rows
            ]

    # ── Row Mappers ──────────────────────────────────────

    # ── Decision Traces ────────────────────────────────────

    async def save_decision_trace(
        self,
        actor: str,
        action: str,
        target_entity_id: str,
        rationale: str = "",
        context_snapshot: dict[str, Any] | None = None,
        policies_evaluated: list[str] | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        vfe_before: float | None = None,
        vfe_after: float | None = None,
        lineage: list[str] | None = None,
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = DecisionTraceRow(
                id=row_id,
                actor=actor,
                action=action,
                target_entity_id=target_entity_id,
                rationale=rationale,
                context_snapshot=context_snapshot or {},
                policies_evaluated=policies_evaluated or [],
                alternatives=alternatives or [],
                vfe_before=vfe_before,
                vfe_after=vfe_after,
                lineage=lineage or [],
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_decision_traces(
        self,
        target_entity_id: str | None = None,
        actor: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with self._conn.session() as session:
            stmt = (
                select(DecisionTraceRow)
                .order_by(desc(DecisionTraceRow.created_at))
                .limit(limit)
            )
            if target_entity_id:
                stmt = stmt.where(DecisionTraceRow.target_entity_id == target_entity_id)
            if actor:
                stmt = stmt.where(DecisionTraceRow.actor == actor)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "actor": r.actor,
                    "action": r.action,
                    "target_entity_id": r.target_entity_id,
                    "context_snapshot": r.context_snapshot,
                    "rationale": r.rationale,
                    "policies_evaluated": r.policies_evaluated,
                    "alternatives": r.alternatives,
                    "vfe_before": r.vfe_before,
                    "vfe_after": r.vfe_after,
                    "lineage": r.lineage,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    # ── Survey Responses ──────────────────────────────────

    async def save_survey_response(
        self,
        survey_id: str,
        outcome_id: str,
        session_id: str,
        importance: float,
        satisfaction: float,
        opportunity_score: float,
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = SurveyResponseRow(
                id=row_id,
                survey_id=survey_id,
                outcome_id=outcome_id,
                session_id=session_id,
                importance=importance,
                satisfaction=satisfaction,
                opportunity_score=opportunity_score,
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_survey_responses(
        self,
        survey_id: str,
        outcome_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        async with self._conn.session() as session:
            stmt = (
                select(SurveyResponseRow)
                .where(SurveyResponseRow.survey_id == survey_id)
                .order_by(desc(SurveyResponseRow.created_at))
                .limit(limit)
            )
            if outcome_id:
                stmt = stmt.where(SurveyResponseRow.outcome_id == outcome_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "survey_id": r.survey_id,
                    "outcome_id": r.outcome_id,
                    "session_id": r.session_id,
                    "importance": r.importance,
                    "satisfaction": r.satisfaction,
                    "opportunity_score": r.opportunity_score,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    async def get_survey_aggregates(
        self,
        survey_id: str,
    ) -> list[dict[str, Any]]:
        from sqlalchemy import func
        async with self._conn.session() as session:
            stmt = (
                select(
                    SurveyResponseRow.outcome_id,
                    func.avg(SurveyResponseRow.importance).label("importance_mean"),
                    func.avg(SurveyResponseRow.satisfaction).label("satisfaction_mean"),
                    func.avg(SurveyResponseRow.opportunity_score).label("opportunity_mean"),
                    func.count().label("response_count"),
                )
                .where(SurveyResponseRow.survey_id == survey_id)
                .group_by(SurveyResponseRow.outcome_id)
            )
            result = await session.execute(stmt)
            rows = result.all()
            return [
                {
                    "outcome_id": r.outcome_id,
                    "importance_mean": float(r.importance_mean) if r.importance_mean else 0.0,
                    "satisfaction_mean": float(r.satisfaction_mean) if r.satisfaction_mean else 0.0,
                    "opportunity_mean": float(r.opportunity_mean) if r.opportunity_mean else 0.0,
                    "response_count": r.response_count,
                }
                for r in rows
            ]

    # ── Context Snapshots ─────────────────────────────────

    async def save_context_snapshot(
        self,
        entity_id: str,
        snapshot_data: dict[str, Any],
        source: str = "system",
    ) -> str:
        import uuid as _uuid
        row_id = _uuid.uuid4().hex[:12]
        async with self._conn.session() as session:
            row = ContextSnapshotRow(
                id=row_id,
                entity_id=entity_id,
                snapshot_data=snapshot_data,
                source=source,
            )
            session.add(row)
            await session.commit()
            return row_id

    async def get_context_snapshots(
        self,
        entity_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        async with self._conn.session() as session:
            stmt = (
                select(ContextSnapshotRow)
                .where(ContextSnapshotRow.entity_id == entity_id)
                .order_by(desc(ContextSnapshotRow.captured_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "entity_id": r.entity_id,
                    "snapshot_data": r.snapshot_data,
                    "source": r.source,
                    "captured_at": r.captured_at,
                }
                for r in rows
            ]

    # ── Row Mappers (original) ────────────────────────────

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
