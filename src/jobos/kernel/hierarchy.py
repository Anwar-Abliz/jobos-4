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
    T4  Experience Jobs    — Emotional + social desired states (FEEL)

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
from typing import Any

from pydantic import BaseModel, Field

from jobos.kernel.entity import _uid


# ═══════════════════════════════════════════════════════════
#  Tier Definitions
# ═══════════════════════════════════════════════════════════

class JobTier(str, Enum):
    """The four tiers of the Job Triad hierarchy.

    Based on open JTBD terminology from Ulwick, Christensen, Moesta:
    - Functional jobs (core + execution) are solution-agnostic
    - Emotional/social jobs capture the human experience
    - Strategic jobs sit above all as the macro-goal (Axiom 4: Singularity)
    """
    STRATEGIC = "T1_strategic"         # WHY — the overarching goal
    CORE_FUNCTIONAL = "T2_core"        # WHAT — solution-agnostic outcomes
    EXECUTION = "T3_execution"         # HOW — concrete processes and actions
    EXPERIENCE = "T4_experience"       # FEEL — emotional + social desired states


class ExecutionCategory(str, Enum):
    """Sub-categories for T3 Execution Jobs."""
    ACQUISITION = "acquisition"         # Get the capability/resource
    PREPARATION = "preparation"         # Set up for use
    OPERATION = "operation"             # Core usage/execution
    MONITORING = "monitoring"           # Track and control
    ADAPTATION = "adaptation"           # Adjust when context changes


class ExperienceCategory(str, Enum):
    """Sub-categories for T4 Experience Jobs."""
    CONFIDENCE = "confidence"           # Feel confident, in control
    RECOGNITION = "recognition"         # Be seen as competent/valuable
    GROWTH = "growth"                   # Feel like I'm developing
    CONNECTION = "connection"           # Feel connected to team/purpose
    RELIEF = "relief"                   # Avoid anxiety, embarrassment, overload


# ═══════════════════════════════════════════════════════════
#  Hierarchy Models
# ═══════════════════════════════════════════════════════════

class HierarchyJob(BaseModel):
    """A single job in the hierarchy.

    Each job becomes an Entity:Job node in Neo4j.
    The tier determines its level in the hierarchy.
    """
    id: str = Field(default_factory=_uid)
    tier: JobTier
    statement: str               # Must start with action verb (Axiom 5)
    category: str = ""           # Tier-specific sub-category
    rationale: str = ""          # Why this job exists in the hierarchy
    metrics_hint: list[str] = Field(default_factory=list)  # Suggested metrics


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

    def jobs_at_tier(self, tier: JobTier) -> list[HierarchyJob]:
        return [j for j in self.jobs if j.tier == tier]

    def children_of(self, job_id: str) -> list[HierarchyJob]:
        child_ids = {e.child_id for e in self.edges if e.parent_id == job_id}
        return [j for j in self.jobs if j.id in child_ids]

    def to_tree_dict(self) -> dict[str, Any]:
        """Convert to a nested tree structure for visualization."""
        # Build adjacency map
        children_map: dict[str, list[str]] = {}
        for e in self.edges:
            children_map.setdefault(e.parent_id, []).append(e.child_id)

        # Find roots (T1 jobs with no parent)
        all_children = {e.child_id for e in self.edges}
        roots = [j for j in self.jobs if j.id not in all_children]

        job_map = {j.id: j for j in self.jobs}

        def build_node(job_id: str) -> dict:
            job = job_map.get(job_id)
            if not job:
                return {}
            node = {
                "id": job.id,
                "tier": job.tier.value,
                "statement": job.statement,
                "category": job.category,
                "metrics_hint": job.metrics_hint,
            }
            kids = children_map.get(job_id, [])
            if kids:
                node["children"] = [build_node(cid) for cid in kids]
            return node

        return {
            "id": self.id,
            "domain": self.context.domain,
            "tree": [build_node(r.id) for r in roots],
        }
