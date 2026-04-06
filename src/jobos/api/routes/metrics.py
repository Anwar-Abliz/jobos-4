"""JobOS 4.0 — Metric Routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobos.kernel.entity import MetricReading, _uid, _now
from jobos.api.deps import get_metric_service

router = APIRouter()


class MetricReadingIn(BaseModel):
    entity_id: str
    metric_id: str
    value: float
    unit: str = ""
    source: str = "user"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


@router.post("/metrics/{metric_id}/readings")
async def record_reading(metric_id: str, req: MetricReadingIn) -> dict:
    """Record a metric observation.

    Writes to PostgreSQL (time-series) and updates the
    Entity:Metric.current_value in Neo4j (write-through).
    """
    svc = get_metric_service()
    reading = MetricReading(
        entity_id=req.entity_id,
        metric_id=metric_id,
        value=req.value,
        unit=req.unit,
        source=req.source,
        confidence=req.confidence,
    )
    saved = await svc.record_reading(reading)
    return {
        "id": saved.id,
        "metric_id": saved.metric_id,
        "value": saved.value,
        "observed_at": saved.observed_at.isoformat(),
    }


@router.get("/metrics/{metric_id}/readings")
async def get_readings(metric_id: str, limit: int = 100) -> dict:
    """Get metric time-series (most recent first)."""
    svc = get_metric_service()
    readings = await svc.get_history(metric_id, limit=limit)
    return {
        "metric_id": metric_id,
        "count": len(readings),
        "readings": [
            {"id": r.id, "value": r.value, "observed_at": r.observed_at.isoformat()}
            for r in readings
        ],
    }


@router.get("/metrics/{metric_id}/readings/latest")
async def get_latest_reading(metric_id: str) -> dict:
    """Get the most recent reading for a metric."""
    svc = get_metric_service()
    reading = await svc.get_latest(metric_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings found")
    return {
        "id": reading.id,
        "value": reading.value,
        "observed_at": reading.observed_at.isoformat(),
    }
