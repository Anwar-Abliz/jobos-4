"""CDEE Dynamic Controller — State-space feedback controller.

Blueprint 2 Component: The Dynamic Controller.
Models each Job as a state-space system where Imperfection is the
error signal and Hiring is the control action.

Phase 1: PID-inspired control with error signal trend analysis.
Phase 2: Full PID with tuned gains from metric history.
Phase 3: State-space estimation with Kalman filtering.

Architectural Synthesis Reference:
    "A feedback controller that models each 'Job' as a state-space
    system. ẋ(t) = Ax(t) + Bu(t), y(t) = Cx(t)
    Where x = job state, u = hire input, y = metric output.
    The error signal e = target - observed IS the Imperfection."
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ControlSignal:
    """Output of the controller analysis."""
    error_current: float = 0.0
    error_trend: str = "stable"  # "converging" | "stable" | "diverging"
    proportional: float = 0.0   # P term: current error magnitude
    integral: float = 0.0       # I term: accumulated error (persistence)
    derivative: float = 0.0     # D term: rate of change (getting worse?)
    control_action: float = 0.0  # Combined PID output
    is_controllable: bool = True
    reasoning: str = ""


@dataclass
class ControllabilityResult:
    """Whether a Hire can influence a Job's Metric."""
    is_controllable: bool = True
    evidence_count: int = 0
    correlation: float = 0.0  # Hire-Metric correlation
    reasoning: str = ""


class DynamicController:
    """State-space feedback controller for Job progress.

    The Imperfection IS the error signal: e = SP - PV
    (Set-Point minus Process Variable).

    Phase 1: Discrete PID-like analysis.
        P = current error (how bad is the imperfection now?)
        I = sum of past errors (has it been bad for a long time?)
        D = error derivative (is it getting better or worse?)

    Phase 2: Tuned PID gains from historical metric data.
    Phase 3: Full state-space model with Kalman filter for
             state estimation under noisy observations.
    """

    def __init__(
        self,
        kp: float = 1.0,   # Proportional gain
        ki: float = 0.1,   # Integral gain
        kd: float = 0.5,   # Derivative gain
    ) -> None:
        self._kp = kp
        self._ki = ki
        self._kd = kd

    def compute_error_signal(
        self, target: float, observed: float
    ) -> float:
        """The Imperfection as control error: SP - PV.

        Positive error = below target (for 'maximize' metrics).
        The sign depends on the metric direction but severity
        is always the absolute value.
        """
        return target - observed

    def analyze(
        self,
        error_history: list[float],
        dt: float = 1.0,
    ) -> ControlSignal:
        """Compute PID control signal from error history.

        Args:
            error_history: Time-ordered error values (oldest first).
                           Each value = target - observed at that time.
            dt: Time step between readings (normalized to 1.0).

        Returns:
            ControlSignal with P/I/D components and trend analysis.
        """
        if not error_history:
            return ControlSignal(reasoning="No error history available")

        current = error_history[-1]

        # Proportional: current error magnitude
        p_term = self._kp * current

        # Integral: sum of all past errors (persistence / entropy_risk)
        i_term = self._ki * sum(error_history) * dt

        # Derivative: rate of change (is it getting better or worse?)
        if len(error_history) >= 2:
            d_term = self._kd * (error_history[-1] - error_history[-2]) / dt
        else:
            d_term = 0.0

        control_action = p_term + i_term + d_term
        trend = self._compute_trend(error_history)

        return ControlSignal(
            error_current=round(current, 4),
            error_trend=trend,
            proportional=round(p_term, 4),
            integral=round(i_term, 4),
            derivative=round(d_term, 4),
            control_action=round(control_action, 4),
            is_controllable=True,  # Phase 1: assume controllable
            reasoning=(
                f"Error={current:.3f}, trend={trend}. "
                f"P={p_term:.3f} I={i_term:.3f} D={d_term:.3f}"
            ),
        )

    def check_controllability(
        self,
        hire_dates: list[str],
        error_before_hire: list[float],
        error_after_hire: list[float],
    ) -> ControllabilityResult:
        """Check if a Hire can actually influence the Job's Metric.

        Phase 1: Simple before/after comparison.
        Phase 2: Granger causality test.
        Phase 3: Full controllability matrix rank test.

        If not controllable, Axiom 6 mandates a Switch.
        """
        if not error_before_hire or not error_after_hire:
            return ControllabilityResult(
                is_controllable=True,
                evidence_count=0,
                reasoning="Insufficient data to assess controllability",
            )

        avg_before = sum(abs(e) for e in error_before_hire) / len(error_before_hire)
        avg_after = sum(abs(e) for e in error_after_hire) / len(error_after_hire)

        if avg_before < 1e-9:
            correlation = 0.0
        else:
            correlation = (avg_before - avg_after) / avg_before

        is_controllable = correlation > -0.1  # Allow slight noise

        return ControllabilityResult(
            is_controllable=is_controllable,
            evidence_count=len(error_before_hire) + len(error_after_hire),
            correlation=round(correlation, 4),
            reasoning=(
                f"Error {'decreased' if correlation > 0 else 'increased'} "
                f"by {abs(correlation)*100:.1f}% after hire. "
                f"{'Controllable' if is_controllable else 'NOT controllable — Switch mandated'}."
            ),
        )

    def _compute_trend(self, history: list[float]) -> str:
        """Determine error convergence from recent history."""
        if len(history) < 3:
            return "stable"

        recent = history[-5:] if len(history) >= 5 else history
        abs_errors = [abs(e) for e in recent]

        # Check if absolute errors are decreasing
        decreasing = all(
            abs_errors[i] >= abs_errors[i + 1] - 0.01
            for i in range(len(abs_errors) - 1)
        )
        increasing = all(
            abs_errors[i] <= abs_errors[i + 1] + 0.01
            for i in range(len(abs_errors) - 1)
        )

        if decreasing and not increasing:
            return "converging"
        elif increasing and not decreasing:
            return "diverging"
        else:
            return "stable"
