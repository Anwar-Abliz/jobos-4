"""JobOS 4.0 — Imperfection Priority Scoring and Severity Computation.

The Imperfection is the central signal in JobOS:
- In NSAIG (Blueprint 1): Imperfection = Variational Free Energy = Surprise
- In CDEE (Blueprint 2): Imperfection = Error Signal = SP - PV

IPS = 3*Blocker + 2*Severity + Frequency + EntropyRisk + (1 - Fixability)
Higher IPS → more urgent → processed first by the scheduler.
"""
from __future__ import annotations

from jobos.kernel.entity import EntityBase, EntityType, ImperfectionProperties


# ─── Weight Constants ────────────────────────────────────

W_BLOCKER = 3.0
W_SEVERITY = 2.0
W_FREQUENCY = 1.0
W_ENTROPY = 1.0
W_FIXABILITY = 1.0  # Inverted: hard-to-fix = higher priority


# ─── Core Functions ──────────────────────────────────────

def compute_ips(props: ImperfectionProperties | dict) -> float:
    """Compute Imperfection Priority Score.

    IPS = 3*Blocker + 2*Severity + Frequency + EntropyRisk + (1 - Fixability)

    Accepts either a typed ImperfectionProperties or a raw dict.
    """
    if isinstance(props, dict):
        props = ImperfectionProperties.model_validate(props)

    blocker_val = 1.0 if props.is_blocker else 0.0
    return (
        W_BLOCKER * blocker_val
        + W_SEVERITY * props.severity
        + W_FREQUENCY * props.frequency
        + W_ENTROPY * props.entropy_risk
        + W_FIXABILITY * (1.0 - props.fixability)
    )


def compute_severity(observed: float | None, target: float, op: str = "<=") -> float:
    """Compute severity score between 0.0 (met) and 1.0 (max gap).

    This is the 'Prediction Error' in Active Inference terms,
    and the 'Error Signal' in Control Theory terms.

    Args:
        observed: Current metric value (None = missing data → max severity)
        target: Target/threshold value
        op: Comparison operator ("<=", ">=", "==", etc.)

    Returns:
        Severity in [0.0, 1.0]
    """
    if observed is None:
        return 1.0

    # Check if threshold is met
    met = _check_threshold(observed, target, op)
    if met:
        return 0.0

    # Compute relative gap
    if abs(target) < 1e-9:
        return min(1.0, abs(observed))

    return min(1.0, abs(target - observed) / abs(target))


def rank_imperfections(
    entities: list[EntityBase],
    top_n: int | None = None,
) -> list[EntityBase]:
    """Sort imperfection entities by IPS score (highest first).

    Args:
        entities: List of Entity:Imperfection entities
        top_n: Optional limit on results

    Returns:
        Sorted list of imperfection entities
    """
    scored = []
    for e in entities:
        if e.entity_type != EntityType.IMPERFECTION:
            continue
        props = ImperfectionProperties.model_validate(e.properties)
        ips = compute_ips(props)
        scored.append((ips, e))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = [e for _, e in scored]
    if top_n is not None:
        result = result[:top_n]
    return result


def derive_imperfection_properties(
    observed: float | None,
    target: float,
    op: str = "<=",
) -> dict:
    """Derive imperfection properties from a metric gap.

    Used by ImperfectionService when auto-generating imperfections
    from unmet metric thresholds.

    Returns a dict suitable for ImperfectionProperties.
    """
    severity = compute_severity(observed, target, op)
    is_blocker = severity >= 0.8 or observed is None
    entropy_risk = min(1.0, severity * 0.6)
    fixability = 0.6 if observed is not None else 0.3
    frequency = 0.8 if is_blocker else 0.5

    return {
        "severity": round(severity, 4),
        "frequency": frequency,
        "entropy_risk": round(entropy_risk, 4),
        "fixability": fixability,
        "is_blocker": is_blocker,
        "mode": "objective" if observed is not None else "hybrid",
        "evidence_level": "quantitative" if observed is not None else "anecdotal",
    }


# ─── Internal Helpers ────────────────────────────────────

def _check_threshold(observed: float, target: float, op: str) -> bool:
    """Check if observed value meets the threshold condition."""
    ops = {
        "<=": lambda o, t: o <= t,
        "<": lambda o, t: o < t,
        ">=": lambda o, t: o >= t,
        ">": lambda o, t: o > t,
        "==": lambda o, t: abs(o - t) < 1e-9,
        "!=": lambda o, t: abs(o - t) >= 1e-9,
    }
    fn = ops.get(op)
    if fn is None:
        return False
    try:
        return fn(observed, target)
    except TypeError:
        return False
