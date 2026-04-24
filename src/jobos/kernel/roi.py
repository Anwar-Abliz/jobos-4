"""JobOS 4.0 — ROI Estimation Model.

Maps metric improvements from baseline comparisons to estimated
business value.  Phase 1 uses a simple linear value map.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ROIEstimate(BaseModel):
    """Estimated return on investment for a single metric improvement."""
    metric_name: str
    baseline_value: float
    current_value: float
    improvement: float
    improvement_pct: float
    estimated_value: float
    currency: str = "USD"
    confidence: float = 0.5
    assumptions: list[str] = Field(default_factory=list)


def compute_roi(
    baselines: dict[str, float],
    current: dict[str, float],
    value_map: dict[str, float],
) -> list[ROIEstimate]:
    """Compute ROI estimates from baseline-to-current metric deltas.

    Args:
        baselines: {metric_name: baseline_value}
        current: {metric_name: current_value}
        value_map: {metric_name: monetary_value_per_unit_improvement}

    Returns:
        List of ROIEstimate for each metric that has a value mapping.
    """
    estimates: list[ROIEstimate] = []

    for metric, base_val in baselines.items():
        curr_val = current.get(metric)
        unit_value = value_map.get(metric)
        if curr_val is None or unit_value is None:
            continue

        improvement = curr_val - base_val
        improvement_pct = (
            (improvement / abs(base_val)) * 100.0
            if abs(base_val) > 1e-9 else 0.0
        )
        estimated_value = improvement * unit_value

        estimates.append(ROIEstimate(
            metric_name=metric,
            baseline_value=base_val,
            current_value=curr_val,
            improvement=round(improvement, 4),
            improvement_pct=round(improvement_pct, 2),
            estimated_value=round(estimated_value, 2),
            assumptions=[
                f"Linear value: ${unit_value}/unit for {metric}",
                "Assumes improvement is sustained",
            ],
        ))

    return estimates


def compute_total_roi(estimates: list[ROIEstimate]) -> dict[str, Any]:
    """Summarize total ROI across all metric estimates."""
    total = sum(e.estimated_value for e in estimates)
    avg_confidence = (
        sum(e.confidence for e in estimates) / len(estimates)
        if estimates else 0.0
    )
    return {
        "total_estimated_value": round(total, 2),
        "currency": estimates[0].currency if estimates else "USD",
        "metric_count": len(estimates),
        "average_confidence": round(avg_confidence, 2),
        "estimates": [e.model_dump() for e in estimates],
    }
