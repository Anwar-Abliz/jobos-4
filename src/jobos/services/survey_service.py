"""JobOS 4.0 — Survey Service.

ODI survey integration: create surveys, generate outcomes (LLM or template),
collect responses, aggregate results, and sync to imperfections.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.odi import compute_opportunity_score, map_opportunity_to_vfe
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)

# Template fallback outcomes when LLM is unavailable
_TEMPLATE_OUTCOMES: list[dict[str, str]] = [
    {
        "context": "Order Processing",
        "outcomes": [
            "Minimize the time it takes to complete the process",
            "Minimize the likelihood of errors during execution",
            "Minimize the effort required to verify results",
        ],
    },
    {
        "context": "Data Management",
        "outcomes": [
            "Minimize the time it takes to find the right information",
            "Maximize the accuracy of data entry",
            "Minimize the variability in data quality",
        ],
    },
    {
        "context": "Decision Making",
        "outcomes": [
            "Minimize the time it takes to gather necessary information",
            "Maximize the accuracy of the decision",
            "Minimize the cost of reversing a wrong decision",
        ],
    },
]


class SurveyService:
    """ODI Survey management service."""

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort,
        llm: Any | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._llm = llm

    async def create_survey(
        self,
        name: str,
        segment_id: str = "",
        process_id: str = "",
    ) -> EntityBase:
        """Create a survey entity linked to segment/process."""
        survey_id = _uid()
        survey = EntityBase(
            id=survey_id,
            name=name,
            statement=f"ODI Survey: {name}",
            entity_type=EntityType.SURVEY,
            properties={
                "survey_type": "odi",
                "status": "draft",
                "total_outcomes": 0,
                "response_count": 0,
                "target_segment_id": segment_id,
            },
        )
        await self._graph.save_entity(survey)

        # Link to segment/process if provided
        if segment_id:
            await self._graph.create_edge(survey_id, segment_id, "TARGETS")
        if process_id:
            await self._graph.create_edge(process_id, survey_id, "SURVEYED_BY")

        logger.info("Created survey '%s' (%s)", name, survey_id)
        return survey

    async def generate_outcomes(
        self,
        survey_id: str,
        job_id: str | None = None,
        process_id: str | None = None,
    ) -> list[EntityBase]:
        """Generate ODI outcome statements from job hierarchy + process steps.

        Uses LLM if available, otherwise falls back to parameterized templates.
        """
        outcomes: list[EntityBase] = []

        if self._llm and (job_id or process_id):
            outcomes = await self._generate_outcomes_llm(
                survey_id, job_id, process_id
            )
        else:
            outcomes = await self._generate_outcomes_template(survey_id)

        # Update survey total
        survey = await self._graph.get_entity(survey_id)
        if survey:
            survey.properties["total_outcomes"] = len(outcomes)
            await self._graph.save_entity(survey)

        return outcomes

    async def _generate_outcomes_llm(
        self,
        survey_id: str,
        job_id: str | None,
        process_id: str | None,
    ) -> list[EntityBase]:
        """Generate outcomes using LLM."""
        # Build context for LLM
        context_parts = []
        if job_id:
            job = await self._graph.get_entity(job_id)
            if job:
                context_parts.append(f"Job: {job.statement}")
                children = await self._graph.get_neighbors(
                    job_id, edge_type="PART_OF", direction="incoming"
                )
                for c in children:
                    context_parts.append(f"  Sub-job: {c.statement}")

        if process_id:
            process = await self._graph.get_entity(process_id)
            if process:
                context_parts.append(f"Process: {process.name}")
                steps = await self._graph.get_neighbors(
                    process_id, edge_type="EXECUTED_BY", direction="outgoing"
                )
                for s in steps:
                    context_parts.append(f"  Step: {s.name}")

        prompt = (
            "You are an ODI analyst. Generate outcome statements per the format:\n"
            '"[Minimize/Maximize] the [metric_type] it takes to [action] when [context]"\n\n'
            "Metric types: time, cost, likelihood of error, effort, variability, accuracy\n\n"
            f"Context:\n{chr(10).join(context_parts)}\n\n"
            "Generate 5-8 outcomes that a customer would use to evaluate performance."
        )

        try:
            response = await self._llm.generate(prompt)
            lines = [
                line.strip()
                for line in response.split("\n")
                if line.strip().lower().startswith(("minimize", "maximize"))
            ]
        except Exception as e:
            logger.warning("LLM outcome generation failed: %s — using templates", e)
            return await self._generate_outcomes_template(survey_id)

        outcomes = []
        for line in lines[:8]:
            outcome = await self.add_outcome(
                survey_id=survey_id,
                text=line,
                context_label="LLM Generated",
                llm_generated=True,
            )
            outcomes.append(outcome)

        return outcomes

    async def _generate_outcomes_template(
        self, survey_id: str,
    ) -> list[EntityBase]:
        """Generate outcomes from templates (fallback when LLM unavailable)."""
        outcomes = []
        for context_group in _TEMPLATE_OUTCOMES:
            for text in context_group["outcomes"]:
                outcome = await self.add_outcome(
                    survey_id=survey_id,
                    text=text,
                    context_label=context_group["context"],
                    llm_generated=False,
                )
                outcomes.append(outcome)
        return outcomes

    async def add_outcome(
        self,
        survey_id: str,
        text: str,
        context_label: str = "",
        llm_generated: bool = False,
    ) -> EntityBase:
        """Add a single outcome to a survey."""
        outcome_id = _uid()
        direction = "minimize" if text.lower().startswith("minimize") else "maximize"

        outcome = EntityBase(
            id=outcome_id,
            name=text[:100],
            statement=text,
            entity_type=EntityType.OUTCOME,
            properties={
                "survey_id": survey_id,
                "context_label": context_label,
                "direction": direction,
                "llm_generated": llm_generated,
            },
        )
        await self._graph.save_entity(outcome)
        await self._graph.create_edge(survey_id, outcome_id, "HAS_OUTCOME")

        return outcome

    async def submit_response(
        self,
        survey_id: str,
        outcome_id: str,
        session_id: str,
        importance: float,
        satisfaction: float,
    ) -> dict[str, Any]:
        """Submit a single response: computes opportunity score, stores in PG."""
        opp_score = compute_opportunity_score(importance, satisfaction)

        response_id = await self._db.save_survey_response(
            survey_id=survey_id,
            outcome_id=outcome_id,
            session_id=session_id,
            importance=importance,
            satisfaction=satisfaction,
            opportunity_score=opp_score,
        )

        return {
            "response_id": response_id,
            "opportunity_score": opp_score,
        }

    async def submit_batch(
        self,
        responses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Submit multiple responses."""
        results = []
        for r in responses:
            result = await self.submit_response(
                survey_id=r["survey_id"],
                outcome_id=r["outcome_id"],
                session_id=r["session_id"],
                importance=r["importance"],
                satisfaction=r["satisfaction"],
            )
            results.append(result)
        return results

    async def get_results(self, survey_id: str) -> dict[str, Any]:
        """Get aggregated survey results."""
        aggregates = await self._db.get_survey_aggregates(survey_id)

        # Enrich with outcome details from graph
        enriched = []
        for agg in aggregates:
            outcome = await self._graph.get_entity(agg["outcome_id"])
            enriched.append({
                **agg,
                "statement": outcome.statement if outcome else "",
                "context_label": (
                    outcome.properties.get("context_label", "") if outcome else ""
                ),
            })

        # Sort by opportunity score descending
        enriched.sort(key=lambda x: x.get("opportunity_mean", 0), reverse=True)

        return {
            "survey_id": survey_id,
            "outcomes": enriched,
            "total_outcomes": len(enriched),
        }

    async def sync_to_imperfections(self, survey_id: str) -> list[EntityBase]:
        """Map high-opportunity outcomes to Imperfection entities with VFE."""
        aggregates = await self._db.get_survey_aggregates(survey_id)
        imperfections = []

        for agg in aggregates:
            opp_score = agg.get("opportunity_mean", 0)
            if opp_score < 10:  # threshold for "interesting" opportunities
                continue

            vfe = map_opportunity_to_vfe(opp_score)
            outcome = await self._graph.get_entity(agg["outcome_id"])
            if not outcome:
                continue

            imp_id = _uid()
            imp = EntityBase(
                id=imp_id,
                name=f"Opportunity: {outcome.statement[:80]}",
                statement=outcome.statement,
                entity_type=EntityType.IMPERFECTION,
                properties={
                    "severity": min(1.0, vfe),
                    "frequency": 0.5,
                    "entropy_risk": vfe,
                    "mode": "objective",
                    "evidence_level": "survey",
                    "metric_dimension": "opportunity",
                    "target_value": 1.0,
                    "observed_value": 1.0 - vfe,
                },
            )
            await self._graph.save_entity(imp)

            # Link outcome → imperfection via RESPONDS_TO
            await self._graph.create_edge(
                agg["outcome_id"], imp_id, "RESPONDS_TO"
            )
            imperfections.append(imp)

        logger.info(
            "Synced %d imperfections from survey %s",
            len(imperfections),
            survey_id,
        )
        return imperfections
