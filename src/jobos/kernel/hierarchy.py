"""JobOS 4.0 — Job Hierarchy Model (The Job Triad).

Our IP-safe hierarchy structure based on JobOS 4.0's golden axiom:
    Entity HIRES Entity IN Context TO MINIMIZE Imperfection.

The Job Triad organizes jobs into 4 tiers based on the JTBD literature's
open taxonomy (functional, emotional, social, consumption chain) without
using trademarked terminology.

Tier Structure:
    T1  Strategic Jobs     — The overarching goals (WHY)
    T2  Core Functional    — Solution-agnostic outcomes (WHAT)
    T3  Execution Jobs     — Concrete actions and processes (HOW)
    T4  Micro-Jobs         — Smallest discrete, self-similar functional actions (EXECUTE)

Experience (FEEL) is Dimension A — an orthogonal dimension, not a tier.
See ``experience.py`` for Dimension A models.

Each tier connects via HIRES edges: a higher-tier job "hires" lower-tier
jobs to accomplish itself. This is the golden axiom applied recursively.

Key difference from JobOS 3.0's "Pyramid":
- Uses the unified Entity model (every job is an Entity node)
- HIRES edges instead of generic SUPPORTS/ENABLES
- LLM-generated instead of template-only
- Persisted to the main graph (not a separate subgraph)
- No trademarked terminology (no "Identity Jobs", no "Image Jobs")
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from jobos.kernel.entity import _uid

if TYPE_CHECKING:
    from jobos.kernel.generative_model import GenerativeModel


# ═══════════════════════════════════════════════════════════
#  Tier Definitions
# ═══════════════════════════════════════════════════════════

class JobTier(str, Enum):
    """The four tiers of the Job Triad hierarchy.

    Based on open JTBD terminology from Ulwick, Christensen, Moesta:
    - All four tiers are functional (solution-agnostic → concrete → micro)
    - Experience (FEEL) is Dimension A, orthogonal to the tier hierarchy
    - Strategic jobs sit above all as the macro-goal (Axiom 4: Singularity)
    """
    STRATEGIC = "T1_strategic"         # WHY — the overarching goal
    CORE_FUNCTIONAL = "T2_core"        # WHAT — solution-agnostic outcomes
    EXECUTION = "T3_execution"         # HOW — concrete processes and actions
    MICRO_JOB = "T4_micro"            # EXECUTE — smallest discrete functional actions


class ExecutionCategory(str, Enum):
    """Sub-categories for T3 Execution Jobs."""
    ACQUISITION = "acquisition"         # Get the capability/resource
    PREPARATION = "preparation"         # Set up for use
    OPERATION = "operation"             # Core usage/execution
    MONITORING = "monitoring"           # Track and control
    ADAPTATION = "adaptation"           # Adjust when context changes
    CONSUMPTION = "consumption"         # Consumption chain lifecycle steps


class MicroJobCategory(str, Enum):
    """Sub-categories for T4 Micro-Jobs."""
    SETUP = "setup"                     # Prepare inputs and environment
    ACT = "act"                         # Perform the atomic action
    VERIFY = "verify"                   # Check the outcome
    CLEANUP = "cleanup"                 # Release resources, hand off


# ─── T3 Execution: Standard 8-Step Sequence ──────────────
# A T3 Execution job may decompose into these canonical child nodes.
# Based on the universal consumption chain pattern (phase-independent).
# Maps to the GenerativeModel.execution_steps field.

T3_STANDARD_STEPS: list[str] = [
    "Define",       # Clarify scope and success criteria
    "Locate",       # Find or acquire necessary resources
    "Prepare",      # Set up environment, tools, inputs
    "Confirm",      # Validate readiness before acting
    "Execute",      # Perform the core action
    "Monitor",      # Track progress and detect deviations
    "Modify",       # Adjust mid-course based on feedback
    "Conclude",     # Wrap up, document, and hand off
]

# ─── Consumption Chain ────────────────────────────────────
# The canonical consumption lifecycle steps — a T3 sub-sequence
# that tracks the full journey from acquisition to end-of-life.
CONSUMPTION_CHAIN_STEPS: list[str] = [
    "Purchase",
    "Receive",
    "Set Up",
    "Learn",
    "Use",
    "Maintain",
    "Upgrade/Dispose",
]

# Neo4j relationship note: CHILD_OF is an alias direction for PART_OF.
# parent -[:HIRES]-> child  (golden axiom direction)
# child  -[:CHILD_OF]-> parent  (for upward traversal queries)
# Both are created when a child job is linked to a parent.
CHILD_OF_RELATIONSHIP = "CHILD_OF"


# ═══════════════════════════════════════════════════════════
#  Hierarchy Models
# ═══════════════════════════════════════════════════════════

class HierarchyJob(BaseModel):
    """A single job in the hierarchy.

    Each job becomes an Entity:Job node in Neo4j.
    The tier determines its level in the hierarchy.

    root_token: Set to 'ROOT' for T1 strategic jobs (Axiom 6 Singularity).
    scope_id:   Logical scope for root_token uniqueness.
    executor_type: Declared 'AI' or 'HUMAN' intent for this job.
    """
    id: str = Field(default_factory=_uid)
    tier: JobTier
    statement: str               # Must start with action verb (Axiom 5)
    category: str = ""           # Tier-specific sub-category
    rationale: str = ""          # Why this job exists in the hierarchy
    metrics_hint: list[str] = Field(default_factory=list)  # Suggested metrics
    root_token: Literal["ROOT"] | None = None
    scope_id: str = ""
    executor_type: Literal["AI", "HUMAN"] | None = None


class HierarchyEdge(BaseModel):
    """A HIRES relationship between two hierarchy jobs.

    Higher-tier jobs HIRE lower-tier jobs to accomplish themselves.
    This is the golden axiom applied to the hierarchy structure.
    """
    parent_id: str               # The hiring job (higher tier)
    child_id: str                # The hired job (lower tier)
    strength: float = 1.0        # How critical this relationship is


class HierarchyContext(BaseModel):
    """User input that seeds the hierarchy generation."""
    domain: str                  # e.g., "B2B SaaS", "retail operations"
    keywords: list[str] = Field(default_factory=list)  # Additional keywords
    actor: str = ""              # Who is the primary job executor
    goal: str = ""               # Optional overarching goal statement
    constraints: str = ""        # Any constraints or context


class HierarchyResult(BaseModel):
    """Complete generated Job Hierarchy (Job Triad)."""
    id: str = Field(default_factory=_uid)
    context: HierarchyContext
    jobs: list[HierarchyJob] = Field(default_factory=list)
    edges: list[HierarchyEdge] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    # GenerativeModel per job_id — populated by HierarchyService._build_hierarchy()
    generative_models: dict[str, Any] = Field(default_factory=dict)
    # Related jobs: cross-cutting T2-level jobs that support multiple core functional jobs
    related_jobs: list[HierarchyJob] = Field(default_factory=list)

    def jobs_at_tier(self, tier: JobTier) -> list[HierarchyJob]:
        return [j for j in self.jobs if j.tier == tier]

    def children_of(self, job_id: str) -> list[HierarchyJob]:
        child_ids = {e.child_id for e in self.edges if e.parent_id == job_id}
        return [j for j in self.jobs if j.id in child_ids]

    def to_tree_dict(self) -> dict[str, Any]:
        """Convert to a nested tree structure with dimension separation.

        Returns a dict with two keys:
          - functional_spine: nested T1→T2→T3→T4 tree (all four tiers are functional)
          - experience_dimension: populated from Dimension A :Experience nodes (if any)

        T4 Micro-Jobs are the smallest functional units, children of T3 via
        HIRES edges. Experience (FEEL) is an orthogonal dimension, not a tier.
        """
        # Build adjacency map — all four tiers are in the functional spine
        children_map: dict[str, list[str]] = {}
        for e in self.edges:
            children_map.setdefault(e.parent_id, []).append(e.child_id)

        # Functional spine roots: T1 jobs with no parent
        all_children = {cid for kids in children_map.values() for cid in kids}
        functional_roots = [
            j for j in self.jobs
            if j.tier == JobTier.STRATEGIC and j.id not in all_children
        ]

        job_map = {j.id: j for j in self.jobs}

        def build_node(job_id: str) -> dict:
            job = job_map.get(job_id)
            if not job:
                return {}
            node: dict[str, Any] = {
                "id": job.id,
                "tier": job.tier.value,
                "statement": job.statement,
                "category": job.category,
                "metrics_hint": job.metrics_hint,
                "executor_type": job.executor_type or "HUMAN",
            }
            kids = children_map.get(job_id, [])
            if kids:
                node["children"] = [build_node(cid) for cid in kids]
            return node

        # Experience dimension: placeholder for Dimension A nodes (populated externally)
        experience_nodes: list[dict[str, Any]] = []

        # Related jobs: cross-cutting T2-level jobs
        related_job_dicts = [
            {
                "id": rj.id,
                "tier": rj.tier.value,
                "statement": rj.statement,
                "category": rj.category,
                "metrics_hint": rj.metrics_hint,
                "executor_type": rj.executor_type or "HUMAN",
            }
            for rj in self.related_jobs
        ]

        return {
            "id": self.id,
            "domain": self.context.domain,
            "functional_spine": [build_node(r.id) for r in functional_roots],
            "experience_dimension": experience_nodes,
            "related_jobs": related_job_dicts,
        }
