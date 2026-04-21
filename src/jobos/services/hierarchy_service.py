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
    MicroJobCategory,
    HierarchyJob,
    HierarchyEdge,
    HierarchyContext,
    HierarchyResult,
)
from jobos.kernel.job_statement import validate_verb
from jobos.kernel.generative_model import GenerativeModel, map_tier_to_generative_model
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
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
  - consumption: the consumption chain — purchasing, receiving, setting up, learning to use, maintaining, and upgrading/disposing. Include 2-4 where relevant.

**T4 Micro-Job (4-8 jobs)**: The EXECUTE. The smallest discrete, self-similar functional actions that decompose T3 steps. Categories:
  - setup: preparing inputs and environment for the action
  - act: performing the atomic action itself
  - verify: checking the outcome against expected results
  - cleanup: releasing resources and handing off

**Related Jobs (2-4 jobs)**: Cross-cutting T2-level jobs that support multiple Core Functional jobs. These handle shared concerns like stakeholder communication, compliance, knowledge management, or cross-functional coordination. They are NOT part of the main hierarchy tree but SUPPORT the T2 jobs.

Rules:
1. Every job statement MUST start with an action verb (reduce, achieve, build, maintain, ensure, etc.)
2. T2 jobs must be solution-agnostic (no specific tools or products)
3. T3 jobs should be specific enough to be measurable
4. T4 jobs are the smallest functional units — concrete, atomic actions with clear completion criteria
5. Each job should include 1-2 suggested metrics
6. Jobs should be genuinely relevant to the specified domain, not generic
7. Assign executor_type "HUMAN" or "AI" per job. HUMAN = requires judgment, creativity, empathy. AI = can be systematically automated. Default HUMAN when uncertain.

Note: Experience (emotional/social FEEL) is Dimension A, orthogonal to this hierarchy. Do not include experience/emotional jobs in the tiers.

**CRITICAL — Language Rule**: You MUST generate ALL job statements, rationales, and metrics_hint values in the SAME LANGUAGE as the user's input. If the user writes in Chinese, output Chinese. If the user writes in French, output French. Match the user's language exactly. Do NOT translate to English unless the user wrote in English.

