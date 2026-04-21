"""JobOS 4.0 — ThresholdEvaluator: Stateful wrapper around switch_evaluator.

Provides a class-based interface for configuring per-metric thresholds
with hysteresis and delegating to the existing ``switch_evaluator()``
function.  All existing logic is preserved — this is a convenience layer.

Phase 2: replace hard thresholds with learned bounds (online regression).
"""
from __future__ import annotations

from typing import Any

from jobos.engines.switch_evaluator import SwitchDecision, switch_evaluator


class ThresholdEvaluator:
    """Stateful metric threshold evaluator with configurable hysteresis.

    Wraps ``switch_evaluator()`` while managing per-job hysteresis state
    and per-metric bounds configuration internally.
    """

    def __init__(self, *, default_hysteresis: float = 0.05) -> None:
        self._thresholds: dict[str, dict[str, float | None]] = {}
        self._default_hysteresis = default_hysteresis
        self._state: dict[str, dict[str, Any]] = {}  # per-job state

    # ── Configuration ────────────────────────────────────

    def configure_threshold(
        self,
        metric_name: str,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
        hysteresis_band: float | None = None,
    ) -> None:
        """Set bounds and optional hysteresis for a single metric."""
        self._thresholds[metric_name] = {
            "lower": lower_bound,
            "upper": upper_bound,
            "hysteresis": hysteresis_band,
        }

    def configure_from_bounds(
        self,
        bounds: dict[str, tuple[float | None, float | None]],
    ) -> None:
        """Bulk-configure thresholds from a bounds dict.

        Args:
            bounds: ``{metric_name: (lower, upper)}``
        """
        for metric_name, (lower, upper) in bounds.items():
            self.configure_threshold(metric_name, lower_bound=lower, upper_bound=upper)

    def get_thresholds(self) -> dict[str, dict[str, float | None]]:
        """Return a copy of the current threshold configuration."""
        return dict(self._thresholds)

    # ── Evaluation ───────────────────────────────────────

    async def evaluate(
        self,
        job_id: str,
        metrics: dict[str, float],
        context_delta: dict[str, float] | None = None,
    ) -> SwitchDecision:
        """Evaluate metrics against configured thresholds.

        Manages per-job hysteresis state automatically.  Delegates to
        ``switch_evaluator()`` for the actual decision logic.
        """
        # Build bounds in the format switch_evaluator expects
        bounds: dict[str, tuple[float, float | None]] = {}
        hysteresis = self._default_hysteresis

        for metric_name, cfg in self._thresholds.items():
            lower = cfg.get("lower")
            upper = cfg.get("upper")
            if lower is not None or upper is not None:
                bounds[metric_name] = (
                    lower if lower is not None else 0.0,
                    upper,
                )
            per_metric_hyst = cfg.get("hysteresis")
            if per_metric_hyst is not None:
                hysteresis = per_metric_hyst

        # Get or create per-job state
        if job_id not in self._state:
            self._state[job_id] = {}

        return await switch_evaluator(
            job_id=job_id,
            latest_metrics=metrics,
            context_delta=context_delta or {},
            bounds=bounds,
            hysteresis_band=hysteresis,
            _state=self._state[job_id],
        )

    # ── State management ─────────────────────────────────

    def reset_state(self, job_id: str) -> None:
        """Clear hysteresis state for a specific job."""
        self._state.pop(job_id, None)
