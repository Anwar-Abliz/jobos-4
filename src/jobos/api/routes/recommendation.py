"""JobOS 4.0 — Preliminary Recommendation Route.

POST /api/recommendation/preliminary — LLM-powered preliminary switch recommendation.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from jobos.api.deps import _llm, get_graph_port
from jobos.kernel.entity import EntityBase

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Request / Response Models ───────────────────────────

class OutcomesIn(BaseModel):
    experience_markers: dict[str, list[str]] = Field(default_factory=dict)
    metrics: list[dict[str, str]] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    job_id: str = Field(..., description="The target job entity ID")
    outcomes: OutcomesIn = Field(default_factory=OutcomesIn)


class RecommendationFactor(BaseModel):
    factor: str
    explanation: str = ""
    impact: str  # "positive" | "negative"
    weight: float


class RecommendationResponse(BaseModel):
    job_id: str
    recommendation: str  # "switch_to_ai" | "keep_human" | "needs_more_data"
    confidence: float
    reasoning: str
    evaluation_method: str = "heuristic_template"
    evaluation_criteria: list[str] = Field(default_factory=list)
    factors: list[RecommendationFactor] = Field(default_factory=list)


# ─── Route ───────────────────────────────────────────────

@router.post("/recommendation/preliminary", response_model=RecommendationResponse)
async def get_preliminary_recommendation(
    body: RecommendationRequest,
) -> RecommendationResponse:
    """Analyze a target job and provide a preliminary hire/switch recommendation."""
    entity: EntityBase | None = None
    children: list[EntityBase] = []

    try:
        graph = get_graph_port()
        entity = await graph.get_entity(body.job_id)
        if entity:
            children = await graph.get_neighbors(
                body.job_id, edge_type="PART_OF", direction="incoming"
            )
    except Exception as e:
        logger.warning("Could not fetch job data for recommendation: %s", e)

    # LLM-powered analysis
    if _llm is not None:
        try:
            return await _analyze_with_llm(body, entity, children)
        except Exception as e:
            logger.warning("LLM recommendation failed, using fallback: %s", e)

    # Fallback: template-based heuristic
    return _template_recommendation(body, entity, children)


async def _analyze_with_llm(
    body: RecommendationRequest,
    entity: EntityBase | None,
    children: list[EntityBase],
) -> RecommendationResponse:
    """Use LLM to generate a preliminary recommendation."""
    job_statement = entity.statement if entity else "Unknown"
    job_tier = entity.properties.get("tier", "Unknown") if entity else "Unknown"
    job_category = entity.properties.get("category", "") if entity else ""
    num_children = len(children)

    metrics_desc = ""
    if body.outcomes.metrics:
        metrics_desc = "\n".join(
            f"- {m.get('statement', m.get('name', '?'))}: target {m.get('target', '?')}"
            for m in body.outcomes.metrics
        )
    else:
        metrics_desc = "No metrics defined yet."

    exp_desc = ""
    feel = body.outcomes.experience_markers.get("feel_markers", [])
    to_be = body.outcomes.experience_markers.get("to_be_markers", [])
    if feel or to_be:
        exp_desc = f"Feel markers: {', '.join(feel)}. To-Be markers: {', '.join(to_be)}."
    else:
        exp_desc = "No experience markers defined."

    system_prompt = (
        "You are a job analysis engine. Analyze jobs and recommend whether "
        "they should be automated (switch_to_ai), kept as human tasks "
        "(keep_human), or if more data is needed (needs_more_data). "
        "Respond in valid JSON only."
    )

    user_prompt = f"""Analyze this job and provide a recommendation.

Job: {job_statement}
Tier: {job_tier}
Category: {job_category}
Executor type: {entity.properties.get("executor_type", "HUMAN") if entity else "HUMAN"}
Number of sub-jobs: {num_children}
Defined metrics: {metrics_desc}
Experience markers: {exp_desc}

Respond in this exact JSON format:
{{
  "recommendation": "switch_to_ai" or "keep_human" or "needs_more_data",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentence explanation",
  "evaluation_criteria": ["criterion 1", "criterion 2", "criterion 3"],
  "factors": [
    {{
      "factor": "short factor name",
      "explanation": "1-sentence explanation of why this matters",
      "impact": "positive" or "negative",
      "weight": 0.0 to 1.0
    }}
  ]
}}

Consider:
- Repetitive execution steps favor AI automation
- High contextual variance favors human execution
- Low-tier (T3/T4) jobs are more likely automation candidates
- Jobs with clear metrics are easier to evaluate
- Experience markers suggest human-centric value