Respond with JSON:
{
  "strategic": [
    {"statement": "...", "rationale": "...", "metrics_hint": ["..."], "executor_type": "HUMAN"}
  ],
  "core_functional": [
    {"statement": "...", "rationale": "...", "metrics_hint": ["..."], "executor_type": "HUMAN"}
  ],
  "execution": [
    {"statement": "...", "category": "acquisition|preparation|operation|monitoring|adaptation|consumption", "rationale": "...", "metrics_hint": ["..."], "executor_type": "HUMAN|AI"}
  ],
  "micro_job": [
    {"statement": "...", "category": "setup|act|verify|cleanup", "rationale": "...", "metrics_hint": ["..."], "executor_type": "HUMAN|AI"}
  ],
  "related_jobs": [
    {"statement": "...", "rationale": "...", "metrics_hint": ["..."], "executor_type": "HUMAN|AI"}
  ]
}"""


# ═══════════════════════════════════════════════════════════
#  Template Fallback (when LLM disabled)
# ═══════════════════════════════════════════════════════════

DOMAIN_TEMPLATES: dict[str, dict[str, list[dict]]] = {
    "b2b_saas": {
        "strategic": [
            {"statement": "achieve sustainable product-market fit and revenue growth", "rationale": "The macro-goal for any B2B SaaS", "metrics_hint": ["MRR growth rate", "Sean Ellis score"], "executor_type": "HUMAN"},
        ],
        "core_functional": [
            {"statement": "reduce customer acquisition cost to sustainable levels", "rationale": "Unit economics must work", "metrics_hint": ["CAC", "CAC/LTV ratio"], "executor_type": "HUMAN"},
            {"statement": "increase product activation and retention rates", "rationale": "PMF requires users staying", "metrics_hint": ["activation rate", "D30 retention"], "executor_type": "HUMAN"},
            {"statement": "maintain reliable and scalable product infrastructure", "rationale": "Growth requires stability", "metrics_hint": ["uptime", "p95 latency"], "executor_type": "AI"},
            {"statement": "build predictable revenue pipeline", "rationale": "Investors and planning require predictability", "metrics_hint": ["MRR", "net revenue retention"], "executor_type": "HUMAN"},
        ],
        "execution": [
            {"statement": "identify and validate ideal customer profile", "category": "acquisition", "rationale": "Must know who to target", "metrics_hint": ["ICP interviews completed"], "executor_type": "HUMAN"},
            {"statement": "build inbound lead generation engine", "category": "acquisition", "rationale": "Scalable demand source", "metrics_hint": ["leads per week", "cost per lead"], "executor_type": "HUMAN"},
            {"statement": "design and optimize onboarding flow", "category": "preparation", "rationale": "First impression drives activation", "metrics_hint": ["time to first value", "onboarding completion rate"], "executor_type": "HUMAN"},
            {"statement": "execute product development sprints", "category": "operation", "rationale": "Core execution activity", "metrics_hint": ["velocity", "feature adoption rate"], "executor_type": "HUMAN"},
            {"statement": "deliver customer success touchpoints", "category": "operation", "rationale": "Retention requires proactive engagement", "metrics_hint": ["NPS", "support ticket volume"], "executor_type": "HUMAN"},
            {"statement": "monitor key SaaS metrics weekly", "category": "monitoring", "rationale": "Can't improve what you don't measure", "metrics_hint": ["MRR", "churn rate", "activation rate"], "executor_type": "AI"},
            {"statement": "track product usage patterns and drop-off points", "category": "monitoring", "rationale": "Data-driven product decisions", "metrics_hint": ["DAU/MAU", "feature usage distribution"], "executor_type": "AI"},
            {"statement": "adjust pricing based on willingness-to-pay signals", "category": "adaptation", "rationale": "Pricing is a lever for growth", "metrics_hint": ["ARPU", "conversion rate by plan"], "executor_type": "HUMAN"},
            {"statement": "pivot acquisition channels based on CAC trends", "category": "adaptation", "rationale": "Channels saturate over time", "metrics_hint": ["CAC by channel", "channel efficiency ratio"], "executor_type": "HUMAN"},
            {"statement": "manage subscription lifecycle from purchase to renewal", "category": "consumption", "rationale": "Full customer journey requires end-to-end management", "metrics_hint": ["renewal rate", "time to first purchase"], "executor_type": "HUMAN"},
            {"statement": "automate user provisioning and setup workflows", "category": "consumption", "rationale": "Streamlined setup reduces time-to-value", "metrics_hint": ["setup completion rate", "provisioning time"], "executor_type": "AI"},
        ],
        "micro_job": [
            {"statement": "prepare customer interview script and schedule session", "category": "setup", "rationale": "Structured discovery yields better ICP data", "metrics_hint": ["interviews scheduled"], "executor_type": "HUMAN"},
            {"statement": "execute A/B test on onboarding variant", "category": "act", "rationale": "Atomic test action for activation improvement", "metrics_hint": ["test completion rate"], "executor_type": "AI"},
            {"statement": "verify feature adoption metric against release target", "category": "verify", "rationale": "Validate sprint outcome at atomic level", "metrics_hint": ["adoption delta"], "executor_type": "AI"},
            {"statement": "archive stale leads and update CRM pipeline status", "category": "cleanup", "rationale": "Clean pipeline improves forecast accuracy", "metrics_hint": ["pipeline hygiene score"], "executor_type": "AI"},
            {"statement": "configure monitoring alert thresholds for SLO breach", "category": "setup", "rationale": "Early detection prevents outages", "metrics_hint": ["alert coverage %"], "executor_type": "AI"},
        ],
        "related_jobs": [
            {"statement": "coordinate cross-functional communication between product, sales, and engineering", "rationale": "Shared concerns across all core functional jobs", "metrics_hint": ["cross-team meeting cadence", "decision turnaround time"], "executor_type": "HUMAN"},
            {"statement": "maintain compliance and data privacy standards", "rationale": "Regulatory obligations cut across all operations", "metrics_hint": ["compliance audit score", "data breach incidents"], "executor_type": "HUMAN"},
            {"statement": "consolidate and share organizational knowledge across teams", "rationale": "Knowledge management supports all pillars", "metrics_hint": ["documentation coverage", "knowledge base usage"], "executor_type": "AI"},
        ],
    },
    "retail_operations": {
        "strategic": [
            {"statement": "optimize end-to-end retail operations for profitability and customer satisfaction", "rationale": "Dual objective: margin + experience", "metrics_hint": ["gross margin", "CSAT"], "executor_type": "HUMAN"},
        ],
        "core_functional": [
            {"statement": "reduce inventory carrying costs while maintaining availability", "rationale": "Inventory is the biggest cost lever", "metrics_hint": ["inventory turnover", "stockout rate"], "executor_type": "HUMAN"},
            {"statement": "increase store conversion rate and average transaction value", "rationale": "Revenue per visit drives profitability", "metrics_hint": ["conversion rate", "ATV"], "executor_type": "HUMAN"},
            {"statement": "ensure consistent customer experience across locations", "rationale": "Brand promise requires consistency", "metrics_hint": ["mystery shopper score", "CSAT variance"], "executor_type": "HUMAN"},
        ],
        "execution": [
            {"statement": "forecast demand using historical and seasonal patterns", "category": "acquisition", "rationale": "Buying right is the first step", "metrics_hint": ["forecast accuracy"], "executor_type": "AI"},
            {"statement": "negotiate vendor terms and manage supplier relationships", "category": "acquisition", "rationale": "Cost of goods determines margin", "metrics_hint": ["cost reduction %", "supplier lead time"], "executor_type": "HUMAN"},
            {"statement": "train staff on product knowledge and service standards", "category": "preparation", "rationale": "Staff capability drives conversion", "metrics_hint": ["training completion rate", "product knowledge score"], "executor_type": "HUMAN"},
            {"statement": "manage daily store operations and merchandising", "category": "operation", "rationale": "Core retail execution", "metrics_hint": ["planogram compliance", "sales per labor hour"], "executor_type": "HUMAN"},
            {"statement": "process returns and handle customer complaints efficiently", "category": "operation", "rationale": "Recovery drives loyalty", "metrics_hint": ["return processing time", "complaint resolution rate"], "executor_type": "HUMAN"},
            {"statement": "monitor foot traffic patterns and conversion funnels", "category": "monitoring", "rationale": "Understand the customer journey", "metrics_hint": ["foot traffic", "dwell time", "conversion funnel"], "executor_type": "AI"},
            {"statement": "adjust staffing levels based on traffic predictions", "category": "adaptation", "rationale": "Labor is the biggest controllable cost", "metrics_hint": ["labor cost ratio", "staff utilization"], "executor_type": "AI"},
            {"statement": "manage product lifecycle from procurement through disposal", "category": "consumption", "rationale": "Full product journey impacts margin and waste", "metrics_hint": ["shrinkage rate", "product lifecycle cost"], "executor_type": "HUMAN"},
            {"statement": "automate inventory replenishment based on sales velocity", "category": "consumption", "rationale": "Timely restocking prevents lost sales", "metrics_hint": ["restock lead time", "auto-reorder accuracy"], "executor_type": "AI"},
        ],
        "micro_job": [
            {"statement": "prepare daily restock list from overnight sales data", "category": "setup", "rationale": "Atomic input for replenishment cycle", "metrics_hint": ["restock accuracy"], "executor_type": "AI"},
            {"statement": "execute planogram reset for promotional display", "category": "act", "rationale": "Smallest merchandising action unit", "metrics_hint": ["planogram compliance"], "executor_type": "HUMAN"},
            {"statement": "verify cash register reconciliation against POS totals", "category": "verify", "rationale": "End-of-shift integrity check", "metrics_hint": ["reconciliation variance"], "executor_type": "AI"},
            {"statement": "archive expired promotional materials and reset signage", "category": "cleanup", "rationale": "Clean visual environment for next promotion", "metrics_hint": ["signage compliance"], "executor_type": "HUMAN"},
        ],
        "related_jobs": [
            {"statement": "manage vendor compliance and quality assurance across suppliers", "rationale": "Cross-cutting concern for all inventory and customer experience", "metrics_hint": ["vendor compliance rate", "quality incident count"], "executor_type": "HUMAN"},
            {"statement": "coordinate marketing and merchandising calendars across locations", "rationale": "Alignment ensures consistent execution", "metrics_hint": ["calendar adherence rate", "promotion sync score"], "executor_type": "HUMAN"},
        ],
    },
    "corporate_transformation": {
        "strategic": [
            {"statement": "drive successful organizational transformation that delivers measurable business outcomes", "rationale": "Transformation must produce results, not just activity", "metrics_hint": ["transformation ROI", "milestone completion rate"], "executor_type": "HUMAN"},
        ],
        "core_functional": [
            {"statement": "align leadership team around transformation vision and priorities", "rationale": "Without alignment, execution fragments", "metrics_hint": ["leadership alignment score", "decision turnaround time"], "executor_type": "HUMAN"},
            {"statement": "build change capability across the organization", "rationale": "Transformation is ongoing, not a one-time event", "metrics_hint": ["change readiness score", "adoption rate"], "executor_type": "HUMAN"},
            {"statement": "deliver quick wins that demonstrate transformation value", "rationale": "Momentum requires visible progress", "metrics_hint": ["quick wins delivered", "stakeholder confidence"], "executor_type": "HUMAN"},
            {"statement": "establish governance and measurement framework for transformation", "rationale": "Can't manage what you can't measure", "metrics_hint": ["KPI tracking coverage", "review cadence adherence"], "executor_type": "HUMAN"},
        ],
        "execution": [
            {"statement": "assess current state capabilities and gaps", "category": "acquisition", "rationale": "Start from reality, not assumptions", "metrics_hint": ["capability assessment coverage"], "executor_type": "HUMAN"},
            {"statement": "recruit transformation champions in each business unit", "category": "acquisition", "rationale": "Change needs local advocates", "metrics_hint": ["champions identified per unit"], "executor_type": "HUMAN"},
            {"statement": "design target operating model and transition roadmap", "category": "preparation", "rationale": "Clear destination enables navigation", "metrics_hint": ["roadmap milestones defined"], "executor_type": "HUMAN"},
            {"statement": "conduct workshops to align team understanding of strategy", "category": "preparation", "rationale": "Shared understanding enables autonomous execution", "metrics_hint": ["workshop completion rate", "comprehension score"], "executor_type": "HUMAN"},
            {"statement": "execute pilot programs in selected business units", "category": "operation", "rationale": "Test before scale", "metrics_hint": ["pilot success rate", "lessons captured"], "executor_type": "HUMAN"},
            {"statement": "scale successful pilots across the organization", "category": "operation", "rationale": "Proven approaches reduce risk", "metrics_hint": ["rollout completion rate"], "executor_type": "HUMAN"},
            {"statement": "track adoption metrics and resistance patterns", "category": "monitoring", "rationale": "Early detection enables course correction", "metrics_hint": ["adoption rate", "resistance incidents"], "executor_type": "AI"},
            {"statement": "measure business impact of transformation initiatives", "category": "monitoring", "rationale": "Justify continued investment", "metrics_hint": ["revenue impact", "cost savings realized"], "executor_type": "AI"},
            {"statement": "adjust transformation approach based on feedback loops", "category": "adaptation", "rationale": "Rigid plans fail in complex systems", "metrics_hint": ["pivot count", "stakeholder feedback score"], "executor_type": "HUMAN"},
            {"statement": "manage tool and process adoption lifecycle across units", "category": "consumption", "rationale": "Tools go through purchase-learn-use-maintain cycle", "metrics_hint": ["tool adoption rate", "training completion per tool"], "executor_type": "HUMAN"},
        ],
        "micro_job": [
            {"statement": "prepare stakeholder interview guide for capability assessment", "category": "setup", "rationale": "Structured input for gap analysis", "metrics_hint": ["interviews prepared"], "executor_type": "HUMAN"},
            {"statement": "execute single-unit pilot kickoff session", "category": "act", "rationale": "Atomic launch action for pilot", "metrics_hint": ["kickoff completion"], "executor_type": "HUMAN"},
            {"statement": "verify adoption metric against pilot success threshold", "category": "verify", "rationale": "Go/no-go gate for scale decision", "metrics_hint": ["threshold met (bool)"], "executor_type": "AI"},
            {"statement": "archive completed pilot documentation and lessons learned", "category": "cleanup", "rationale": "Knowledge capture for next unit", "metrics_hint": ["documents archived"], "executor_type": "AI"},
            {"statement": "distribute workshop materials to next business unit cohort", "category": "setup", "rationale": "Preparation for rollout continuation", "metrics_hint": ["materials distributed"], "executor_type": "AI"},
        ],
        "related_jobs": [
            {"statement": "manage stakeholder communication and expectation alignment", "rationale": "Communication cuts across all transformation pillars", "metrics_hint": ["stakeholder satisfaction score", "communication cadence"], "executor_type": "HUMAN"},
            {"statement": "ensure regulatory and compliance alignment during transformation", "rationale": "Compliance is a shared concern across all business units", "metrics_hint": ["compliance check pass rate", "regulatory incidents"], "executor_type": "HUMAN"},
            {"statement": "consolidate lessons learned and best practices across pilots", "rationale": "Knowledge management supports scaling", "metrics_hint": ["lessons captured per pilot", "reuse rate"], "executor_type": "AI"},
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

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort | None = None,
        llm: OpenAIAdapter | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
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
                executor_type=props.get("executor_type", "HUMAN"),
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
                max_tokens=4000,
                temperature=0.4,
            )
            if raw and any(raw.get(k) for k in ["strategic", "core_functional", "execution", "micro_job"]):
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

        # Derive a stable scope_id from the domain (used for Axiom 6 root_token)
        scope_id = context.domain.lower().replace(" ", "_") or _uid()

        # T1: Strategic — root jobs (Axiom 6: each gets root_token='ROOT' + scope_id)
        t1_jobs: list[HierarchyJob] = []
        for item in raw.get("strategic", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.STRATEGIC,
                statement=stmt,
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
                root_token="ROOT",
                scope_id=scope_id,
                executor_type=item.get("executor_type", "HUMAN"),
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
                executor_type=item.get("executor_type", "HUMAN"),
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
                executor_type=item.get("executor_type", "HUMAN"),
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

        # T4: Micro-Job — smallest discrete functional actions (children of T3)
        # These are regular functional jobs with action verbs and metrics.
        t4_jobs: list[HierarchyJob] = []
        for item in raw.get("micro_job", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.MICRO_JOB,
                statement=stmt,
                category=item.get("category", "act"),
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
                executor_type=item.get("executor_type", "HUMAN"),
            )
            t4_jobs.append(job)
            jobs.append(job)

        # T3 HIRES T4 (distribute micro-jobs across execution jobs)
        if t3_jobs and t4_jobs:
            chunk_size = max(1, len(t4_jobs) // len(t3_jobs))
            for i, t3 in enumerate(t3_jobs):
                start = i * chunk_size
                end = start + chunk_size if i < len(t3_jobs) - 1 else len(t4_jobs)
                for t4 in t4_jobs[start:end]:
                    edges.append(HierarchyEdge(parent_id=t3.id, child_id=t4.id))

        # Related jobs: cross-cutting T2-level jobs that support multiple core functional jobs
        related: list[HierarchyJob] = []
        for item in raw.get("related_jobs", []):
            stmt = self._ensure_verb(item.get("statement", ""))
            job = HierarchyJob(
                tier=JobTier.CORE_FUNCTIONAL,
                statement=stmt,
                category="related",
                rationale=item.get("rationale", ""),
                metrics_hint=item.get("metrics_hint", []),
                executor_type=item.get("executor_type", "HUMAN"),
            )
            related.append(job)

        # Build GenerativeModel per job (tier → field mapping)
        generative_models: dict[str, GenerativeModel] = {
            job.id: map_tier_to_generative_model(job)
            for job in jobs
        }

        # Count consumption category T3 jobs
        t3_consumption = sum(
            1 for j in t3_jobs if j.category == "consumption"
        )

        # Build summary
        summary = {
            "T1_strategic": len(t1_jobs),
            "T2_core": len(t2_jobs),
            "T3_execution": len(t3_jobs),
            "T3_consumption": t3_consumption,
            "T4_micro": len(t4_jobs),
            "related_jobs": len(related),
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
            generative_models=generative_models,
            related_jobs=related,
        )

    # ─── Persist to Neo4j ────────────────────────────────

    async def _persist(self, result: HierarchyResult) -> None:
        """Persist all hierarchy jobs and edges to Neo4j, with per-tier handling.

        Per-tier behaviour:
          T1 Strategic      → Entity:Job + root_token='ROOT' + scope_id in properties
          T2 Core Functional → Entity:Job + job_metrics scaffold in PostgreSQL
          T3 Execution      → Entity:Job + job_metrics scaffold in PostgreSQL
          T4 Micro-Job      → Entity:Job + job_metrics scaffold in PostgreSQL
                              (T4 is functional, not emotional — no :Experience label)
        """
        tier_level = {
            JobTier.STRATEGIC: 0,
            JobTier.CORE_FUNCTIONAL: 1,
            JobTier.EXECUTION: 2,
            JobTier.MICRO_JOB: 3,
        }

        for job in result.jobs:
            is_strategic = job.tier == JobTier.STRATEGIC

            props: dict = {
                "job_type": "core_functional",
                "job_nature": "project",
                "level": tier_level.get(job.tier, 0),
                "hierarchy_tier": job.tier.value,
                "hierarchy_category": job.category,
                "hierarchy_rationale": job.rationale,
                "hierarchy_domain": result.context.domain,
                "metrics_hint": job.metrics_hint,
                "vfe_current": 0.0,
                "executor_type": job.executor_type or "HUMAN",
            }

            if is_strategic:
                props["root_token"] = job.root_token  # "ROOT"
                props["scope_id"] = job.scope_id

            entity = EntityBase(
                id=job.id,
                name=job.statement[:80],
                statement=job.statement,
                entity_type=EntityType.JOB,
                status="active",
                labels=["Job"],
                properties=props,
            )
            await self._graph.save_entity(entity)

            # All tiers (T2, T3, T4) get job_metrics scaffold
            if self._db and job.tier in (
                JobTier.CORE_FUNCTIONAL, JobTier.EXECUTION, JobTier.MICRO_JOB,
            ):
                metrics: dict[str, float] = {
                    hint: 0.0 for hint in job.metrics_hint
                }
                bounds: dict[str, list] = {
                    hint: [0.0, 1.0] for hint in job.metrics_hint
                }
                await self._db.insert_job_metric(
                    job_id=job.id,
                    metrics=metrics,
                    bounds=bounds,
                    context_hash=result.context.domain,
                )

        for edge in result.edges:
            await self._graph.create_edge(
                source_id=edge.parent_id,
                target_id=edge.child_id,
                edge_type="HIRES",
                properties={"strength": edge.strength, "source": "hierarchy_generator"},
            )

        # Persist related jobs as Entity:Job nodes with is_related_job flag
        t2_ids = [j.id for j in result.jobs if j.tier == JobTier.CORE_FUNCTIONAL]
        for rj in result.related_jobs:
            props = {
                "job_type": "core_functional",
                "job_nature": "project",
                "level": 1,
                "hierarchy_tier": rj.tier.value,
                "hierarchy_category": "related",
                "hierarchy_rationale": rj.rationale,
                "hierarchy_domain": result.context.domain,
                "metrics_hint": rj.metrics_hint,
                "vfe_current": 0.0,
                "executor_type": rj.executor_type or "HUMAN",
                "is_related_job": True,
            }
            entity = EntityBase(
                id=rj.id,
                name=rj.statement[:80],
                statement=rj.statement,
                entity_type=EntityType.JOB,
                status="active",
                labels=["Job"],
                properties=props,
            )
            await self._graph.save_entity(entity)

            # Create SUPPORTS edges from related job to all T2 jobs
            for t2_id in t2_ids:
                await self._graph.create_edge(
                    source_id=rj.id,
                    target_id=t2_id,
                    edge_type="SUPPORTS",
                    properties={"source": "hierarchy_generator"},
                )

        logger.info(
            "Persisted hierarchy: %d jobs, %d edges, %d related for domain '%s'",
            len(result.jobs), len(result.edges), len(result.related_jobs),
            result.context.domain,
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
