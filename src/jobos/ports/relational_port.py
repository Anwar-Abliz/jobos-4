"""JobOS 4.0 — Relational Database Port (PostgreSQL abstraction).

Per CTO Decision 3: PostgreSQL stores high-frequency metrics,
context snapshots, hiring audit logs, VFE time-series, and experiments.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

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

    # ── Job Metrics (Dimension B — Evaluation Space) ──────

    @abstractmethod
    async def insert_job_metric(
        self,
        job_id: str,
        metrics: dict[str, float],
        bounds: dict[str, list[float | None]],
        *,
        context_hash: str | None = None,
        context_vector_ref: str | None = None,
    ) -> str:
        """Persist a job-level metrics reading for SwitchEvaluator input.

        Args:
            job_id:             The Job entity ID.
            metrics:            Dict of metric_name → value (accuracy, speed, throughput).
            bounds:             Per-metric [lower, upper] bounds. Use None for open-ended.
            context_hash:       Optional SHA-256 of the context vector.
            context_vector_ref: Optional Context entity ID.

        Returns:
            The new row ID.
        """
        ...

    @abstractmethod
    async def get_job_metrics(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve recent job metric readings, most recent first.

        Returns list of dicts with keys: id, job_id, timestamp,
        accuracy, speed, throughput, bounds, context_hash, context_vector_ref.
        """
        ...

    # ── Health ───────────────────────────────────────────

    @abstractmethod
    async def verify_connectivity(self) -> bool:
        """Health check. Returns True if reachable."""
        ...

    # ── Experience Versions (Dimension A) ────────────────

    @abstractmethod
    async def save_experience_version(
        self,
        job_id: str,
        version: int,
        markers: dict[str, Any],
        source: str,
        confidence: float | None = None,
        created_by: str | None = None,
    ) -> str:
        """Persist an experience version record. Returns the record ID."""
        ...

    @abstractmethod
    async def get_experience_history(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve experience version history for a job, most recent first."""
        ...

    # ── Baseline Snapshots ───────────────────────────────

    @abstractmethod
    async def save_baseline_snapshot(
        self,
        scenario_id: str,
        job_id: str,
        metrics: dict[str, Any],
        bounds: dict[str, Any],
        captured_by: str | None = None,
    ) -> str:
        """Persist a baseline metric snapshot. Returns the record ID."""
        ...

    @abstractmethod
    async def get_baseline_snapshot(
        self,
        scenario_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve the most recent baseline snapshot for a scenario/job pair."""
        ...

    # ── Switch Events ────────────────────────────────────

    @abstractmethod
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
        """Persist a switch event. Returns the record ID."""
        ...

    @abstractmethod
    async def get_switch_events(
        self,
        scenario_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve switch events for a scenario, most recent first."""
        ...
