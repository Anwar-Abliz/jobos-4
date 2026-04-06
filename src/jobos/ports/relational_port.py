"""JobOS 4.0 — Relational Database Port (PostgreSQL abstraction).

Per CTO Decision 3: PostgreSQL stores high-frequency metrics,
context snapshots, hiring audit logs, VFE time-series, and experiments.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from jobos.kernel.entity import (
    MetricReading,
    VFEReading,
    HiringEvent,
    ExperimentRecord,
)


class RelationalPort(ABC):
    """Abstract interface for relational database operations.

    Implementations: PostgreSQL repos (adapters/postgres/)
    """

    # ── Metric Readings ──────────────────────────────────

    @abstractmethod
    async def save_metric_reading(self, reading: MetricReading) -> str:
        """Persist a metric observation. Returns the reading ID."""
        ...

    @abstractmethod
    async def get_metric_readings(
        self,
        metric_id: str,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[MetricReading]:
        """Retrieve metric time-series, most recent first."""
        ...

    @abstractmethod
    async def get_latest_reading(self, metric_id: str) -> MetricReading | None:
        """Get the most recent reading for a metric."""
        ...

    # ── VFE Readings ─────────────────────────────────────

    @abstractmethod
    async def save_vfe_reading(self, reading: VFEReading) -> str:
        """Persist a VFE snapshot. Returns the reading ID."""
        ...

    @abstractmethod
    async def get_vfe_history(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[VFEReading]:
        """Retrieve VFE time-series for a Job."""
        ...

    # ── Hiring Events (audit log) ────────────────────────

    @abstractmethod
    async def save_hiring_event(self, event: HiringEvent) -> str:
        """Persist an immutable hiring event. Returns the event ID."""
        ...

    @abstractmethod
    async def get_hiring_events(
        self,
        entity_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[HiringEvent]:
        """Retrieve hiring events with optional filters."""
        ...

    # ── Experiments ───────────────────────────────────────

    @abstractmethod
    async def save_experiment(self, experiment: ExperimentRecord) -> str:
        """Persist an experiment record. Returns the experiment ID."""
        ...

    @abstractmethod
    async def get_experiments(
        self,
        assumption_id: str | None = None,
        limit: int = 50,
    ) -> list[ExperimentRecord]:
        """Retrieve experiments, optionally filtered by assumption."""
        ...

    # ── Health ───────────────────────────────────────────

    @abstractmethod
    async def verify_connectivity(self) -> bool:
        """Health check. Returns True if reachable."""
        ...
