"""SAP Data Generator — Generate realistic SAP-shaped test data."""
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any


def generate_metric_value(kpi_range: list[float]) -> float:
    """Generate a random value within a KPI range."""
    low, high = kpi_range
    return round(random.uniform(low, high), 4)


def generate_process_metrics(template: dict) -> dict[str, Any]:
    """Generate randomized metrics for a process template."""
    result: dict[str, Any] = {"steps": {}, "overall": {}}

    for step in template.get("steps", []):
        step_metrics = {}
        for kpi_name, kpi_range in step.get("kpis", {}).items():
            step_metrics[kpi_name] = generate_metric_value(kpi_range)
        result["steps"][step["name"]] = step_metrics

    for kpi_name, kpi_range in template.get("overall_kpis", {}).items():
        result["overall"][kpi_name] = generate_metric_value(kpi_range)

    return result


def generate_volume_data(
    num_days: int = 30,
    daily_range: tuple[int, int] = (50, 200),
) -> list[dict[str, Any]]:
    """Generate daily transaction volume data."""
    data = []
    now = datetime.now(UTC)
    for i in range(num_days):
        date = now - timedelta(days=num_days - i)
        data.append({
            "date": date.isoformat(),
            "volume": random.randint(*daily_range),
            "errors": random.randint(0, max(1, daily_range[1] // 20)),
        })
    return data


def generate_cycle_time_samples(
    n: int = 100,
    mean_hours: float = 48.0,
    std_hours: float = 12.0,
) -> list[float]:
    """Generate cycle time samples (normal distribution)."""
    return [
        max(0.1, round(random.gauss(mean_hours, std_hours), 2))
        for _ in range(n)
    ]
