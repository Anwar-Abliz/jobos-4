"""JobOS 4.0 — Job Hierarchy Generation Service.

Generates domain-specific Job Triads (hierarchies) using:
1. LLM-powered generation (when enabled) — produces contextually rich,
   domain-specific job hierarchies from user keywords
2. Template fallback (when LLM disabled) — produces structural
   hierarchies from pre-built domain templates

All generated jobs are persisted to Neo4j as Entity:Job nodes
connected by HIRES edges (the golden axiom applied recursively).

Key design decisions:
- LLM generates the content; kernel validates the structure
- Every job statement is validated against Axiom 5 (action verb)
- Hierarchy is persisted immediately (not ephemeral)
- Uses our own IP-safe terminology (Job Triad, not Job Pyramid)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.kernel.hierarchy import (
    JobTier,
    ExecutionCategory,
    ExperienceCategory,
    HierarchyJob,
    HierarchyEdge,
    HierarchyContext,
    HierarchyResult,
)
from jobos.kernel.job_statement import validate_verb
from jobos.ports.graph_port import GraphPort
from jobos.adapters.openai.llm_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  LLM Prompt for Hierarchy Generation
# ═══════════════════════════════════════════════════════════

HIERARCHY_SYSTEM_PROMPT = """You are the Job Hierarchy Generator for JobOS, a neurosymbolic Job-Centric Operating System.

Your task: generate a structured job hierarchy for a given business domain. The hierarchy has 4 tiers:

**T1 Strategic (1-2 jobs)**: The overarching WHY. The macro-goal that all other jobs serve. Must be singular and ambitious.
  Example: "Achieve sustainable product-market fit in the B2B SaaS segment"

**T2 Core Functional (3-5 jobs)**: The WHAT. Solution-agnostic outcomes that must be true for T1 to succeed. These are the pillars.
  Example: "Reduce customer acquisition cost below LTV/3"

**T3 Execution (8-15 jobs)**: The HOW. Concrete processes, actions, and tasks. Organized by category:
  - acquisition: getting resources/capabilities
  - preparation: setting up for execution
  - operation: core execution activities
  - monitoring: tracking and controlling
  - adaptation: adjusting when context changes

**T4 Experience (4-8 jobs)**: The FEEL. Emotional and social desired states of the people doing the work. Categories:
  - confidence: feeling in control, competent
  - recognition: being valued, acknowledged
  - growth: developing new capabilities
  - connection: feeling aligned with team/purpose
  - relief: avoiding stress, overwhelm, embarrassment

Rules:
1. Every job statement MUST start with an action verb (reduce, achieve, build, maintain, ensure, etc.)
2. T2 jobs must be solution-agnostic (no specific tools or products)
3. T3 jobs should be specific enough to be measurable
4. T4 jobs express emotional/social states as actionable goals ("build confidence that..." not just "feel good")
5. Each job should include 1-2 suggested metrics
6. Jobs should be genuinely relevant to the specified domain, not generic

