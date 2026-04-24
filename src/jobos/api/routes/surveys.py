"""JobOS 4.0 — Survey API Routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from jobos.api.deps import get_survey_service
from jobos.services.survey_service import SurveyService

router = APIRouter(prefix="/surveys")


class CreateSurveyRequest(BaseModel):
    name: str
    segment_id: str = ""
    process_id: str = ""


class SurveyResponse(BaseModel):
    id: str
    name: str
    status: str


class GenerateOutcomesRequest(BaseModel):
    job_id: str | None = None
    process_id: str | None = None


class AddOutcomeRequest(BaseModel):
    text: str
    context_label: str = ""


class SubmitResponseRequest(BaseModel):
    outcome_id: str
    session_id: str
    importance: float
    satisfaction: float


class BatchResponseRequest(BaseModel):
    responses: list[dict[str, Any]]


@router.post("", response_model=SurveyResponse)
async def create_survey(
    request: CreateSurveyRequest,
    svc: SurveyService = Depends(get_survey_service),
):
    survey = await svc.create_survey(
        name=request.name,
        segment_id=request.segment_id,
        process_id=request.process_id,
    )
    return SurveyResponse(
        id=survey.id,
        name=survey.name,
        status=survey.properties.get("status", "draft"),
    )


@router.post("/{survey_id}/generate-outcomes")
async def generate_outcomes(
    survey_id: str,
    request: GenerateOutcomesRequest,
    svc: SurveyService = Depends(get_survey_service),
):
    outcomes = await svc.generate_outcomes(
        survey_id=survey_id,
        job_id=request.job_id,
        process_id=request.process_id,
    )
    return {
        "survey_id": survey_id,
        "outcomes_generated": len(outcomes),
        "outcomes": [
            {"id": o.id, "statement": o.statement, **o.properties}
            for o in outcomes
        ],
    }


@router.post("/{survey_id}/outcomes")
async def add_outcome(
    survey_id: str,
    request: AddOutcomeRequest,
    svc: SurveyService = Depends(get_survey_service),
):
    outcome = await svc.add_outcome(
        survey_id=survey_id,
        text=request.text,
        context_label=request.context_label,
    )
    return {"id": outcome.id, "statement": outcome.statement, **outcome.properties}


@router.get("/{survey_id}")
async def get_survey(
    survey_id: str,
    svc: SurveyService = Depends(get_survey_service),
):
    survey = await svc._graph.get_entity(survey_id)
    if not survey:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Survey not found")

    outcomes = await svc._graph.get_neighbors(
        survey_id, edge_type="HAS_OUTCOME", direction="outgoing"
    )
    return {
        "id": survey.id,
        "name": survey.name,
        **survey.properties,
        "outcomes": [
            {"id": o.id, "statement": o.statement, **o.properties}
            for o in outcomes
        ],
    }


@router.post("/{survey_id}/responses")
async def submit_responses(
    survey_id: str,
    request: BatchResponseRequest,
    svc: SurveyService = Depends(get_survey_service),
):
    # Inject survey_id into each response
    for r in request.responses:
        r["survey_id"] = survey_id
    results = await svc.submit_batch(request.responses)
    return {"survey_id": survey_id, "responses_recorded": len(results), "results": results}


@router.get("/{survey_id}/results")
async def get_results(
    survey_id: str,
    svc: SurveyService = Depends(get_survey_service),
):
    return await svc.get_results(survey_id)


@router.post("/{survey_id}/sync-imperfections")
async def sync_imperfections(
    survey_id: str,
    svc: SurveyService = Depends(get_survey_service),
):
    imperfections = await svc.sync_to_imperfections(survey_id)
    return {
        "survey_id": survey_id,
        "imperfections_created": len(imperfections),
        "imperfections": [
            {"id": i.id, "name": i.name, "severity": i.properties.get("severity", 0)}
            for i in imperfections
        ],
    }


@router.get("/{survey_id}/scatter")
async def scatter_data(
    survey_id: str,
    svc: SurveyService = Depends(get_survey_service),
):
    """Scatter plot data: importance vs satisfaction per outcome."""
    aggregates = await svc._db.get_survey_aggregates(survey_id)
    points = []
    for agg in aggregates:
        outcome = await svc._graph.get_entity(agg["outcome_id"])
        points.append({
            "outcome_id": agg["outcome_id"],
            "statement": outcome.statement if outcome else "",
            "importance": agg.get("importance_mean", 0),
            "satisfaction": agg.get("satisfaction_mean", 0),
            "opportunity": agg.get("opportunity_mean", 0),
            "response_count": agg.get("response_count", 0),
        })
    return {"survey_id": survey_id, "points": points}


# ─── Bulk / Machine-to-Machine Endpoints ────────────────

class BulkDiscoveryIn(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    outcomes_per_job: int = 10
    deduplicate: bool = True


class HierarchySurveyIn(BaseModel):
    hierarchy_id: str
    name: str = ""
    outcomes_per_job: int = 5


@router.post("/surveys/{survey_id}/discover-bulk")
async def discover_outcomes_bulk(survey_id: str, req: BulkDiscoveryIn):
    """Bulk outcome discovery: generate outcomes for multiple jobs at once."""
    svc = get_survey_service()
    outcomes = await svc.discover_outcomes_bulk(
        survey_id=survey_id,
        job_ids=req.job_ids,
        outcomes_per_job=req.outcomes_per_job,
        deduplicate=req.deduplicate,
    )
    return {
        "survey_id": survey_id,
        "outcomes_generated": len(outcomes),
        "outcomes": [
            {"id": o.id, "statement": o.statement}
            for o in outcomes
        ],
    }


@router.post("/surveys/from-hierarchy")
async def create_survey_from_hierarchy(req: HierarchySurveyIn):
    """Auto-create a survey from a hierarchy, generating outcomes per T2-T3 job."""
    svc = get_survey_service()
    result = await svc.create_survey_from_hierarchy(
        hierarchy_id=req.hierarchy_id,
        name=req.name,
        outcomes_per_job=req.outcomes_per_job,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/surveys/{survey_id}/scatter")
async def get_scatter_data(survey_id: str):
    """Get scatter plot data (importance vs satisfaction per outcome)."""
    svc = get_survey_service()
    return await svc.get_scatter_data(survey_id)
