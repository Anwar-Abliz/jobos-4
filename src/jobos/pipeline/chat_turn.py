"""JobOS 4.0 — Chat Turn Pipeline (LLM-driven).

Fundamentally different from JobOS 3.0's regex→template approach.

Flow:
1. INTERPRET  — LLM extracts structured intent + entities from user message
2. GROUND     — Create/update entities and edges in the graph
3. ANALYZE    — Derive imperfections, compute VFE, check active hires
4. RESPOND    — LLM generates a response grounded in actual graph state

The LLM never hallucinates system state — it only sees what's in the graph.
The response is anchored to real entities, real metrics, real imperfections.

If LLM is disabled, falls back to a simplified extraction + rule-based response.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from jobos.kernel.entity import (
    EntityBase,
    EntityType,
    MetricReading,
    VFEReading,
    _uid,
)
from jobos.kernel.imperfection import compute_vfe, derive_imperfection_properties, compute_severity
from jobos.kernel.axioms import JobOSAxioms
from jobos.kernel.job_statement import validate_verb
from jobos.engines.nsaig import PolicyOptimizer
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.adapters.openai.llm_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  LLM System Prompts
# ═══════════════════════════════════════════════════════════

EXTRACTION_SYSTEM_PROMPT = """You are the perception layer of JobOS, a neurosymbolic Job-Centric Operating System.

Your task: extract structured entities from the user's message. The core ontology:
- **Job**: A desired change in state (goal). Statement MUST start with an action verb.
- **Metric**: A quantitative measure with target_value and optional current_value.
- **Context**: The 5W2H circumstances (who, why, what, where, when, how, constraints).
- **Capability**: A solution, tool, or approach that could be hired to address a job.
- **Imperfection**: A gap, blocker, or friction the user describes.
- **Fact**: A metric observation (e.g., "our churn is 8%" → metric_name: churn, value: 0.08).

Extract what's present. Don't invent entities the user didn't mention.

Respond with JSON:
{
  "intent": "define_job | report_metric | describe_problem | propose_solution | ask_question | general",
  "entities": [
    {
      "entity_type": "job|metric|context|capability|imperfection",
      "name": "short name",
      "statement": "full description",
      "properties": { ... type-specific properties ... }
    }
  ],
  "facts": [
    {"metric_name": "...", "value": ..., "unit": "..."}
  ],
  "summary": "one-line summary of what the user wants"
}"""

RESPONSE_SYSTEM_PROMPT = """You are JobOS, a neurosymbolic Job-Centric Operating System that helps users define goals, identify blockers, hire solutions, and track progress.

You are given the current graph state (entities, metrics, imperfections) as context.
Your response must be:
1. **Grounded** — only reference entities and data that exist in the provided context
2. **Actionable** — suggest a concrete next step
3. **Concise** — 2-4 paragraphs max
4. **Natural** — conversational, not robotic template text

Core axiom: Entity hires Entity in Context to minimize Imperfection.

If the user defines a job, acknowledge it and ask about success metrics.
If they report metrics, compute progress and highlight the top blocker.
If they describe a problem, frame it as an imperfection and suggest what to measure.
If they propose a solution, frame it as a capability that could be hired.
If the context is unclear, ask a focused clarifying question.

