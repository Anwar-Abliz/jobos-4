"""JobOS 4.0 — Imperfection Priority Scoring and Severity Computation.

The Imperfection is the central signal in JobOS:
- In NSAIG (Blueprint 1): Imperfection = Variational Free Energy = Surprise
- In CDEE (Blueprint 2): Imperfection = Error Signal = SP - PV

Primary scoring function: compute_vfe() — severity-based VFE score.
Legacy compute_ips() is deprecated but retained for backward compatibility.
"""
from __future__ import annotations

import warnings

from jobos.kernel.entity import EntityBase, EntityType, ImperfectionProperties


# ─── Weight Constants ────────────────────────────────────

W_BLOCKER = 3.0
W_SEVERITY = 2.0
W_FREQUENCY = 1.0
W_ENTROPY = 1.0
W_FIXABILITY = 1.0  # Inverted: hard-to-fix = higher priority


# ─── Core Functions ──────────────────────────────────────

def compute_vfe(props: ImperfectionProperties | dict) -> float:
    """Compute VFE score for an imperfection.

    Minimizing Imperfection is formally equivalent to minimizing variational
    free energy (Research Synthesis §Active Inference). The VFE score is
    severity-based: it represents the prediction error magnitude.

    For a single imperfection, VFE ≈ severity (the gap between observed
    and target). Additional terms (blocker, entropy_risk) are retained as
    weighting factors for backward compatibility with the IPS formula.

    Args:
        props: ImperfectionProperties or raw dict.

    Returns:
        VFE score as a float >= 0.
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


def compute_ips(props: ImperfectionProperties | dict) -> float:
    """Compute Imperfection Priority Score (DEPRECATED).

    .. deprecated::
        Use ``compute_vfe()`` instead. IPS and VFE are formally equivalent
        (minimizing Imperfection = minimizing variational free energy).

    IPS = 3*Blocker + 2*Severity + Frequency + EntropyRisk + (1 - Fixability)
    """
    warnings.warn(
        "compute_ips() is deprecated, use compute_vfe() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return compute_vfe(props)


def compute_severity(observed: float | None, target: float, op: str = "<=") -> float:
    """Compute severity score between 0.0 (met) and 1.0 (max gap).

    Dual interpretation:

    - **Active Inference (NSAIG)**: Severity = Prediction Error. The generative
      model (Job) predicted a target state; observed deviates from it. Severity
      quantifies the magnitude of surprise: ``|target - observed| / |target|``.

    - **Control Theory (CDEE)**: Severity = Error Signal = SP - PV. The set-point
      (target) minus the process variable (observed), normalised to [0, 1].

    Both frames converge: minimising severity ≡ minimising VFE ≡ driving the
    controlled system toward its set-point.

    Args:
        observed: Current metric value (None = missing data → max severity)
        target: Target/threshold value (set-point)
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
    """Sort imperfection entities by severity (highest first).

    Severity is the primary ranking signal — it represents the prediction
    error (VFE) for each imperfection.

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
        scored.append((props.severity, e))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = [e for _, e in scored]
    if top_n is not None:
        result = result[:top_n]
    return result


def derive_imperfection_properties(
    observed: float | None,
    target: float,
    op: str = "<=",
    metric_dimension: str = "",
) -> dict:
    """Derive imperfection properties from a metric gap.

    Used by ImperfectionService when auto-generating imperfections
    from unmet metric thresholds.

    Args:
        observed:         Current metric value (None = missing data).
        target:           Target/threshold value.
        op:               Comparison operator ("<=", ">=", etc.).
        metric_dimension: Which metric dimension (accuracy, speed, throughput).

    Returns a dict suitable for ImperfectionProperties.
    """
    severity = compute_severity(observed, target, op)
    is_blocker = severity >= 0.8 or observed is None
    entropy_risk = min(1.0, severity * 0.6)
    fixability = 0.6 if observed is not None else 0.3
    frequency = 0.8 if is_blocker else 0.5

    return {
        "severity": round(severity, 4),
        "metric_dimension": metric_dimension,
        "target_value": target,
        "observed_value": observed,
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
