"""JobOS 4.0 — PostgreSQL Table Definitions (SQLAlchemy ORM).

Per CTO Decision 3: PostgreSQL stores high-frequency metrics,
VFE time-series, hiring audit logs, experiments, and sessions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import uuid


class Base(DeclarativeBase):
    pass


class MetricReadingRow(Base):
    """High-frequency metric observations."""
    __tablename__ = "metric_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    metric_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="")
    source: Mapped[str] = mapped_column(String(50), default="user")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VFEReadingRow(Base):
    """Variational Free Energy snapshots for Jobs."""
    __tablename__ = "vfe_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    vfe_value: Mapped[float] = mapped_column(Float, nullable=False)
    efe_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class HiringEventRow(Base):
    """Immutable hiring audit log."""
    __tablename__ = "hiring_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    hirer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    hiree_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    context_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    causal_estimate: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ExperimentRow(Base):
    """Experiment results linked to Assumptions."""
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    assumption_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[dict] = mapped_column(JSONB, default=dict)
    failure_criteria: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, default=dict)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SessionRow(Base):
    """User session state."""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    focus: Mapped[str] = mapped_column(String(100), default="general")
    goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(50), default="INIT")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class JobMetricsRow(Base):
    """Dimension B: Evaluation Space — per-job performance metrics.

    Stores accuracy, speed, and throughput readings for a Job, along with
    the bounds that the SwitchEvaluator (Axiom 7) uses to detect breaches.

    context_hash:       SHA-256 of the context vector at observation time.
    context_vector_ref: ID of the Context entity associated with this reading.
    bounds:             Per-metric (lower, upper) bounds as JSONB.
                        e.g. {"accuracy": [0.8, 1.0], "speed": [0, 200], "throughput": [30, null]}
    """
    __tablename__ = "job_metrics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    throughput: Mapped[float | None] = mapped_column(Float, nullable=True)
    bounds: Mapped[dict] = mapped_column(JSONB, default=dict)
    context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_vector_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_job_metrics_job_ts", "job_id", "timestamp"),
        Index("ix_job_metrics_accuracy", "accuracy"),
        Index("ix_job_metrics_speed", "speed"),
        Index("ix_job_metrics_throughput", "throughput"),
    )


class ExperienceVersionRow(Base):
    """Experience marker version history (Dimension A versioning)."""
    __tablename__ = "experience_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    markers: Mapped[dict] = mapped_column(JSONB, default=dict)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="llm")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_experience_versions_job_ver", "job_id", "version"),
    )


class BaselineSnapshotRow(Base):
    """Baseline metric snapshots for scenarios."""
    __tablename__ = "baseline_snapshots"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    bounds: Mapped[dict] = mapped_column(JSONB, default=dict)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    captured_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class SwitchEventRow(Base):
    """Switch events triggered by metric breaches."""
    __tablename__ = "switch_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    trigger_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_value: Mapped[float] = mapped_column(Float, nullable=False)
    trigger_bound: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