Respond with JSON:
{
  "strategic": [
    {"statement": "...", "rationale": "...", "metrics_hint": ["..."]}
  ],
  "core_functional": [
    {"statement": "...", "rationale": "...", "metrics_hint": ["..."]}
  ],
  "execution": [
    {"statement": "...", "category": "acquisition|preparation|operation|monitoring|adaptation", "rationale": "...", "metrics_hint": ["..."]}
  ],
  "experience": [
    {"statement": "...", "category": "confidence|recognition|growth|connection|relief", "rationale": "...", "metrics_hint": ["..."]}
  ]
}"""


# ═══════════════════════════════════════════════════════════
#  Template Fallback (when LLM disabled)
# ═══════════════════════════════════════════════════════════

DOMAIN_TEMPLATES: dict[str, dict[str, list[dict]]] = {
    "b2b_saas": {
        "strategic": [
            {"statement": "achieve sustainable product-market fit and revenue growth", "rationale": "The macro-goal for any B2B SaaS", "metrics_hint": ["MRR growth rate", "Sean Ellis score"]},
        ],
        "core_functional": [
            {"statement": "reduce customer acquisition cost to sustainable levels", "rationale": "Unit economics must work", "metrics_hint": ["CAC", "CAC/LTV ratio"]},
            {"statement": "increase product activation and retention rates", "rationale": "PMF requires users staying", "metrics_hint": ["activation rate", "D30 retention"]},
            {"statement": "maintain reliable and scalable product infrastructure", "rationale": "Growth requires stability", "metrics_hint": ["uptime", "p95 latency"]},
            {"statement": "build predictable revenue pipeline", "rationale": "Investors and planning require predictability", "metrics_hint": ["MRR", "net revenue retention"]},
        ],
        "execution": [
            {"statement": "identify and validate ideal customer profile", "category": "acquisition", "rationale": "Must know who to target", "metrics_hint": ["ICP interviews completed"]},
            {"statement": "build inbound lead generation engine", "category": "acquisition", "rationale": "Scalable demand source", "metrics_hint": ["leads per week", "cost per lead"]},
            {"statement": "design and optimize onboarding flow", "category": "preparation", "rationale": "First impression drives activation", "metrics_hint": ["time to first value", "onboarding completion rate"]},
            {"statement": "execute product development sprints", "category": "operation", "rationale": "Core execution activity", "metrics_hint": ["velocity", "feature adoption rate"]},
            {"statement": "deliver customer success touchpoints", "category": "operation", "rationale": "Retention requires proactive engagement", "metrics_hint": ["NPS", "support ticket volume"]},
            {"statement": "monitor key SaaS metrics weekly", "category": "monitoring", "rationale": "Can't improve what you don't measure", "metrics_hint": ["MRR", "churn rate", "activation rate"]},
            {"statement": "track product usage patterns and drop-off points", "category": "monitoring", "rationale": "Data-driven product decisions", "metrics_hint": ["DAU/MAU", "feature usage distribution"]},
            {"statement": "adjust pricing based on willingness-to-pay signals", "category": "adaptation", "rationale": "Pricing is a lever for growth", "metrics_hint": ["ARPU", "conversion rate by plan"]},
            {"statement": "pivot acquisition channels based on CAC trends", "category": "adaptation", "rationale": "Channels saturate over time", "metrics_hint": ["CAC by channel", "channel efficiency ratio"]},
        ],
        "experience": [
            {"statement": "build confidence that the product solves a real problem", "category": "confidence", "rationale": "Founder conviction drives persistence", "metrics_hint": ["customer interview sentiment"]},
            {"statement": "earn recognition from customers as a trusted partner", "category": "recognition", "rationale": "Social proof accelerates growth", "metrics_hint": ["testimonials count", "referral rate"]},
            {"statement": "develop mastery of the target market dynamics", "category": "growth", "rationale": "Domain expertise compounds", "metrics_hint": ["market insights documented"]},
            {"statement": "maintain team alignment around shared mission", "category": "connection", "rationale": "Distributed teams need shared purpose", "metrics_hint": ["team alignment score"]},
            {"statement": "prevent burnout during high-growth phases", "category": "relief", "rationale": "Sustainable pace beats sprint culture", "metrics_hint": ["team satisfaction score"]},
        ],
    },
    "retail_operations": {
        "strategic": [
            {"statement": "optimize end-to-end retail operations for profitability and customer satisfaction", "rationale": "Dual objective: margin + experience", "metrics_hint": ["gross margin", "CSAT"]},
        ],
        "core_functional": [
            {"statement": "reduce inventory carrying costs while maintaining availability", "rationale": "Inventory is the biggest cost lever", "metrics_hint": ["inventory turnover", "stockout rate"]},
            {"statement": "increase store conversion rate and average transaction value", "rationale": "Revenue per visit drives profitability", "metrics_hint": ["conversion rate", "ATV"]},
            {"statement": "ensure consistent customer experience across locations", "rationale": "Brand promise requires consistency", "metrics_hint": ["mystery shopper score", "CSAT variance"]},
        ],
        "execution": [
            {"statement": "forecast demand using historical and seasonal patterns", "category": "acquisition", "rationale": "Buying right is the first step", "metrics_hint": ["forecast accuracy"]},
            {"statement": "negotiate vendor terms and manage supplier relationships", "category": "acquisition", "rationale": "Cost of goods determines margin", "metrics_hint": ["cost reduction %", "supplier lead time"]},
            {"statement": "train staff on product knowledge and service standards", "category": "preparation", "rationale": "Staff capability drives conversion", "metrics_hint": ["training completion rate", "product knowledge score"]},
            {"statement": "manage daily store operations and merchandising", "category": "operation", "rationale": "Core retail execution", "metrics_hint": ["planogram compliance", "sales per labor hour"]},
            {"statement": "process returns and handle customer complaints efficiently", "category": "operation", "rationale": "Recovery drives loyalty", "metrics_hint": ["return processing time", "complaint resolution rate"]},
            {"statement": "monitor foot traffic patterns and conversion funnels", "category": "monitoring", "rationale": "Understand the customer journey", "metrics_hint": ["foot traffic", "dwell time", "conversion funnel"]},
            {"statement": "adjust staffing levels based on traffic predictions", "category": "adaptation", "rationale": "Labor is the biggest controllable cost", "metrics_hint": ["labor cost ratio", "staff utilization"]},
        ],
        "experience": [
            {"statement": "build confidence in inventory decisions through data", "category": "confidence", "rationale": "Reduce buying anxiety", "metrics_hint": ["forecast confidence interval"]},
            {"statement": "earn recognition as a well-run operation from leadership", "category": "recognition", "rationale": "Career progression for store managers", "metrics_hint": ["performance ranking"]},
            {"statement": "develop cross-functional retail management skills", "category": "growth", "rationale": "Talent retention requires growth paths", "metrics_hint": ["skill assessments passed"]},
            {"statement": "reduce daily operational stress through better systems", "category": "relief", "rationale": "Operational chaos causes turnover", "metrics_hint": ["manager satisfaction", "system downtime"]},
        ],
    },
    "corporate_transformation": {
        "strategic": [
            {"statement": "drive successful organizational transformation that delivers measurable business outcomes", "rationale": "Transformation must produce results, not just activity", "metrics_hint": ["transformation ROI", "milestone completion rate"]},
        ],
        "core_functional": [
            {"statement": "align leadership team around transformation vision and priorities", "rationale": "Without alignment, execution fragments", "metrics_hint": ["leadership alignment score", "decision turnaround time"]},
            {"statement": "build change capability across the organization", "rationale": "Transformation is ongoing, not a one-time event", "metrics_hint": ["change readiness score", "adoption rate"]},
            {"statement": "deliver quick wins that demonstrate transformation value", "rationale": "Momentum requires visible progress", "metrics_hint": ["quick wins delivered", "stakeholder confidence"]},
            {"statement": "establish governance and measurement framework for transformation", "rationale": "Can't manage what you can't measure", "metrics_hint": ["KPI tracking coverage", "review cadence adherence"]},
        ],
        "execution": [
            {"statement": "assess current state capabilities and gaps", "category": "acquisition", "rationale": "Start from reality, not assumptions", "metrics_hint": ["capability assessment coverage"]},
            {"statement": "recruit transformation champions in each business unit", "category": "acquisition", "rationale": "Change needs local advocates", "metrics_hint": ["champions identified per unit"]},
            {"statement": "design target operating model and transition roadmap", "category": "preparation", "rationale": "Clear destination enables navigation", "metrics_hint": ["roadmap milestones defined"]},
            {"statement": "conduct workshops to align team understanding of strategy", "category": "preparation", "rationale": "Shared understanding enables autonomous execution", "metrics_hint": ["workshop completion rate", "comprehension score"]},
            {"statement": "execute pilot programs in selected business units", "category": "operation", "rationale": "Test before scale", "metrics_hint": ["pilot success rate", "lessons captured"]},
            {"statement": "scale successful pilots across the organization", "category": "operation", "rationale": "Proven approaches reduce risk", "metrics_hint": ["rollout completion rate"]},
            {"statement": "track adoption metrics and resistance patterns", "category": "monitoring", "rationale": "Early detection enables course correction", "metrics_hint": ["adoption rate", "resistance incidents"]},
            {"statement": "measure business impact of transformation initiatives", "category": "monitoring", "rationale": "Justify continued investment", "metrics_hint": ["revenue impact", "cost savings realized"]},
            {"statement": "adjust transformation approach based on feedback loops", "category": "adaptation", "rationale": "Rigid plans fail in complex systems", "metrics_hint": ["pivot count", "stakeholder feedback score"]},
        ],
        "experience": [
            {"statement": "build confidence among employees that transformation benefits them", "category": "confidence", "rationale": "Fear kills adoption", "metrics_hint": ["employee confidence survey"]},
            {"statement": "ensure leaders are recognized for transformation contributions", "category": "recognition", "rationale": "Incentives must align with desired behavior", "metrics_hint": ["transformation contributions in reviews"]},
            {"statement": "develop new skills that increase individual market value", "category": "growth", "rationale": "Self-interest drives engagement", "metrics_hint": ["skills acquired", "certification completions"]},
            {"statement": "maintain team cohesion during organizational restructuring", "category": "connection", "rationale": "Restructuring fractures relationships", "metrics_hint": ["team cohesion score", "voluntary turnover"]},
            {"statement": "reduce anxiety about job security during transition periods", "category": "relief", "rationale": "Uncertainty paralyzes action", "metrics_hint": ["employee sentiment score"]},
        ],
    },
}

# Normalize lookup keys
_TEMPLATE_ALIASES: dict[str, str] = {
    "saas": "b2b_saas", "b2b saas": "b2b_saas", "b2b_saas": "b2b_saas", "software": "b2b_saas",
    "retail": "retail_operations", "retail operations": "retail_operations", "retail_operations": "retail_operations", "store": "retail_operations", "ecommerce": "retail_operations",
    "transformation": "corporate_transformation", "corporate transformation": "corporate_transformation", "corporate_transformation": "corporate_transformation", "change management": "corporate_transformation",
}


# ═══════════════════════════════════════════════════════════
#  Service
# ═══════════════════════════════════════════════════════════

class HierarchyService:
    """Generates and persists domain-specific Job Triads."""

    def __init__(self, graph: GraphPort, llm: OpenAIAdapter | None = None) -> None:
        self._graph = graph
        self._llm = llm

    async def generate(self, context: HierarchyContext) -> HierarchyResult:
        """Generate a Job Triad hierarchy for the given domain.

        Flow:
        1. Generate jobs (LLM or template fallback)
        2. Validate all statements (Axiom 5)
        3. Build HIRES edges between tiers
        4. Persist all entities and edges to Neo4j
        5. Return the complete hierarchy
        """
        # Step 1: Generate raw hierarchy
        if self._llm:
            raw = await self._llm_generate(context)
        else:
            raw = self._template_generate(context)

        # Step 2: Build typed hierarchy
        result = self._build_hierarchy(raw, context)

        # Step 3: Persist to Neo4j
        await self._persist(result)

        return result

    async def get(self, hierarchy_id: str) -> HierarchyResult | None:
        """Retrieve a previously generated hierarchy by its root job ID."""
        # The hierarchy ID is the strategic job's ID
        root = await self._graph.get_entity(hierarchy_id)
        if not root:
            return None

        # Traverse HIRES edges to reconstruct
        all_jobs: list[HierarchyJob] = []
        all_edges: list[HierarchyEdge] = []
        visited: set[str] = set()

        async def traverse(job_id: str):
            if job_id in visited:
                return
            visited.add(job_id)
            entity = await self._graph.get_entity(job_id)
            if not entity or entity.entity_type != EntityType.JOB:
                return

            props = entity.properties
            tier_str = props.get("hierarchy_tier", "T1_strategic")
            try:
                tier = JobTier(tier_str)
            except ValueError:
                tier = JobTier.STRATEGIC

            all_jobs.append(HierarchyJob(
                id=entity.id,
                tier=tier,
                statement=entity.statement,
                category=props.get("hierarchy_category", ""),
                rationale=props.get("hierarchy_rationale", ""),
                metrics_hint=props.get("metrics_hint", []),
            ))

            children = await self._graph.get_neighbors(job_id, edge_type="HIRES", direction="outgoing")
            for child in children:
                all_edges.append(HierarchyEdge(parent_id=job_id, child_id=child.id))
                await traverse(child.id)

        await traverse(hierarchy_id)

        if not all_jobs:
            return None

        return HierarchyResult(
            id=hierarchy_id,
            context=HierarchyContext(domain=root.properties.get("hierarchy_domain", "")),
            jobs=all_jobs,
            edges=all_edges,
        )

    # ─── LLM Generation ─────────────────────────────────

    async def _llm_generate(self, context: HierarchyContext) -> dict[str, list[dict]]:
        """Use LLM to generate domain-specific hierarchy."""
        keywords_str = ", ".join(context.keywords) if context.keywords else ""
        user_prompt = f"""Generate a Job Triad hierarchy for this domain:

