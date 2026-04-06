"""CDEE Switch Hub — Lyapunov stability check.

Blueprint 2 Component: The Switch Hub.
Executes a Switch when the Imperfection violates stability criteria.

Architectural Synthesis Reference:
    "A control-theory-based switch that executes a 'Switch' whenever
    the 'Imperfection' violates 'Lyapunov Stability' criteria."

    Stability: Does the Imperfection converge to zero over time?
    If not → Switch is mathematically mandated.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StabilityResult:
    """Output of the stability analysis."""
    status: str = "stable"  # "converging" | "stable" | "oscillating" | "diverging"
    should_switch: bool = False
    urgency: str = "none"  # "none" | "warning" | "critical"
    consecutive_diverging: int = 0
    reasoning: str = ""


class SwitchHub:
    """Control-theory Switch — fires when stability is violated.

    Uses simplified Lyapunov stability analysis:
    - If the absolute error is monotonically decreasing → converging (stable)
    - If the absolute error is increasing → diverging (unstable → SWITCH)
    - If oscillating without convergence → oscillating (warning)

    Phase 1: Simple trend analysis on error magnitude.
    Phase 2: Exponential smoothing with convergence rate estimation.
    Phase 3: Full Lyapunov function V(x) analysis with proven bounds.
    """

    def __init__(self, divergence_window: int = 4) -> None:
        self._divergence_window = divergence_window

    def check_stability(
        self, error_history: list[float]
    ) -> StabilityResult:
        """Analyze error history for Lyapunov stability.

        Args:
            error_history: Time-ordered absolute error values.

        Returns:
            StabilityResult with stability classification.
        """
        if len(error_history) < 3:
            return StabilityResult(
                status="stable",
                reasoning="Insufficient data for stability analysis (need >= 3 readings)",
            )

        abs_errors = [abs(e) for e in error_history]
        recent = abs_errors[-self._divergence_window:] if len(abs_errors) >= self._divergence_window else abs_errors

        # Count consecutive increases from most recent
        consecutive_diverging = 0
        for i in range(len(recent) - 1, 0, -1):
            if recent[i] > recent[i - 1] + 0.005:  # small tolerance for noise
                consecutive_diverging += 1
            else:
                break

        # Classification
        if consecutive_diverging >= self._divergence_window - 1:
            return StabilityResult(
                status="diverging",
                should_switch=True,
                urgency="critical",
                consecutive_diverging=consecutive_diverging,
                reasoning=(
                    f"Error has been increasing for {consecutive_diverging} "
                    f"consecutive readings. System is UNSTABLE — Switch mandated."
                ),
            )

        # Check if converging: last 3+ readings show decreasing error
        converging_count = 0
        for i in range(len(recent) - 1, 0, -1):
            if recent[i] <= recent[i - 1] + 0.005:
                converging_count += 1
            else:
                break

        if converging_count >= min(3, len(recent) - 1):
            return StabilityResult(
                status="converging",
                should_switch=False,
                urgency="none",
                reasoning=f"Error converging for {converging_count} readings. Hire is effective.",
            )

        # Check for oscillation
        direction_changes = 0
        for i in range(2, len(recent)):
            prev_dir = recent[i - 1] - recent[i - 2]
            curr_dir = recent[i] - recent[i - 1]
            if (prev_dir > 0.005 and curr_dir < -0.005) or (prev_dir < -0.005 and curr_dir > 0.005):
                direction_changes += 1

        if direction_changes >= 2:
            return StabilityResult(
                status="oscillating",
                should_switch=False,
                urgency="warning",
                reasoning=(
                    f"Error oscillating ({direction_changes} direction changes). "
                    f"Hire may be partially effective but not converging."
                ),
            )

        return StabilityResult(
            status="stable",
            should_switch=False,
            urgency="none",
            reasoning="Error within stable range.",
        )
