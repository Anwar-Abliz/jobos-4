"""JobOS 4.0 — Generative Model Tier Mapping.

Each tier in the Job Triad hierarchy corresponds to a distinct "Generative Model"
in Active Inference terminology — the mental model the system uses to predict
and minimize Imperfection at that level of abstraction.

Tier → Generative Model field mapping:
    T1 Strategic   → prior_aspiration (the WHY, the overarching belief)
    T2 Core Functional → primary_goal (the WHAT, solution-agnostic outcome)
    T3 Execution   → execution_steps (the HOW, 8-step standard sequence)
    T4 Micro-Job   → primary_goal + micro_actions (the EXECUTE, smallest discrete actions)

Experience (FEEL) is Dimension A — an orthogonal dimension, not a tier.

Reference: Friston's Active Inference — Generative Models encode prior beliefs
about how observations (outcomes) are generated from hidden states (jobs).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from jobos.kernel.hierarchy import HierarchyJob, JobTier, T3_STANDARD_STEPS


# ─── Generative Model ────────────────────────────────────

@dataclass
class GenerativeModel:
    """The active inference generative model for a single Job tier.

    Each tier contributes a different level of temporal abstraction
    to the predictive hierarchy:

        T1 (Strategic):     Slow — months to years. prior_aspiration drives policy.
        T2 (Core Functional): Medium — weeks. primary_goal drives HIRES selection.
        T3 (Execution):     Fast — days. execution_steps drive micro-scheduling.
        T4 (Micro-Job):     Fastest — minutes. primary_goal + micro_actions drive task.
    """
    tier: int
    job_id: str = ""
    job_statement: str = ""
    prior_aspiration: str = ""           # T1: The WHY — encodes the goal prior belief
    primary_goal: str = ""               # T2: The WHAT — solution-agnostic outcome
    execution_steps: list[str] = field(default_factory=list)   # T3: 8-step standard
    micro_actions: list[str] = field(default_factory=list)     # T4: atomic actions


# ─── Tier → GenerativeModel Mapping ─────────────────────

def map_tier_to_generative_model(job: HierarchyJob) -> GenerativeModel:
    """Map a HierarchyJob to its GenerativeModel field based on tier.

    T1 Strategic:    Sets prior_aspiration from the job statement.
    T2 Core Functional: Sets primary_goal from the job statement.
    T3 Execution:    Sets execution_steps to T3_STANDARD_STEPS template.
                     The job statement is the "name" of the execution phase.
    T4 Micro-Job:    Sets primary_goal from the job statement (functional, not emotional).
                     micro_actions populated from decomposition.

    Args:
        job: A HierarchyJob with tier and statement set.

    Returns:
        GenerativeModel with the appropriate fields populated.
    """
    tier_int = _tier_to_int(job.tier)
    model = GenerativeModel(
        tier=tier_int,
        job_id=job.id,
        job_statement=job.statement,
    )

    if job.tier == JobTier.STRATEGIC:
        # T1: The why — this is the prior aspiration that all lower tiers serve
        model.prior_aspiration = job.statement

    elif job.tier == JobTier.CORE_FUNCTIONAL:
        # T2: The what — primary outcome goal, solution-agnostic
        model.primary_goal = job.statement

    elif job.tier == JobTier.EXECUTION:
        # T3: The how — inject standard 8-step execution sequence as child hints
        # Actual child nodes are separate HierarchyJob instances; these are the
        # canonical step labels that T3 execution jobs decompose into.
        model.primary_goal = job.statement
        model.execution_steps = list(T3_STANDARD_STEPS)

    elif job.tier == JobTier.MICRO_JOB:
        # T4: The execute — smallest discrete functional actions
        # These are regular functional jobs (action verbs, metrics), not emotional
        model.primary_goal = job.statement
        model.micro_actions = []  # Populated from decomposition

    return model


def _tier_to_int(tier: JobTier) -> int:
    """Convert JobTier enum to integer tier number."""
    mapping = {
        JobTier.STRATEGIC: 1,
        JobTier.CORE_FUNCTIONAL: 2,
        JobTier.EXECUTION: 3,
        JobTier.MICRO_JOB: 4,
    }
    return mapping[tier]


def generative_model_to_dict(model: GenerativeModel) -> dict[str, object]:
    """Serialise a GenerativeModel to a plain dict for API responses or logging."""
    return {
        "tier": model.tier,
        "job_id": model.job_id,
        "job_statement": model.job_statement,
        "prior_aspiration": model.prior_aspiration,
        "primary_goal": model.primary_goal,
        "execution_steps": model.execution_steps,
        "micro_actions": model.micro_actions,
    }
