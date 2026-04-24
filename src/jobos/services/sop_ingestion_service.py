"""JobOS 4.0 — SOP / Workflow Ingestion Service.

Ingests structured documents (SOPs, workflow descriptions) and
converts them into job hierarchies.  Uses document extraction
for text parsing, then LLM or heuristic for step decomposition
and tier classification.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from jobos.kernel.entity import _uid
from jobos.kernel.hierarchy import HierarchyContext
from jobos.services.tier_classifier import TierClassifier
from jobos.adapters.extraction.document_extractor import extract_from_bytes

logger = logging.getLogger(__name__)

SOP_EXTRACTION_PROMPT = """You are a process analyst. Extract discrete process
steps from the following document text. Each step should be a clear,
actionable statement starting with a verb.

Return JSON:
{
  "domain": "inferred domain name",
  "steps": [
    {"statement": "verb-first action statement", "order": 1},
    ...
  ]
}

Document text:
"""


class SOPIngestionService:
    """Ingests SOPs and workflows into job hierarchies."""

    def __init__(self, llm=None, graph=None) -> None:
        self._llm = llm
        self._graph = graph
        self._classifier = TierClassifier(llm=llm)

    async def ingest_document(
        self,
        content: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """Ingest a document file and return a hierarchy structure.

        Supported formats: .txt, .md, .pdf, .docx
        """
        extracted = extract_from_bytes(content, filename)
        if not extracted or not extracted.text:
            return {"error": "Could not extract text from document"}

        return await self.ingest_from_text(
            text=extracted.text,
            domain=extracted.title or filename,
        )

    async def ingest_from_text(
        self,
        text: str,
        domain: str = "",
    ) -> dict[str, Any]:
        """Ingest raw text and return a hierarchy structure."""
        steps = await self._extract_steps(text)
        if not steps:
            return {"error": "No process steps extracted"}

        jobs: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        # Classify each step into a tier
        for step in steps:
            tier = self._classifier.classify(step["statement"])
            job_id = _uid()
            jobs.append({
                "id": job_id,
                "tier": f"T{tier}",
                "statement": step["statement"],
                "category": "",
                "rationale": "",
                "metrics_hint": [],
                "executor_type": "HUMAN",
                "order": step.get("order", 0),
            })

        # Sort by tier then order for edge inference
        jobs.sort(key=lambda j: (j["tier"], j.get("order", 0)))

        # Infer parent-child edges: each Tn job is child of preceding Tn-1
        tier_parents: dict[str, str] = {}
        for job in jobs:
            tier_str = job["tier"]
            tier_num = int(tier_str.replace("T", "")) if tier_str.startswith("T") else 3
            job["tier_num"] = tier_num

            if tier_num > 1:
                parent_tier = f"T{tier_num - 1}"
                parent_id = tier_parents.get(parent_tier)
                if parent_id:
                    edges.append({
                        "parent_id": parent_id,
                        "child_id": job["id"],
                        "strength": 1.0,
                    })

            tier_parents[tier_str] = job["id"]

        tier_map = {
            "T1": "T1_strategic", "T2": "T2_core",
            "T3": "T3_execution", "T4": "T4_micro",
        }
        for job in jobs:
            job["tier"] = tier_map.get(job["tier"], job["tier"])
            job.pop("tier_num", None)
            job.pop("order", None)

        logger.info(
            "SOP ingestion: %d steps extracted, %d jobs, %d edges",
            len(steps), len(jobs), len(edges),
        )

        return {
            "domain": domain,
            "jobs": jobs,
            "edges": edges,
            "summary": {
                "total_jobs": len(jobs),
                "total_edges": len(edges),
                "source": "sop_ingest",
            },
        }

    async def _extract_steps(self, text: str) -> list[dict[str, Any]]:
        """Extract process steps from document text."""
        if self._llm:
            try:
                raw = await self._llm.complete_json(
                    system_prompt=SOP_EXTRACTION_PROMPT,
                    user_prompt=text[:4000],
                    max_tokens=2000,
                )
                if raw and raw.get("steps"):
                    return raw["steps"]
            except Exception as e:
                logger.warning("LLM SOP extraction failed: %s", e)

        return self._heuristic_extract_steps(text)

    def _heuristic_extract_steps(self, text: str) -> list[dict[str, Any]]:
        """Extract steps using numbered list / bullet point detection."""
        steps: list[dict[str, Any]] = []
        lines = text.split("\n")
        order = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Match numbered items: "1.", "1)", "Step 1:", "- ", "* "
            match = re.match(
                r"^(?:\d+[.)]\s*|step\s+\d+[.:]\s*|[-*]\s+)",
                line,
                re.IGNORECASE,
            )
            if match:
                statement = line[match.end():].strip()
                if statement and len(statement) > 5:
                    order += 1
                    steps.append({
                        "statement": statement,
                        "order": order,
                    })

        return steps
