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
