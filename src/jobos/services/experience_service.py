"""JobOS 4.0 — Experience Service (Dimension A Generation + Versioning).

Generates, edits, and versions Experience markers (Feel / To Be statements)
for functional jobs. Supports LLM-powered generation with template fallback,
tier reconciliation, human override with full version history, and graph
persistence as :Experience entities with EXPERIENCE_OF edges.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.experience import (
    ExperienceProperties,
    validate_experiential_statement,
    extract_emotion_keywords,
)
from jobos.kernel.axioms import AxiomViolation
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.adapters.openai.llm_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

EXPERIENCE_SYSTEM_PROMPT = """You are the Experience Dimension Generator for JobOS.

Given a functional job statement, generate Experience markers — the emotional and identity
dimension (Dimension A) that accompanies the functional job.

Rules:
1. Generate exactly 3 "Feel" markers and 3 "To be" markers.
2. "Feel" markers must start with "Feel" (e.g., "Feel confident in the quality of output").
3. "To be" markers must start with "To be" (e.g., "To be seen as a reliable partner").
4. Markers should be specific to the job context, not generic.
5. Consider the role archetype if provided.

Respond with JSON:
{
  "feel_markers": ["Feel ...", "Feel ...", "Feel ..."],
  "to_be_markers": ["To be ...", "To be ...", "To be ..."],
  "confidence": 0.8
}"""

# Template fallback when LLM is unavailable
DEFAULT_FEEL_MARKERS = [
    "Feel confident in the quality of work delivered",
    "Feel in control of the process and outcomes",
    "Feel supported by tools and teammates",
]

DEFAULT_TO_BE_MARKERS = [
    "To be recognized for competent execution",
    "To be trusted with increasing responsibility",
    "To be seen as a reliable contributor",
]


class ExperienceService:
    """Generates, edits, and versions Dimension A experience markers."""

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort | None = None,
        llm: OpenAIAdapter | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._llm = llm

    async def generate(
        self,
        job_id: str,
        role_archetype: str = "",
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Generate experience markers for a job via LLM or template fallback.

        Returns the created experience entity data.
        """
        job = await self._graph.get_entity(job_id)
        if not job or job.entity_type != EntityType.JOB:
            raise ValueError(f"Job entity not found: {job_id}")

        # Get current version number
        version = await self._get_next_version(job_id)

        if self._llm:
            markers = await self._llm_generate(job.statement, role_archetype)
        else:
            markers = self._template_generate(job.statement)

        # Reconcile with T1 if this is not the root
        t1_score = await self._reconcile_with_tier_1(job, markers)

        # Persist version to PostgreSQL
        combined_markers = {
            "feel_markers": markers.get("feel_markers", []),
            "to_be_markers": markers.get("to_be_markers", []),
        }
        confidence = markers.get("confidence", 0.5)

        if self._db:
            await self._db.save_experience_version(
                job_id=job_id,
                version=version,
                markers=combined_markers,
                source="llm" if self._llm else "manual",
                confidence=confidence,
                created_by=created_by,
            )

        # Commit to graph
        exp_entity = await self._commit_to_graph(
            job_id=job_id,
            markers=combined_markers,
            source="llm" if self._llm else "manual",
            confidence=confidence,
            version=version,
            role_archetype=role_archetype,
        )

        return {
            "experience_id": exp_entity.id,
            "job_id": job_id,
            "version": version,
            "markers": combined_markers,
            "source": "llm" if self._llm else "manual",
            "confidence": confidence,
            "reconciliation_score": t1_score,
        }

    async def edit(
        self,
        job_id: str,
        markers: dict[str, list[str]],
        created_by: str = "user",
    ) -> dict[str, Any]:
        """Human override of experience markers with Axiom 5 validation.

        Creates a new version (source='override') and updates the graph.
        """
        # Validate all markers against Axiom 5 (experiential format)
        for marker_type in ("feel_markers", "to_be_markers"):
            for marker in markers.get(marker_type, []):
                if not validate_experiential_statement(marker):
                    raise AxiomViolation(
                        5,
                        f"Experience marker must start with 'Feel' or 'To be': '{marker}'"
                    )

        version = await self._get_next_version(job_id)

        if self._db:
            await self._db.save_experience_version(
                job_id=job_id,
                version=version,
                markers=markers,
                source="override",
                confidence=1.0,
                created_by=created_by,
            )

        exp_entity = await self._commit_to_graph(
            job_id=job_id,
            markers=markers,
            source="override",
            confidence=1.0,
            version=version,
        )

        return {
            "experience_id": exp_entity.id,
            "job_id": job_id,
            "version": version,
            "markers": markers,
            "source": "override",
            "confidence": 1.0,
        }

    async def get_history(
        self, job_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get experience version history for a job."""
        if not self._db:
            return []
        return await self._db.get_experience_history(job_id, limit=limit)

    # ─── LLM Generation ─────────────────────────────────

    async def _llm_generate(
        self, job_statement: str, role_archetype: str = ""
    ) -> dict[str, Any]:
        """Use LLM to generate experience markers."""
        archetype_hint = f"\nRole archetype: {role_archetype}" if role_archetype else ""
        user_prompt = (
            f"Generate Experience markers for this job:\n\n"
            f"Job statement: {job_statement}{archetype_hint}\n\n"
            f"Generate markers that are specific to this job context."
        )

        try:
            raw = await self._llm.complete_json(
                system_prompt=EXPERIENCE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=500,
                temperature=0.4,
            )
            if raw and (raw.get("feel_markers") or raw.get("to_be_markers")):
                # Validate each marker
                validated: dict[str, Any] = {"confidence": raw.get("confidence", 0.7)}
                for key in ("feel_markers", "to_be_markers"):
                    validated[key] = [
                        m for m in raw.get(key, [])
                        if validate_experiential_statement(m)
                    ]
                return validated
        except Exception as e:
            logger.warning("LLM experience generation failed, using template: %s", e)

        return self._template_generate(job_statement)

    def _template_generate(self, job_statement: str) -> dict[str, Any]:
        """Template fallback for experience marker generation."""
        return {
            "feel_markers": list(DEFAULT_FEEL_MARKERS),
            "to_be_markers": list(DEFAULT_TO_BE_MARKERS),
            "confidence": 0.3,
        }

    # ─── Tier Reconciliation ────────────────────────────

    async def _reconcile_with_tier_1(
        self, job: EntityBase, markers: dict[str, Any]
    ) -> float:
        """Check keyword overlap between generated markers and T1 strategic job.

        Returns a reconciliation score (0.0–1.0). Higher = more aligned.
        """
        # Find the T1 root in the same scope
        scope_id = job.properties.get("scope_id", "")
        if not scope_id:
            return 0.0

        all_jobs = await self._graph.list_entities(entity_type="job", limit=200)
        t1_jobs = [
            j for j in all_jobs
            if j.properties.get("root_token") == "ROOT"
            and j.properties.get("scope_id") == scope_id
        ]

        if not t1_jobs:
            return 0.0

        # Extract keywords from T1 statement
        t1_keywords = set(t1_jobs[0].statement.lower().split())

        # Extract emotion keywords from all markers
        all_markers = markers.get("feel_markers", []) + markers.get("to_be_markers", [])
        marker_keywords: set[str] = set()
        for m in all_markers:
            marker_keywords.update(extract_emotion_keywords(m))

        if not marker_keywords or not t1_keywords:
            return 0.0

        overlap = t1_keywords & marker_keywords
        return len(overlap) / max(len(marker_keywords), 1)

    # ─── Graph Persistence ──────────────────────────────

    async def _commit_to_graph(
        self,
        job_id: str,
        markers: dict[str, Any],
        source: str,
        confidence: float,
        version: int,
        role_archetype: str = "",
    ) -> EntityBase:
        """Create or update :Experience entity and EXPERIENCE_OF edge."""
        feel = markers.get("feel_markers", [])
        to_be = markers.get("to_be_markers", [])

        # Build the statement from the first marker
        statement = feel[0] if feel else (to_be[0] if to_be else "")

        entity = EntityBase(
            id=_uid(),
            name=f"Experience for {job_id} v{version}",
            statement=statement,
            entity_type=EntityType.JOB,  # Experience is a sub-type of Entity
            status="active",
            labels=["Experience"],
            properties={
                "identity_phrases": to_be,
                "emotion_phrases": feel,
                "job_id": job_id,
                "version": version,
                "source": source,
                "confidence": confidence,
                "role_archetype": role_archetype,
                "provenance": source,
                "job_type": "emotional",
            },
        )
        await self._graph.save_entity(entity)
        await self._graph.create_edge(entity.id, job_id, "EXPERIENCE_OF")

        return entity

    # ─── Helpers ─────────────────────────────────────────

    async def _get_next_version(self, job_id: str) -> int:
        """Get the next version number for a job's experience markers."""
        if not self._db:
            return 1
        history = await self._db.get_experience_history(job_id, limit=1)
        if history:
            return history[0]["version"] + 1
        return 1