Domain: {context.domain}
Keywords: {keywords_str}
Actor: {context.actor or 'the organization'}
Goal: {context.goal or 'not specified — infer from domain'}
Constraints: {context.constraints or 'none specified'}

Generate jobs that are specific and relevant to this exact domain. Avoid generic business platitudes."""

        try:
            raw = await self._llm.complete_json(
                system_prompt=HIERARCHY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=2000,
                temperature=0.4,
            )
            if raw and any(raw.get(k) for k in ["strategic", "core_functional", "execution", "experience"]):
                return raw
        except Exception as e:
            logger.warning("LLM hierarchy generation failed, using template fallback: %s", e)

        return self._template_generate(context)

    # ─── Template Fallback ───────────────────────────────

    def _template_generate(self, context: HierarchyContext) -> dict[str, list[dict]]:
        """Generate from pre-built domain templates."""
        domain_key = context.domain.lower().strip().replace(" ", "_")
        # Try alias lookup
        template_key = _TEMPLATE_ALIASES.get(domain_key)
        if not template_key:
            # Try fuzzy match on keywords
            for kw in context.keywords:
                template_key = _TEMPLATE_ALIASES.get(kw.lower().strip())
                if template_key:
                    break

        if template_key and template_key in DOMAIN_TEMPLATES:
            return DOMAIN_TEMPLATES[template_key]

        # Default: use B2B SaaS as the most generic template
        logger.info("No template for domain '%s', using generic template", context.domain)
        return DOMAIN_TEMPLATES["b2b_saas"]

    # ─── Build Typed Hierarchy ───────────────────────────

    def _build_hierarchy(
        self,
        raw: dict[str, list[dict]],
        context: HierarchyContext,
    ) -> HierarchyResult:
        """Convert raw LLM/template output into a typed HierarchyResult."""
        jobs: list[HierarchyJob] = []
        edges: list[HierarchyEdge] = []

        # T1: Strategic
        t1_jobs: list[HierarchyJob] = []
        for item in raw.get("strategic", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.STRATEGIC,
                statement=stmt,
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
            )
            t1_jobs.append(job)
            jobs.append(job)

        # T2: Core Functional
        t2_jobs: list[HierarchyJob] = []
        for item in raw.get("core_functional", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.CORE_FUNCTIONAL,
                statement=stmt,
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
            )
            t2_jobs.append(job)
            jobs.append(job)

        # T1 HIRES T2
        for t1 in t1_jobs:
            for t2 in t2_jobs:
                edges.append(HierarchyEdge(parent_id=t1.id, child_id=t2.id))

        # T3: Execution
        t3_jobs: list[HierarchyJob] = []
        for item in raw.get("execution", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.EXECUTION,
                statement=stmt,
                category=item.get("category", "operation"),
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
            )
            t3_jobs.append(job)
            jobs.append(job)

        # T2 HIRES T3 (distribute execution jobs across core jobs)
        if t2_jobs and t3_jobs:
            chunk_size = max(1, len(t3_jobs) // len(t2_jobs))
            for i, t2 in enumerate(t2_jobs):
                start = i * chunk_size
                end = start + chunk_size if i < len(t2_jobs) - 1 else len(t3_jobs)
                for t3 in t3_jobs[start:end]:
                    edges.append(HierarchyEdge(parent_id=t2.id, child_id=t3.id))

        # T4: Experience
        t4_jobs: list[HierarchyJob] = []
        for item in raw.get("experience", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.EXPERIENCE,
                statement=stmt,
                category=item.get("category", "confidence"),
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
            )
            t4_jobs.append(job)
            jobs.append(job)

        # T2 HIRES T4 (experience jobs support all core jobs)
        for t2 in t2_jobs:
            for t4 in t4_jobs:
                edges.append(HierarchyEdge(parent_id=t2.id, child_id=t4.id, strength=0.5))

        # Build summary
        summary = {
            "T1_strategic": len(t1_jobs),
            "T2_core": len(t2_jobs),
            "T3_execution": len(t3_jobs),
            "T4_experience": len(t4_jobs),
            "total_jobs": len(jobs),
            "total_edges": len(edges),
        }

        hierarchy_id = t1_jobs[0].id if t1_jobs else _uid()
        return HierarchyResult(
            id=hierarchy_id,
            context=context,
            jobs=jobs,
            edges=edges,
            summary=summary,
        )

    # ─── Persist to Neo4j ────────────────────────────────

    async def _persist(self, result: HierarchyResult) -> None:
        """Persist all hierarchy jobs and edges to Neo4j."""
        for job in result.jobs:
            entity = EntityBase(
                id=job.id,
                name=job.statement[:80],
                statement=job.statement,
                entity_type=EntityType.JOB,
                status="active",
                labels=["Job"],
                properties={
                    "job_type": "core_functional",
                    "job_nature": "project",
                    "level": {"T1_strategic": 0, "T2_core": 1, "T3_execution": 2, "T4_experience": 3}.get(job.tier.value, 0),
                    "hierarchy_tier": job.tier.value,
                    "hierarchy_category": job.category,
                    "hierarchy_rationale": job.rationale,
                    "hierarchy_domain": result.context.domain,
                    "metrics_hint": job.metrics_hint,
                    "vfe_current": 0.0,
                },
            )
            await self._graph.save_entity(entity)

        for edge in result.edges:
            await self._graph.create_edge(
                source_id=edge.parent_id,
                target_id=edge.child_id,
                edge_type="HIRES",
                properties={"strength": edge.strength, "source": "hierarchy_generator"},
            )

        logger.info(
            "Persisted hierarchy: %d jobs, %d edges for domain '%s'",
            len(result.jobs), len(result.edges), result.context.domain,
        )

    # ─── Helpers ─────────────────────────────────────────

    @staticmethod
    def _ensure_verb(statement: str) -> str:
        """Ensure statement starts with an action verb (Axiom 5)."""
        if not statement:
            return "achieve unspecified goal"
        if validate_verb(statement):
            return statement
        return f"achieve {statement}"
