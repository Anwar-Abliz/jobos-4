"""JobOS.ai — T-3 DSL: Constraint Language for Agent Job Hierarchies.

Two canonical patterns derived from the JobOS.ai architecture spec:

  Pattern A (time minimization):
    "Minimize the time to [verb_noun] from [start_state] to [end_state],
     measured in [unit], target ≤ [threshold]"

  Pattern B (likelihood minimization):
    "Minimize the likelihood of [event], measured as [rate_type] in [unit],
     target ≤ [threshold]"

These DSL statements are the lingua franca between managerial job hierarchies
(T-2/T-3 outcome statements) and agent job hierarchies (executable constraints).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class T3Pattern(str, Enum):
    A_TIME = "A_time"
    B_LIKELIHOOD = "B_likelihood"


class TimeUnit(str, Enum):
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    BUSINESS_DAYS = "business_days"
    CALENDAR_DAYS = "calendar_days"
    WEEKS = "weeks"


class RateType(str, Enum):
    ERROR_RATE = "error_rate"
    FAILURE_RATE = "failure_rate"
    CHURN_RATE = "churn_rate"
    BREACH_RATE = "breach_rate"
    DEFECT_RATE = "defect_rate"
    ESCALATION_RATE = "escalation_rate"
    EXCEPTION_RATE = "exception_rate"
    MISS_RATE = "miss_rate"


class RateUnit(str, Enum):
    PERCENT = "percent"
    PER_1000 = "per_1000"
    PER_10000 = "per_10000"
    RATIO = "ratio"


@dataclass
class T3ConstraintA:
    """Pattern A — Time Minimization constraint."""
    pattern: T3Pattern = T3Pattern.A_TIME
    verb_noun: str = ""
    start_state: str = ""
    end_state: str = ""
    unit: TimeUnit = TimeUnit.HOURS
    threshold: float = 0.0
    baseline: float | None = None
    p50: float | None = None
    p95: float | None = None

    def to_statement(self) -> str:
        """Render as canonical T-3 DSL statement."""
        return (
            f"Minimize the time to {self.verb_noun} "
            f"from {self.start_state} to {self.end_state}, "
            f"measured in {self.unit.value}, "
            f"target ≤ {self.threshold}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "verb_noun": self.verb_noun,
            "start_state": self.start_state,
            "end_state": self.end_state,
            "unit": self.unit.value,
            "threshold": self.threshold,
            "baseline": self.baseline,
        }

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors: list[str] = []
        if not self.verb_noun.strip():
            errors.append("verb_noun is required")
        elif not _starts_with_verb(self.verb_noun):
            errors.append(f"verb_noun must start with an action verb: '{self.verb_noun}'")
        if not self.start_state.strip():
            errors.append("start_state is required")
        if not self.end_state.strip():
            errors.append("end_state is required")
        if self.threshold <= 0:
            errors.append("threshold must be > 0")
        if self.baseline is not None and self.baseline <= self.threshold:
            errors.append(
                f"baseline ({self.baseline}) should exceed threshold ({self.threshold}) "
                "— a constraint only makes sense if current performance is worse than target"
            )
        return errors


@dataclass
class T3ConstraintB:
    """Pattern B — Likelihood Minimization constraint."""
    pattern: T3Pattern = T3Pattern.B_LIKELIHOOD
    event: str = ""
    rate_type: RateType = RateType.ERROR_RATE
    unit: RateUnit = RateUnit.PERCENT
    threshold: float = 0.0
    baseline: float | None = None
    measurement_window: str = ""
    denominator: str = ""

    def to_statement(self) -> str:
        """Render as canonical T-3 DSL statement."""
        return (
            f"Minimize the likelihood of {self.event}, "
            f"measured as {self.rate_type.value} in {self.unit.value}, "
            f"target ≤ {self.threshold}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "event": self.event,
            "rate_type": self.rate_type.value,
            "unit": self.unit.value,
            "threshold": self.threshold,
            "baseline": self.baseline,
            "measurement_window": self.measurement_window,
            "denominator": self.denominator,
        }

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors: list[str] = []
        if not self.event.strip():
            errors.append("event is required")
        if self.threshold < 0:
            errors.append("threshold must be ≥ 0")
        if self.baseline is not None and self.baseline <= self.threshold:
            errors.append(
                f"baseline ({self.baseline}) should exceed threshold ({self.threshold})"
            )
        return errors


T3Constraint = T3ConstraintA | T3ConstraintB


# ── Threshold operator: ≤, <=, or < ─────────────────────────────────────────
_LE_OP = r"(?:≤|<=?)"

# ── Pattern A regex ──────────────────────────────────────────────────────────
# "Minimize the time to [verb_noun] from [start] to [end], measured in [unit], target ≤ [N]"
_PATTERN_A_RE = re.compile(
    r"Minimize the time to (?P<verb_noun>.+?) "
    r"from (?P<start>.+?) to (?P<end>.+?), "
    r"measured in (?P<unit>\w+(?:_\w+)?), "
    r"target\s*" + _LE_OP + r"\s*(?P<threshold>[\d.]+)",
    re.IGNORECASE,
)

# ── Pattern B regex ──────────────────────────────────────────────────────────
# "Minimize the likelihood of [event], measured as [rate_type] in [unit], target ≤ [N]"
_PATTERN_B_RE = re.compile(
    r"Minimize the likelihood of (?P<event>.+?), "
    r"measured as (?P<rate_type>\w+(?:_\w+)?) in (?P<unit>\w+(?:_\w+)?), "
    r"target\s*" + _LE_OP + r"\s*(?P<threshold>[\d.]+)",
    re.IGNORECASE,
)

_UNIT_ALIASES: dict[str, TimeUnit] = {
    "seconds": TimeUnit.SECONDS, "second": TimeUnit.SECONDS, "sec": TimeUnit.SECONDS,
    "minutes": TimeUnit.MINUTES, "minute": TimeUnit.MINUTES, "min": TimeUnit.MINUTES,
    "hours": TimeUnit.HOURS, "hour": TimeUnit.HOURS, "hr": TimeUnit.HOURS,
    "business_days": TimeUnit.BUSINESS_DAYS, "business days": TimeUnit.BUSINESS_DAYS,
    "calendar_days": TimeUnit.CALENDAR_DAYS, "calendar days": TimeUnit.CALENDAR_DAYS,
    "days": TimeUnit.CALENDAR_DAYS,
    "weeks": TimeUnit.WEEKS, "week": TimeUnit.WEEKS,
}

_RATE_UNIT_ALIASES: dict[str, RateUnit] = {
    "percent": RateUnit.PERCENT, "%": RateUnit.PERCENT,
    "per_1000": RateUnit.PER_1000, "per 1000": RateUnit.PER_1000,
    "per_10000": RateUnit.PER_10000, "per 10000": RateUnit.PER_10000,
    "ratio": RateUnit.RATIO,
}


def parse_constraint(statement: str) -> T3Constraint | None:
    """Parse a natural language T-3 DSL statement into a structured constraint.

    Returns None if the statement doesn't match either pattern.
    """
    stmt = statement.strip()

    m = _PATTERN_A_RE.search(stmt)
    if m:
        unit_str = m.group("unit").lower().replace(" ", "_")
        unit = _UNIT_ALIASES.get(unit_str)
        if unit is None:
            try:
                unit = TimeUnit(unit_str)
            except ValueError:
                unit = TimeUnit.HOURS

        return T3ConstraintA(
            verb_noun=m.group("verb_noun").strip(),
            start_state=m.group("start").strip(),
            end_state=m.group("end").strip(),
            unit=unit,
            threshold=float(m.group("threshold")),
        )

    m = _PATTERN_B_RE.search(stmt)
    if m:
        rate_str = m.group("rate_type").lower()
        unit_str = m.group("unit").lower().replace(" ", "_")

        try:
            rate_type = RateType(rate_str)
        except ValueError:
            rate_type = RateType.ERROR_RATE

        rate_unit = _RATE_UNIT_ALIASES.get(unit_str)
        if rate_unit is None:
            try:
                rate_unit = RateUnit(unit_str)
            except ValueError:
                rate_unit = RateUnit.PERCENT

        return T3ConstraintB(
            event=m.group("event").strip(),
            rate_type=rate_type,
            unit=rate_unit,
            threshold=float(m.group("threshold")),
        )

    return None


def validate_statement(statement: str) -> tuple[bool, list[str]]:
    """Validate a T-3 DSL statement string.

    Returns (is_valid, list_of_errors).
    """
    constraint = parse_constraint(statement)
    if constraint is None:
        return False, [
            "Statement does not match Pattern A or Pattern B. "
            "Expected: "
            "'Minimize the time to [verb-noun] from [start] to [end], measured in [unit], target ≤ [N]' "
            "or "
            "'Minimize the likelihood of [event], measured as [rate_type] in [unit], target ≤ [N]'"
        ]
    errors = constraint.validate()
    return len(errors) == 0, errors


def render_statement(constraint: T3Constraint) -> str:
    """Render a structured constraint as a canonical T-3 DSL statement."""
    return constraint.to_statement()


def from_dict(data: dict[str, Any]) -> T3Constraint | None:
    """Deserialize a constraint from a dict (e.g., loaded from JSON Schema instance)."""
    pattern = data.get("pattern")
    if pattern == T3Pattern.A_TIME.value:
        try:
            return T3ConstraintA(
                verb_noun=data["verb_noun"],
                start_state=data["start_state"],
                end_state=data["end_state"],
                unit=TimeUnit(data["unit"]),
                threshold=float(data["threshold"]),
                baseline=data.get("baseline"),
                p50=data.get("p50"),
                p95=data.get("p95"),
            )
        except (KeyError, ValueError):
            return None

    if pattern == T3Pattern.B_LIKELIHOOD.value:
        try:
            return T3ConstraintB(
                event=data["event"],
                rate_type=RateType(data["rate_type"]),
                unit=RateUnit(data["unit"]),
                threshold=float(data["threshold"]),
                baseline=data.get("baseline"),
                measurement_window=data.get("measurement_window", ""),
                denominator=data.get("denominator", ""),
            )
        except (KeyError, ValueError):
            return None

    return None


def infer_pattern(managerial_statement: str) -> T3Pattern:
    """Infer which T-3 DSL pattern best fits a managerial job statement.

    Heuristic rules:
    - Statements about speed, time, latency, cycle → Pattern A
    - Statements about risk, error, likelihood, compliance, prevention → Pattern B
    """
    lower = managerial_statement.lower()

    a_signals = [
        "reduce the time", "speed up", "faster", "cycle time", "latency",
        "time to", "faster time", "accelerate", "shorten", "time it takes",
    ]
    b_signals = [
        "minimize the likelihood", "reduce the risk", "prevent", "avoid",
        "error rate", "failure rate", "compliance", "eliminate", "protect from",
        "ensure no", "minimize errors", "reduce errors",
    ]

    a_score = sum(1 for s in a_signals if s in lower)
    b_score = sum(1 for s in b_signals if s in lower)

    return T3Pattern.A_TIME if a_score >= b_score else T3Pattern.B_LIKELIHOOD


def translate_t2_to_t3_dsl(
    t2_statement: str,
    importance: float = 5.0,
    baseline_time: float | None = None,
    baseline_rate: float | None = None,
) -> list[T3Constraint]:
    """Translate a T-2 managerial outcome statement to T-3 DSL constraints.

    Returns one or two constraints (Pattern A + optionally Pattern B for
    outcomes that have both a speed and a reliability dimension).

    This is a heuristic translation — always review with domain expert.
    """
    pattern = infer_pattern(t2_statement)
    results: list[T3Constraint] = []

    # Extract the core action phrase (basic heuristic)
    lower = t2_statement.lower()
    verb_noun = _extract_verb_noun(t2_statement)
    event = _extract_event(t2_statement)

    if pattern == T3Pattern.A_TIME:
        threshold = _suggest_time_threshold(importance, baseline_time)
        results.append(T3ConstraintA(
            verb_noun=verb_noun,
            start_state="task initiated",
            end_state="outcome confirmed",
            unit=_suggest_time_unit(threshold),
            threshold=threshold,
            baseline=baseline_time,
        ))
    else:
        threshold = _suggest_rate_threshold(importance, baseline_rate)
        results.append(T3ConstraintB(
            event=event,
            rate_type=RateType.ERROR_RATE,
            unit=RateUnit.PERCENT,
            threshold=threshold,
            baseline=baseline_rate,
        ))

    return results


# ── Internal helpers ─────────────────────────────────────────────────────────

_ACTION_VERBS = {
    "reduce", "increase", "improve", "minimize", "maximize", "ensure",
    "maintain", "achieve", "build", "grow", "protect", "sustain", "lead",
    "define", "execute", "monitor", "adjust", "validate", "report",
    "qualify", "process", "resolve", "onboard", "provision", "complete",
    "generate", "review", "approve", "submit", "close", "update", "create",
}


def _starts_with_verb(text: str) -> bool:
    first_word = text.strip().split()[0].lower().rstrip("s") if text.strip() else ""
    return first_word in _ACTION_VERBS or len(text.split()) >= 3


def _extract_verb_noun(statement: str) -> str:
    """Extract a verb-noun phrase from a managerial statement."""
    lower = statement.lower()
    for prefix in ["reduce the time to ", "increase the speed of ", "improve "]:
        if prefix in lower:
            idx = lower.index(prefix) + len(prefix)
            phrase = statement[idx:].split(".")[0].split(",")[0].strip()
            return phrase[:80]
    words = statement.split()
    if len(words) >= 4:
        return " ".join(words[:6]).rstrip(",.")
    return statement[:60]


def _extract_event(statement: str) -> str:
    """Extract an event phrase for Pattern B from a managerial statement."""
    lower = statement.lower()
    for prefix in ["minimize ", "reduce ", "prevent ", "avoid ", "eliminate "]:
        if lower.startswith(prefix):
            return statement[len(prefix):].rstrip(".").strip()
    return statement.rstrip(".").strip()


def _suggest_time_threshold(importance: float, baseline: float | None) -> float:
    """Suggest a reasonable time threshold given importance and current baseline."""
    if baseline:
        return round(baseline * (1 - (importance / 20)), 1)  # ~25-50% improvement
    # Rough defaults by importance
    if importance >= 8:
        return 4.0  # hours
    if importance >= 6:
        return 24.0
    return 48.0


def _suggest_time_unit(threshold: float) -> TimeUnit:
    if threshold <= 60:
        return TimeUnit.MINUTES
    if threshold <= 168:
        return TimeUnit.HOURS
    return TimeUnit.BUSINESS_DAYS


def _suggest_rate_threshold(importance: float, baseline: float | None) -> float:
    """Suggest a reasonable rate threshold."""
    if baseline:
        return round(baseline * 0.5, 2)  # 50% reduction
    if importance >= 8:
        return 0.5
    if importance >= 6:
        return 1.0
    return 2.0