Never say "I need baseline data" as a generic response. Always engage with what the user actually said."""


# ═══════════════════════════════════════════════════════════
#  Result Type
# ═══════════════════════════════════════════════════════════

@dataclass
class ChatTurnResult:
    """Output of a single chat turn."""
    session_id: str = ""
    assistant_message: str = ""
    intent: str = "general"
    entities_created: list[dict] = field(default_factory=list)
    entities_updated: list[dict] = field(default_factory=list)
    imperfections: list[dict] = field(default_factory=list)
    vfe_current: float | None = None
    top_blocker: dict | None = None


# ═══════════════════════════════════════════════════════════
#  Pipeline
# ═══════════════════════════════════════════════════════════

class ChatTurnPipeline:
    """LLM-driven chat pipeline.

    Unlike JobOS 3.0 which used regex intent detection and hardcoded
    response templates, this pipeline uses the LLM for both perception
    (extracting entities) and generation (grounded responses).

    The LLM never sees stale or invented state — it only receives
    the actual graph context as input for response generation.
    """

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort,
        llm: OpenAIAdapter | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._llm = llm
        self._policy = PolicyOptimizer()

    async def run(
        self,
        message: str,
        session_id: str | None = None,
        job_id: str | None = None,
    ) -> ChatTurnResult:
        """Execute the full chat turn pipeline.

        Steps:
        1. INTERPRET — extract entities + intent from user message
        2. GROUND   — persist extracted entities to the graph
        3. ANALYZE  — derive imperfections, compute VFE
        4. RESPOND  — generate grounded response
        """
        is_new_session = session_id is None
        session_id = session_id or _uid()
        result = ChatTurnResult(session_id=session_id)

        # ── Step 1: INTERPRET ────────────────────────────
        extraction = await self._interpret(message)
        result.intent = extraction.get("intent", "general")

        # ── Step 2: GROUND ───────────────────────────────
        created, updated = await self._ground(extraction, job_id)
        result.entities_created = [{"id": e.id, "name": e.name, "type": e.entity_type.value} for e in created]
        result.entities_updated = [{"id": e.id, "name": e.name, "type": e.entity_type.value} for e in updated]

        # Find the active job (created, specified, or most recent in session)
        active_job_id = await self._resolve_active_job(job_id, created, is_new_session=is_new_session)

        # ── Step 3: ANALYZE ──────────────────────────────
        graph_context = {}
        if active_job_id:
            graph_context = await self._analyze(active_job_id)
            result.imperfections = graph_context.get("imperfections", [])
            result.vfe_current = graph_context.get("vfe_current")
            result.top_blocker = graph_context.get("top_blocker")

        # ── Step 4: RESPOND ──────────────────────────────
        result.assistant_message = await self._respond(
            user_message=message,
            intent=result.intent,
            extraction=extraction,
            graph_context=graph_context,
        )

        return result

    # ─── Step 1: INTERPRET ───────────────────────────────

    async def _interpret(self, message: str) -> dict[str, Any]:
        """Extract structured intent + entities from user message.

        If LLM is available, uses structured JSON extraction.
        If not, falls back to basic keyword heuristics.
        """
        if self._llm:
            try:
                return await self._llm.complete_json(
                    system_prompt=EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=message,
                    max_tokens=800,
                    temperature=0.0,
                )
            except Exception as e:
                logger.warning("LLM extraction failed, using fallback: %s", e)

        # Fallback: basic heuristic extraction
        return self._heuristic_extract(message)

    def _heuristic_extract(self, message: str) -> dict[str, Any]:
        """Simple keyword-based extraction when LLM is unavailable."""
        msg_lower = message.lower()
        intent = "general"

        # Detect intent from keywords
        if any(w in msg_lower for w in ["reduce", "increase", "improve", "achieve", "build", "launch"]):
            intent = "define_job"
        elif any(w in msg_lower for w in ["churn", "revenue", "rate", "metric", "%", "dropped", "increased"]):
            intent = "report_metric"
        elif any(w in msg_lower for w in ["problem", "issue", "blocker", "struggling", "failing"]):
            intent = "describe_problem"
        elif any(w in msg_lower for w in ["solution", "tool", "hire", "try", "implement", "use"]):
            intent = "propose_solution"
        elif message.strip().endswith("?"):
            intent = "ask_question"

        entities = []

        # If it looks like a job definition, create a job entity
        if intent == "define_job":
            entities.append({
                "entity_type": "job",
                "name": message[:50],
                "statement": message,
                "properties": {"job_type": "core_functional", "job_nature": "project", "level": 0},
            })

        return {
            "intent": intent,
            "entities": entities,
            "facts": [],
            "summary": message[:100],
        }

    # ─── Step 2: GROUND ─────────────────────────────────

    async def _ground(
        self,
        extraction: dict[str, Any],
        existing_job_id: str | None = None,
    ) -> tuple[list[EntityBase], list[EntityBase]]:
        """Persist extracted entities and facts to the graph + PostgreSQL."""
        created: list[EntityBase] = []
        updated: list[EntityBase] = []

        # Create entities from extraction
        for raw_entity in extraction.get("entities", []):
            try:
                entity_type = EntityType(raw_entity.get("entity_type", "job"))
            except ValueError:
                continue

            entity = EntityBase(
                name=raw_entity.get("name", ""),
                statement=raw_entity.get("statement", ""),
                entity_type=entity_type,
                status="active",
                properties=raw_entity.get("properties", {}),
            )

            # Validate job statements (Axiom 5) — relax if LLM generated it
            if entity_type == EntityType.JOB and entity.statement:
                if not validate_verb(entity.statement):
                    # Prepend "achieve" to make it valid
                    entity.statement = f"achieve {entity.statement}"

            # Ensure type label
            type_label = entity_type.value.capitalize()
            if type_label not in entity.labels:
                entity.labels.append(type_label)

            await self._graph.save_entity(entity)
            created.append(entity)

            # If it's a metric and we have a job, link them
            if entity_type == EntityType.METRIC and existing_job_id:
                await self._graph.create_edge(existing_job_id, entity.id, "MEASURED_BY")

            # If it's an imperfection and we have a job, link it
            if entity_type == EntityType.IMPERFECTION and existing_job_id:
                await self._graph.create_edge(entity.id, existing_job_id, "OCCURS_IN")

        # Record metric facts
        for fact in extraction.get("facts", []):
            metric_name = fact.get("metric_name", "")
            value = fact.get("value")
            if not metric_name or value is None:
                continue

            # Find or create the metric entity
            existing_metrics = await self._graph.list_entities(
                entity_type="metric", limit=50
            )
            target_metric = None
            for m in existing_metrics:
                if metric_name.lower() in (m.name or "").lower() or metric_name.lower() in (m.statement or "").lower():
                    target_metric = m
                    break

            if target_metric:
                # Update current_value
                target_metric.properties["current_value"] = float(value)
                target_metric.updated_at = datetime.now(timezone.utc)
                await self._graph.save_entity(target_metric)
                updated.append(target_metric)

                # Record reading in PostgreSQL
                reading = MetricReading(
                    entity_id=existing_job_id or "",
                    metric_id=target_metric.id,
                    value=float(value),
                    unit=fact.get("unit", ""),
                    source="chat",
                )
                await self._db.save_metric_reading(reading)

        return created, updated

    # ─── Step 3: ANALYZE ─────────────────────────────────

    async def _analyze(self, job_id: str) -> dict[str, Any]:
        """Compute the current state of a job: metrics, imperfections, VFE."""
        context: dict[str, Any] = {"job_id": job_id}

        # Get the job
        job = await self._graph.get_entity(job_id)
        if not job:
            return context
        context["job"] = {"id": job.id, "name": job.name, "statement": job.statement}

        # Get metrics
        metrics = await self._graph.get_neighbors(job_id, edge_type="MEASURED_BY", direction="outgoing")
        context["metrics"] = []
        metric_state: dict[str, dict] = {}
        for m in metrics:
            props = m.properties
            metric_info = {
                "id": m.id,
                "name": m.name,
                "target": props.get("target_value"),
                "current": props.get("current_value"),
                "direction": props.get("direction", "minimize"),
                "unit": props.get("unit", ""),
            }
            context["metrics"].append(metric_info)
            if metric_info["target"] is not None:
                metric_state[m.id] = {
                    "observed": metric_info["current"],
                    "target": metric_info["target"],
                    "op": "<=" if metric_info["direction"] == "minimize" else ">=",
                }

        # Derive imperfections from unmet metrics
        imperfections: list[dict] = []
        for m in context["metrics"]:
            target = m.get("target")
            current = m.get("current")
            if target is None:
                continue

            direction = m.get("direction", "minimize")
            op = "<=" if direction == "minimize" else ">="
            severity = compute_severity(current, target, op)

            if severity > 0.0:
                imp_props = derive_imperfection_properties(current, target, op)
                vfe = compute_vfe(imp_props)
                imperfections.append({
                    "metric_name": m["name"],
                    "metric_id": m["id"],
                    "severity": round(severity, 3),
                    "is_blocker": imp_props["is_blocker"],
                    "vfe_score": round(vfe, 3),
                    "observed": current,
                    "target": target,
                    "op": op,
                })

        imperfections.sort(key=lambda x: x["vfe_score"], reverse=True)
        context["imperfections"] = imperfections
        context["top_blocker"] = imperfections[0] if imperfections else None

        # Compute VFE
        vfe = self._policy.compute_vfe(metric_state) if metric_state else 0.0
        context["vfe_current"] = round(vfe, 4)

        # Record VFE if meaningful
        if vfe > 0:
            vfe_reading = VFEReading(job_id=job_id, vfe_value=vfe)
            await self._db.save_vfe_reading(vfe_reading)

        # Get active hires
        hires = await self._graph.get_neighbors(job_id, edge_type="HIRES", direction="incoming")
        context["active_hires"] = [
            {"id": h.id, "name": h.name, "type": h.entity_type.value}
            for h in hires
        ]

        return context

    # ─── Step 4: RESPOND ─────────────────────────────────

    async def _respond(
        self,
        user_message: str,
        intent: str,
        extraction: dict[str, Any],
        graph_context: dict[str, Any],
    ) -> str:
        """Generate a response grounded in the actual graph state.

        If LLM available: passes the graph context to the LLM for
        a natural, grounded response.
        If not: generates a structured but readable summary.
        """
        if self._llm:
            return await self._llm_respond(user_message, intent, extraction, graph_context)

        return self._fallback_respond(intent, extraction, graph_context)

    async def _llm_respond(
        self,
        user_message: str,
        intent: str,
        extraction: dict[str, Any],
        graph_context: dict[str, Any],
    ) -> str:
        """LLM-grounded response generation."""
        # Build context summary for the LLM
        context_parts = [f"**User intent**: {intent}"]

        if graph_context.get("job"):
            j = graph_context["job"]
            context_parts.append(f"**Active job**: {j['name']} — \"{j['statement']}\"")

        if graph_context.get("metrics"):
            context_parts.append("**Metrics**:")
            for m in graph_context["metrics"]:
                status = ""
                if m["target"] is not None and m["current"] is not None:
                    status = f" (current: {m['current']}, target: {m['target']})"
                elif m["target"] is not None:
                    status = f" (target: {m['target']}, no reading yet)"
                context_parts.append(f"  - {m['name']}{status}")

        if graph_context.get("imperfections"):
            context_parts.append("**Top imperfections (ranked by VFE)**:")
            for imp in graph_context["imperfections"][:3]:
                context_parts.append(
                    f"  - {imp['metric_name']}: severity={imp['severity']}, "
                    f"blocker={imp['is_blocker']}, VFE={imp['vfe_score']}"
                )

        if graph_context.get("vfe_current") is not None:
            context_parts.append(f"**VFE (system surprise)**: {graph_context['vfe_current']}")

        if graph_context.get("active_hires"):
            context_parts.append("**Active hires**:")
            for h in graph_context["active_hires"]:
                context_parts.append(f"  - {h['name']} ({h['type']})")

        if extraction.get("entities"):
            context_parts.append(f"**Entities extracted from this message**: {len(extraction['entities'])}")

        context_text = "\n".join(context_parts)

        user_prompt = f"""The user said: "{user_message}"

