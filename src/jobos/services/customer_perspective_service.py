"""JobOS 4.0 — Customer Perspective Service.

Bridges internal SAP view → external customer outcome view.
Maps process steps to jobs, identifies pain points, and
generates customer journey representations.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType
from jobos.ports.graph_port import GraphPort

logger = logging.getLogger(__name__)


class CustomerPerspectiveService:
    """Bridges internal SAP processes to customer outcomes."""

    def __init__(self, graph: GraphPort, llm: Any | None = None) -> None:
        self._graph = graph
        self._llm = llm

    async def map_process_to_jobs(self, process_id: str) -> dict[str, Any]:
        """Map SAP process steps to JTBD hierarchy.

        For each transaction step, finds or suggests corresponding
        Job entities via HIRES or naming heuristics.
        """
        process = await self._graph.get_entity(process_id)
        if not process:
            return {"error": "process not found"}

        steps = await self._graph.get_neighbors(
            process_id, edge_type="EXECUTED_BY", direction="outgoing"
        )

        mappings = []
        for step in steps:
            # Look for existing job mappings
            job_neighbors = await self._graph.get_neighbors(
                step.id, edge_type="HIRES", direction="incoming"
            )
            jobs = [
                j for j in job_neighbors
                if j.entity_type == EntityType.JOB
            ]

            mappings.append({
                "step_id": step.id,
                "step_name": step.name,
                "tcode": step.properties.get("tcode", ""),
                "mapped_jobs": [
                    {"id": j.id, "statement": j.statement} for j in jobs
                ],
                "has_mapping": len(jobs) > 0,
            })

        mapped_count = sum(1 for m in mappings if m["has_mapping"])

        return {
            "process_id": process_id,
            "process_name": process.name,
            "total_steps": len(mappings),
            "mapped_steps": mapped_count,
            "coverage_pct": round(mapped_count / len(mappings) * 100, 2) if mappings else 0,
            "mappings": mappings,
        }

    async def identify_pain_points(self, process_id: str) -> dict[str, Any]:
        """Identify pain points from process gaps and imperfections."""
        process = await self._graph.get_entity(process_id)
        if not process:
            return {"error": "process not found"}

        steps = await self._graph.get_neighbors(
            process_id, edge_type="EXECUTED_BY", direction="outgoing"
        )

        pain_points = []
        for step in steps:
            # Check for imperfections linked to this step
            imperfections = await self._graph.get_neighbors(
                step.id, edge_type="OCCURS_IN", direction="incoming"
            )
            imps = [
                i for i in imperfections
                if i.entity_type == EntityType.IMPERFECTION
            ]

            if imps:
                for imp in imps:
                    pain_points.append({
                        "step_id": step.id,
                        "step_name": step.name,
                        "imperfection_id": imp.id,
                        "description": imp.statement,
                        "severity": imp.properties.get("severity", 0),
                    })

        # Sort by severity descending
        pain_points.sort(key=lambda x: x.get("severity", 0), reverse=True)

        return {
            "process_id": process_id,
            "process_name": process.name,
            "total_pain_points": len(pain_points),
            "pain_points": pain_points,
        }

    async def generate_customer_journey(
        self, process_id: str,
    ) -> dict[str, Any]:
        """Generate a customer journey map from context graph.

        Maps: process steps → customer touchpoints → outcomes.
        """
        process = await self._graph.get_entity(process_id)
        if not process:
            return {"error": "process not found"}

        steps = await self._graph.get_neighbors(
            process_id, edge_type="EXECUTED_BY", direction="outgoing"
        )

        journey_stages = []
        for i, step in enumerate(steps):
            # Get objects touched
            objects = await self._graph.get_neighbors(
                step.id, edge_type="OPERATES_ON", direction="outgoing"
            )

            # Get surveys linked
            surveys = await self._graph.get_neighbors(
                step.id, edge_type="SURVEYED_BY", direction="outgoing"
            )

            journey_stages.append({
                "order": i + 1,
                "step_id": step.id,
                "step_name": step.name,
                "touchpoints": [o.name for o in objects],
                "has_survey": len(surveys) > 0,
                "customer_visible": self._is_customer_visible(step),
            })

        return {
            "process_id": process_id,
            "process_name": process.name,
            "journey_stages": journey_stages,
            "total_stages": len(journey_stages),
            "customer_visible_stages": sum(
                1 for s in journey_stages if s["customer_visible"]
            ),
        }

    @staticmethod
    def _is_customer_visible(step: EntityBase) -> bool:
        """Heuristic: is this step visible to the customer?"""
        customer_tcodes = {"VA01", "VL02N", "VF01", "F-28"}
        tcode = step.properties.get("tcode", "")
        name_lower = step.name.lower()
        return (
            tcode in customer_tcodes
            or "order" in name_lower
            or "delivery" in name_lower
            or "invoice" in name_lower
            or "payment" in name_lower
        )
