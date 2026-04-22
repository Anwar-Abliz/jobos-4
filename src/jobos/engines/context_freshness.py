"""JobOS 4.0 — Context Freshness Engine.

Computes freshness scores, decay risk, and recommends refresh priorities.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from jobos.kernel.entity import EntityBase

logger = logging.getLogger(__name__)


def compute_freshness(
    entity: EntityBase,
    latest_snapshot_at: datetime | None = None,
) -> str:
    """Compute freshness status: live / snapshot / stale.

    Args:
        entity: The entity to evaluate.
        latest_snapshot_at: When the last context snapshot was taken.

    Returns:
        "live" if < 1 hour, "snapshot" if < 24 hours, "stale" otherwise.
    """
    if latest_snapshot_at is None:
        return "stale"

    age = datetime.now(UTC) - latest_snapshot_at

    if age < timedelta(hours=1):
        return "live"
    elif age < timedelta(hours=24):
        return "snapshot"
    else:
        return "stale"


def compute_decay_risk(
    entity: EntityBase,
    latest_snapshot_at: datetime | None = None,
    max_age_hours: float = 168.0,
) -> float:
    """Compute decay risk as a score from 0.0 to 1.0.

    Linear decay: risk = min(1.0, age_hours / max_age_hours).
    """
    if latest_snapshot_at is None:
        return 1.0

    age = datetime.now(UTC) - latest_snapshot_at
    age_hours = age.total_seconds() / 3600

    return min(1.0, age_hours / max_age_hours)


def recommend_refresh(
    entities_with_snapshots: list[tuple[EntityBase, datetime | None]],
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Recommend entities that need context refresh.

    Returns prioritized list sorted by decay risk descending.

    Args:
        entities_with_snapshots: List of (entity, latest_snapshot_time) pairs.
        threshold: Minimum decay risk to recommend refresh.
    """
    recommendations = []

    for entity, snapshot_at in entities_with_snapshots:
        risk = compute_decay_risk(entity, snapshot_at)
        if risk >= threshold:
            recommendations.append({
                "entity_id": entity.id,
                "entity_name": entity.name,
                "entity_type": entity.entity_type.value,
                "freshness": compute_freshness(entity, snapshot_at),
                "decay_risk": round(risk, 4),
                "last_snapshot_at": snapshot_at.isoformat() if snapshot_at else None,
            })

    # Sort by decay risk descending
    recommendations.sort(key=lambda x: x["decay_risk"], reverse=True)

    return recommendations