For evaluation_criteria, list what aspects you analyzed (e.g., "Job tier and complexity",
"Defined metrics coverage", "Experience marker analysis", "Sub-job decomposition pattern")."""

    assert _llm is not None
    parsed = await _llm.complete_json(system_prompt, user_prompt, max_tokens=1000)

    return RecommendationResponse(
        job_id=body.job_id,
        recommendation=parsed.get("recommendation", "needs_more_data"),
        confidence=min(max(float(parsed.get("confidence", 0.5)), 0.0), 1.0),
        reasoning=parsed.get("reasoning", ""),
        evaluation_method="llm_analysis",
        evaluation_criteria=parsed.get("evaluation_criteria", []),
        factors=[
            RecommendationFactor(
                factor=f.get("factor", ""),
                explanation=f.get("explanation", ""),
                impact=f.get("impact", "positive"),
                weight=min(max(float(f.get("weight", 0.5)), 0.0), 1.0),
            )
            for f in parsed.get("factors", [])
        ],
    )


def _template_recommendation(
    body: RecommendationRequest,
    entity: EntityBase | None,
    children: list[EntityBase],
) -> RecommendationResponse:
    """Template fallback when LLM is disabled."""
    if not entity:
        return RecommendationResponse(
            job_id=body.job_id,
            recommendation="needs_more_data",
            confidence=0.0,
            reasoning="Could not find job data. Enable LLM for preliminary analysis.",
            evaluation_method="heuristic_template",
            evaluation_criteria=["Job data availability"],
            factors=[],
        )

    tier = entity.properties.get("tier", "")
    executor_type = entity.properties.get("executor_type", "HUMAN")
    has_metrics = len(body.outcomes.metrics) > 0
    has_experience = bool(
        body.outcomes.experience_markers.get("feel_markers")
        or body.outcomes.experience_markers.get("to_be_markers")
    )

    criteria: list[str] = ["Job tier classification"]
    factors: list[RecommendationFactor] = []

    if tier in ("T3_execution", "T4_micro"):
        factors.append(RecommendationFactor(
            factor="Low-tier execution job",
            explanation=(
                "T3/T4 jobs are concrete execution steps with less contextual variance, "
                "making them stronger candidates for automation."
            ),
            impact="positive",
            weight=0.3,
        ))
    elif tier == "T1_strategic":
        factors.append(RecommendationFactor(
            factor="Strategic-level job requires human judgment",
            explanation=(
                "T1 strategic jobs involve high-level decision-making and vision "
                "that typically requires human intuition and stakeholder alignment."
            ),
            impact="negative",
            weight=0.4,
        ))

    # Executor type analysis
    criteria.append("Executor type classification")
    if executor_type == "AI":
        factors.append(RecommendationFactor(
            factor="Job already designated as AI-executable",
            explanation=(
                "This job has been classified as suitable for AI execution, "
                "indicating systematic, repeatable work patterns."
            ),
            impact="positive",
            weight=0.25,
        ))
    elif not has_experience:
        factors.append(RecommendationFactor(
            factor="Human job without experience markers defined",
            explanation=(
                "A human-designated job without experience markers may indicate "
                "that the emotional/identity dimension hasn't been explored yet."
            ),
            impact="positive",
            weight=0.15,
        ))

    if has_experience:
        criteria.append("Experience marker analysis")
        factors.append(RecommendationFactor(
            factor="Experience markers suggest human-centric value",
            explanation=(
                "Feel and To-Be markers indicate emotional or identity-based outcomes "
                "that are difficult for AI systems to deliver authentically."
            ),
            impact="negative",
            weight=0.2,
        ))

    if has_metrics:
        criteria.append("Defined metrics coverage")
        factors.append(RecommendationFactor(
            factor="Defined metrics enable objective evaluation",
            explanation=(
                "Having explicit success metrics means performance can be measured objectively, "
                "making it feasible to compare human vs AI execution."
            ),
            impact="positive",
            weight=0.2,
        ))

    if len(children) > 3:
        criteria.append("Sub-job decomposition pattern")
        factors.append(RecommendationFactor(
            factor="Multiple sub-jobs indicate decomposable work",
            explanation=(
                "Jobs with many sub-tasks can often be partially automated, "
                "with individual steps delegated to AI while humans oversee the whole."
            ),
            impact="positive",
            weight=0.2,
        ))

    if not has_metrics and not has_experience:
        return RecommendationResponse(
            job_id=body.job_id,
            recommendation="needs_more_data",
            confidence=0.2,
            reasoning=(
                "Enable LLM for preliminary analysis, "
                "or define metrics and experience markers for a heuristic evaluation."
            ),
            evaluation_method="heuristic_template",
            evaluation_criteria=criteria,
            factors=factors,
        )

    positive_weight = sum(f.weight for f in factors if f.impact == "positive")
    negative_weight = sum(f.weight for f in factors if f.impact == "negative")

    if positive_weight > negative_weight + 0.1:
        recommendation = "switch_to_ai"
    elif negative_weight > positive_weight + 0.1:
        recommendation = "keep_human"
    else:
        recommendation = "needs_more_data"

    confidence = min(abs(positive_weight - negative_weight) + 0.3, 0.7)

    return RecommendationResponse(
        job_id=body.job_id,
        recommendation=recommendation,
        confidence=round(confidence, 2),
        reasoning=(
            f"Heuristic analysis based on job tier ({tier}), "
            f"{len(body.outcomes.metrics)} metric(s), and "
            f"{'present' if has_experience else 'absent'} experience markers. "
            "Enable LLM for deeper analysis."
        ),
        evaluation_method="heuristic_template",
        evaluation_criteria=criteria,
        factors=factors,
    )
