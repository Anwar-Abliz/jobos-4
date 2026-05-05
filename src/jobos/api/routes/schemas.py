"""JobOS.ai — Hierarchy Schema API Routes.

Endpoints for:
- POST /api/schemas/t3/validate   — validate a T-3 DSL statement
- POST /api/schemas/t3/parse      — parse DSL statement to structured constraint
- POST /api/schemas/t3/render     — render structured constraint to DSL statement
- POST /api/schemas/crosswalk/translate — auto-translate managerial T-2/T-3 to T-3 DSL
- POST /api/schemas/hierarchy/classify-2d — place a managerial job on the 2D orthogonal model
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobos.kernel.t3_dsl import (
    T3ConstraintA,
    T3ConstraintB,
    TimeUnit,
    RateType,
    RateUnit,
    T3Pattern,
    from_dict,
    infer_pattern,
    parse_constraint,
    render_statement,
    translate_t2_to_t3_dsl,
    validate_statement,
)

router = APIRouter()


class T3ValidateIn(BaseModel):
    statement: str


class T3ParseIn(BaseModel):
    statement: str


class T3RenderIn(BaseModel):
    constraint: dict[str, Any]


class CrosswalkTranslateIn(BaseModel):
    statement: str
    tier: str = "T2_core"  # T1_strategic, T2_core, T3_execution
    importance: float = 5.0
    baseline_time: float | None = None
    baseline_rate: float | None = None


class Classify2DIn(BaseModel):
    statement: str
    tier: str = "T2_core"
    executor_type: str = "HUMAN"


@router.post("/schemas/t3/validate")
def validate_t3(req: T3ValidateIn) -> dict[str, Any]:
    """Validate a T-3 DSL statement against Pattern A and Pattern B rules.

    Returns is_valid, detected pattern, and any validation errors.
    """
    is_valid, errors = validate_statement(req.statement)
    constraint = parse_constraint(req.statement)

    return {
        "is_valid": is_valid,
        "errors": errors,
        "detected_pattern": constraint.pattern.value if constraint else None,
        "statement": req.statement,
    }


@router.post("/schemas/t3/parse")
def parse_t3(req: T3ParseIn) -> dict[str, Any]:
    """Parse a T-3 DSL statement to a structured constraint object."""
    constraint = parse_constraint(req.statement)
    if constraint is None:
        raise HTTPException(
            422,
            "Statement does not match Pattern A or Pattern B. "
            "Use GET /schemas/t3/validate to see expected format.",
        )
    errors = constraint.validate()
    return {
        "pattern": constraint.pattern.value,
        "constraint": constraint.to_dict(),
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
        "canonical_statement": constraint.to_statement(),
    }


@router.post("/schemas/t3/render")
def render_t3(req: T3RenderIn) -> dict[str, Any]:
    """Render a structured constraint dict to a canonical T-3 DSL statement."""
    constraint = from_dict(req.constraint)
    if constraint is None:
        raise HTTPException(
            422,
            "Invalid constraint dict. Must have 'pattern': 'A_time' or 'B_likelihood' "
            "with all required fields.",
        )
    errors = constraint.validate()
    return {
        "statement": constraint.to_statement(),
        "pattern": constraint.pattern.value,
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
    }


@router.post("/schemas/crosswalk/translate")
def crosswalk_translate(req: CrosswalkTranslateIn) -> dict[str, Any]:
    """Auto-translate a managerial job statement to T-3 DSL constraint(s).

    Uses heuristic pattern inference — always review with domain expert.
    Returns one or two constraints (Pattern A + optionally Pattern B).
    """
    inferred = infer_pattern(req.statement)

    constraints = translate_t2_to_t3_dsl(
        req.statement,
        importance=req.importance,
        baseline_time=req.baseline_time,
        baseline_rate=req.baseline_rate,
    )

    results = []
    for c in constraints:
        errors = c.validate()
        results.append({
            "pattern": c.pattern.value,
            "statement": c.to_statement(),
            "constraint": c.to_dict(),
            "is_valid": len(errors) == 0,
            "validation_errors": errors,
        })

    return {
        "managerial_statement": req.statement,
        "tier": req.tier,
        "inferred_pattern": inferred.value,
        "translation_count": len(results),
        "translations": results,
        "translation_note": (
            "Heuristic translation. Verb-noun, start_state, and end_state "
            "may need refinement by a domain expert. "
            "Threshold is derived from importance score and baseline if provided."
        ),
    }


@router.post("/schemas/hierarchy/classify-2d")
def classify_2d(req: Classify2DIn) -> dict[str, Any]:
    """Place a managerial job on the 2D orthogonal model.

    X-axis: Functional abstraction (1=strategic/WHY, 5=operational/HOW)
    Y-axis: Experience intensity (1=purely functional, 5=highly experiential)

    Heuristic: based on tier, key verbs, and experiential language.
    """
    tier_x_map = {
        "T1_strategic": 1.5,
        "T2_core": 2.5,
        "T3_execution": 3.5,
        "T4_micro": 4.5,
    }
    x = tier_x_map.get(req.tier, 3.0)

    lower = req.statement.lower()
    y = _score_experience_intensity(lower, req.executor_type)

    quadrant = _get_quadrant(x, y)

    return {
        "statement": req.statement,
        "tier": req.tier,
        "placement": {
            "x": round(x, 1),
            "y": round(y, 1),
            "quadrant": quadrant,
        },
        "notes": (
            "X-axis (functional abstraction) is derived from tier. "
            "Y-axis (experience intensity) is heuristic — review for HUMAN executors."
        ),
    }


@router.get("/schemas/t3/patterns")
def get_t3_patterns() -> dict[str, Any]:
    """Return the canonical T-3 DSL pattern definitions with examples."""
    return {
        "patterns": [
            {
                "id": "A_time",
                "name": "Pattern A — Time Minimization",
                "template": "Minimize the time to [verb_noun] from [start_state] to [end_state], measured in [unit], target ≤ [threshold]",
                "units": [u.value for u in TimeUnit],
                "examples": [
                    "Minimize the time to qualify a lead from first contact to CRM stage updated, measured in hours, target ≤ 4",
                    "Minimize the time to process a purchase order from PO submitted to supplier notified, measured in business_days, target ≤ 2",
                    "Minimize the time to onboard a new user from account created to first feature used, measured in calendar_days, target ≤ 7",
                ],
            },
            {
                "id": "B_likelihood",
                "name": "Pattern B — Likelihood Minimization",
                "template": "Minimize the likelihood of [event], measured as [rate_type] in [unit], target ≤ [threshold]",
                "rate_types": [r.value for r in RateType],
                "units": [u.value for u in RateUnit],
                "examples": [
                    "Minimize the likelihood of invoice processing error due to PO mismatch, measured as error_rate in percent, target ≤ 0.5",
                    "Minimize the likelihood of SLA breach on P1 tickets, measured as breach_rate in per_1000, target ≤ 5",
                    "Minimize the likelihood of customer churn within 90 days of sign-up, measured as churn_rate in percent, target ≤ 3",
                ],
            },
        ]
    }


# ── Internal helpers ─────────────────────────────────────────────────────────

_EXPERIENCE_SIGNALS = [
    "feel", "to be", "recognized", "trusted", "confident", "satisfied",
    "empowered", "respected", "free from", "proud", "secure",
    "comfortable", "motivated", "engaged", "appreciated",
]

_FUNCTIONAL_SIGNALS = [
    "reduce", "increase", "minimize", "maximize", "ensure", "define",
    "process", "validate", "compute", "generate", "report", "execute",
    "monitor", "adjust", "automate", "measure",
]


def _score_experience_intensity(lower: str, executor_type: str) -> float:
    exp_score = sum(1 for s in _EXPERIENCE_SIGNALS if s in lower)
    func_score = sum(1 for s in _FUNCTIONAL_SIGNALS if s in lower)

    # AI executors are always functional
    if executor_type == "AI":
        return 1.0 + min(exp_score * 0.2, 0.5)

    if exp_score == 0 and func_score == 0:
        return 2.5
    if exp_score == 0:
        return 1.5
    ratio = exp_score / max(exp_score + func_score, 1)
    return round(1.0 + ratio * 4.0, 1)


def _get_quadrant(x: float, y: float) -> str:
    strategic = x <= 2.5
    experiential = y >= 3.0
    if strategic and experiential:
        return "strategic-experiential"
    if strategic:
        return "strategic-functional"
    if experiential:
        return "operational-experiential"
    return "operational-functional"
