"""JobOS 4.0 — Axiom 7: The Switch Evaluator (Phase 1 Heuristic).

Axiom 7: "Hire/Fire justified by context change OR metric breach."

This is a pure heuristic implementation (Phase 1). No variational inference,
no pymdp, no dowhy. The SwitchEvaluator answers: should we hire, fire, or
leave the current executor unchanged?

Phase 2: Replace hysteresis band with learned thresholds (online regression).
Phase 3: Replace with NSAIG EFE policy selection + CDEE stability check.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

logger = structlog.get_logger(__name__)


# ─── Decision Type ───────────────────────────────────────

@dataclass
class SwitchDecision:
    """The output of a Switch evaluation.

    action:       HIRE (need new executor), FIRE (terminate current), NONE (stable)
    reason:       Human-readable explanation
    details:      Structured metric details for audit trail
    triggered_by: What caused this decision
    """
    action: Literal["HIRE", "FIRE", "NONE"]
    reason: str
    details: dict[str, Any] = field(default_factory=dict)
    triggered_by: Literal["context_change", "metric_breach", "both", "none"] = "none"


# ─── Switch Evaluator ────────────────────────────────────

async def switch_evaluator(
    job_id: str,
    latest_metrics: dict[str, float],
    context_delta: dict[str, float],
    bounds: dict[str, tuple[float, float | None]],
    *,
    context_threshold: float = 0.15,
    hysteresis_band: float = 0.05,
    _state: dict[str, Any] | None = None,
) -> SwitchDecision:
    """Axiom 7 heuristic Switch controller.

    Determines if a Hire/Fire action is warranted based on:
    1. Context shift magnitude exceeding a threshold
    2. Metric values outside defined bounds (with hysteresis dead-band)

    Args:
        job_id:            The Job being evaluated.
        latest_metrics:    Current metric readings, e.g. {'accuracy': 0.7, 'speed': 120}.
        context_delta:     Vector of context weight changes (dimension → delta magnitude).
        bounds:            Per-metric (lower, upper) bounds. Use None for open-ended.
                           e.g. {'accuracy': (0.8, 1.0), 'speed': (0, 200), 'throughput': (30, None)}
        context_threshold: L2-norm of context_delta that triggers a context_change event.
        hysteresis_band:   Dead-band around bounds to prevent oscillating HIRE/FIRE cycles.
                           A metric at lower_bound - hysteresis_band triggers breach, but
                           once FIRE is issued, the metric must recover above lower_bound
                           before a new FIRE is emitted (suppressed in _state).
        _state:            Caller-managed mutable state dict for hysteresis tracking.
                           Keys: 'last_action' (str), 'breach_metrics' (set[str]).

    Returns:
        SwitchDecision with action, reason, and details.
    """
    if _state is None:
        _state = {}

    last_action: str = _state.get("last_action", "NONE")
    previously_breached: set[str] = _state.get("breach_metrics", set())

    # ── Step 1: Context change detection ─────────────────
    context_change = False
    context_norm = 0.0
    if context_delta:
        context_norm = math.sqrt(sum(v * v for v in context_delta.values()))
        context_change = context_norm > context_threshold

    # ── Step 2: Metric breach detection ──────────────────
    breached_metrics: dict[str, str] = {}  # metric_name → violation description

    for metric_name, value in latest_metrics.items():
        if metric_name not in bounds:
            continue

        lower, upper = bounds[metric_name]

        lower_limit = (lower - hysteresis_band) if lower is not None else None
        upper_limit = (upper + hysteresis_band) if upper is not None else None

        # Check lower bound breach
        if lower_limit is not None and value < lower_limit:
            # Hysteresis: if we already fired for this metric and it's still below
            # the raw bound (not just hysteresis limit), suppress the re-fire
            if last_action == "FIRE" and metric_name in previously_breached:
                # Check if it's improving (still below bound but above hysteresis limit)
                if lower is not None and value > lower_limit and value < lower:
                    # Still in dead-band — suppress
                    continue
                # Still fully below — continue to breach
            breached_metrics[metric_name] = (
                f"{metric_name}={value:.4f} below lower bound "
                f"{lower:.4f} (with hysteresis: {lower_limit:.4f})"
            )

        # Check upper bound breach
        elif upper_limit is not None and value > upper_limit:
            if last_action == "FIRE" and metric_name in previously_breached:
                if upper is not None and value < upper_limit and value > upper:
                    continue
            breached_metrics[metric_name] = (
                f"{metric_name}={value:.4f} above upper bound "
                f"{upper:.4f} (with hysteresis: {upper_limit:.4f})"
            )

    metric_breach = len(breached_metrics) > 0

    # ── Step 3: Determine triggered_by ───────────────────
    if context_change and metric_breach:
        triggered_by: Literal["context_change", "metric_breach", "both", "none"] = "both"
    elif context_change:
        triggered_by = "context_change"
    elif metric_breach:
        triggered_by = "metric_breach"
    else:
        triggered_by = "none"

    # ── Step 4: Compose decision ─────────────────────────
    if triggered_by == "none":
        decision = SwitchDecision(
            action="NONE",
            reason="All metrics within bounds; context stable.",
            details={
                "context_norm": context_norm,
                "context_threshold": context_threshold,
                "metrics_evaluated": list(latest_metrics.keys()),
            },
            triggered_by="none",
        )
    elif triggered_by == "context_change":
        decision = SwitchDecision(
            action="HIRE",
            reason=(
                f"Context shift detected (norm={context_norm:.4f} > "
                f"threshold={context_threshold}). New executor may be better suited."
            ),
            details={
                "context_norm": context_norm,
                "context_threshold": context_threshold,
                "context_delta": context_delta,
            },
            triggered_by="context_change",
        )
    elif triggered_by == "metric_breach":
        reason_parts = [f"Metric breach(es) detected:"]
        for name, desc in breached_metrics.items():
            reason_parts.append(f"  • {desc}")
        decision = SwitchDecision(
            action="FIRE",
            reason="\n".join(reason_parts),
            details={
                "breached_metrics": breached_metrics,
                "all_metrics": latest_metrics,
                "bounds": {k: list(v) for k, v in bounds.items()},
                "hysteresis_band": hysteresis_band,
            },
            triggered_by="metric_breach",
        )
    else:  # both
        reason_parts = [
            f"Context shift (norm={context_norm:.4f}) AND metric breach(es):",
        ]
        for name, desc in breached_metrics.items():
            reason_parts.append(f"  • {desc}")
        decision = SwitchDecision(
            action="FIRE",
            reason="\n".join(reason_parts),
            details={
                "context_norm": context_norm,
                "context_threshold": context_threshold,
                "context_delta": context_delta,
                "breached_metrics": breached_metrics,
                "all_metrics": latest_metrics,
                "bounds": {k: list(v) for k, v in bounds.items()},
                "hysteresis_band": hysteresis_band,
            },
            triggered_by="both",
        )

    # ── Step 5: Update caller-managed state ──────────────
    _state["last_action"] = decision.action
    _state["breach_metrics"] = set(breached_metrics.keys())

    # ── Step 6: Emit structured log ──────────────────────
    if decision.action != "NONE":
        logger.info(
            "switch_evaluator.fired",
            job_id=job_id,
            action=decision.action,
            triggered_by=decision.triggered_by,
            breached_metrics=list(breached_metrics.keys()),
            context_norm=round(context_norm, 4),
        )
    else:
        logger.debug(
            "switch_evaluator.stable",
            job_id=job_id,
            context_norm=round(context_norm, 4),
        )

    return decision