Current graph state:
{context_text}

Generate a helpful, grounded response. Reference specific entities and metrics from the graph state. Suggest a concrete next step."""

        try:
            return await self._llm.complete(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=600,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning("LLM response generation failed: %s", e)
            return self._fallback_respond(intent, extraction, graph_context)

    def _fallback_respond(
        self,
        intent: str,
        extraction: dict[str, Any],
        graph_context: dict[str, Any],
    ) -> str:
        """Rule-based response when LLM is unavailable.

        Unlike JobOS 3.0's static templates, this still references
        actual graph state.
        """
        parts: list[str] = []

        # Acknowledge what was extracted
        entities = extraction.get("entities", [])
        if entities:
            names = [e.get("name", "entity") for e in entities]
            parts.append(f"Registered: {', '.join(names)}.")

        facts = extraction.get("facts", [])
        if facts:
            for f in facts:
                parts.append(f"Recorded {f.get('metric_name', 'metric')}: {f.get('value')}.")

        # Report graph state
        if graph_context.get("job"):
            j = graph_context["job"]
            parts.append(f"Active job: \"{j['statement']}\".")

        if graph_context.get("imperfections"):
            top = graph_context["imperfections"][0]
            parts.append(
                f"Top blocker: {top['metric_name']} "
                f"(severity={top['severity']}, VFE={top['vfe_score']})."
            )

        if graph_context.get("vfe_current") is not None and graph_context["vfe_current"] > 0:
            parts.append(f"System surprise (VFE): {graph_context['vfe_current']}.")

        # Suggest next step based on intent
        if intent == "define_job":
            parts.append("Next: define success metrics with target values so I can track imperfections.")
        elif intent == "report_metric":
            parts.append("Next: I'll recompute imperfections. Check the top blocker above.")
        elif intent == "describe_problem":
            parts.append("Next: frame this as a measurable metric so we can track progress.")
        elif intent == "propose_solution":
            parts.append("Next: use the hiring flow to formally hire this capability and track its impact.")
        elif intent == "ask_question":
            parts.append("I can help you define jobs, track metrics, and hire solutions. What would you like to focus on?")
        else:
            if not graph_context.get("job"):
                parts.append("Start by describing a goal you're working toward.")
            elif not graph_context.get("metrics"):
                parts.append("Next: define how you'll measure success for this job.")
            else:
                parts.append("Report updated metrics so I can track your progress.")

        return " ".join(parts) if parts else "Tell me about a goal you're working toward."

    # ─── Helpers ─────────────────────────────────────────

    async def _resolve_active_job(
        self,
        explicit_job_id: str | None,
        created_entities: list[EntityBase],
        is_new_session: bool = True,
    ) -> str | None:
        """Determine the active job for this turn.

        Priority:
        1. Explicitly provided job_id
        2. A Job entity just created in this turn
        3. Most recent job in the graph — only if this is a continuation
           of an existing session (is_new_session=False). On brand-new
           sessions we never fall back to prior graph state so that old
           jobs from previous conversations don't bleed into the response.
        """
        # If explicitly provided, use it
        if explicit_job_id:
            return explicit_job_id

        # If we just created a job, use it
        for e in created_entities:
            if e.entity_type == EntityType.JOB:
                return e.id

        # Only fall back to the most recent graph job within an ongoing session.
        if not is_new_session:
            jobs = await self._graph.list_entities(entity_type="job", limit=1)
            if jobs:
                return jobs[0].id

        return None
