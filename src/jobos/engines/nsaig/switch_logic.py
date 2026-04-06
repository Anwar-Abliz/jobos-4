"""NSAIG Switch Logic — VFE threshold monitoring.

Blueprint 1 Component: The Switch Logic.
Monitors Variational Free Energy over time. If VFE stays above
threshold τ for a sustained window, the current Hire is ineffective
and must be Switched.

Architectural Synthesis Reference:
    "A binary activation unit that monitors the VFE F. If F > τ
    for a sustained period, the link e_uv is pruned, and the
    Belief Engine is updated to search for a new Entity."
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SwitchRecommendation:
    """Output of the switch analysis."""
    should_switch: bool = False
    urgency: str = "none"  # "none" | "warning" | "critical"
    vfe_current: float = 0.0
    vfe_trend: str = "stable"  # "decreasing" | "stable" | "increasing"
    sustained_above_threshold: int = 0  # number of readings above τ
    reasoning: str = ""


class SwitchLogic:
    """VFE threshold monitor — triggers Fire decisions.

    Phase 1: Simple moving-window analysis.
    Phase 2: Trend detection with derivative analysis.
    Phase 3: Predictive switch using EFE forecasting.
    """

    def __init__(
        self,
        threshold: float = 0.6,
        window_size: int = 5,
    ) -> None:
        self._threshold = threshold
        self._window_size = window_size

    def analyze(self, vfe_history: list[float]) -> SwitchRecommendation:
        """Analyze VFE history to determine if a Switch is needed.

        Args:
            vfe_history: Time-ordered VFE readings (oldest first).

        Returns:
            SwitchRecommendation with verdict and reasoning.
        """
        if not vfe_history:
            return SwitchRecommendation(reasoning="No VFE data available")

        current = vfe_history[-1]
        trend = self._compute_trend(vfe_history)

        # Count consecutive readings above threshold (from most recent)
        sustained = 0
        for v in reversed(vfe_history):
            if v > self._threshold:
                sustained += 1
            else:
                break

        # Decision logic
        if sustained >= self._window_size:
            return SwitchRecommendation(
                should_switch=True,
                urgency="critical",
                vfe_current=round(current, 4),
                vfe_trend=trend,
                sustained_above_threshold=sustained,
                reasoning=(
                    f"VFE has been above threshold ({self._threshold}) "
                    f"for {sustained} consecutive readings. "
                    f"Current hire is ineffective — Switch recommended."
                ),
            )
        elif sustained >= self._window_size // 2:
            return SwitchRecommendation(
                should_switch=False,
                urgency="warning",
                vfe_current=round(current, 4),
                vfe_trend=trend,
                sustained_above_threshold=sustained,
                reasoning=(
                    f"VFE has been above threshold for {sustained} readings "
                    f"(switch at {self._window_size}). Monitor closely."
                ),
            )
        else:
            return SwitchRecommendation(
                should_switch=False,
                urgency="none",
                vfe_current=round(current, 4),
                vfe_trend=trend,
                sustained_above_threshold=sustained,
                reasoning="VFE within acceptable range.",
            )

    def _compute_trend(self, history: list[float]) -> str:
        """Simple trend detection from the last few readings."""
        if len(history) < 3:
            return "stable"

        recent = history[-3:]
        diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
        avg_diff = sum(diffs) / len(diffs)

        if avg_diff < -0.02:
            return "decreasing"
        elif avg_diff > 0.02:
            return "increasing"
        else:
            return "stable"
