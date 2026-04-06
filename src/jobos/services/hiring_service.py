"""JobOS 4.0 — Hiring Service (Core Axiom Orchestrator).

The core axiom: Entity HIRES Entity IN Context TO MINIMIZE Imperfection.

This service is where Blueprint 1 (NSAIG) and Blueprint 2 (CDEE) converge.
It mediates all interactions between the two engines:

1. NSAIG proposes → PolicyOptimizer selects candidate (minimizes EFE)
2. CDEE validates → CausalGuardian estimates ATE, Controller checks controllability
3. HiringService decides → combined assessment → propose / commit / evaluate / switch

Architectural Synthesis Reference:
    "Hiring is the act of selecting and delegating a Job to an Entity."
    "The 'Hire' is an 'Intervention' (do-operator) that breaks the
    existing causal structure and forces a variable to a new value."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from jobos.kernel.entity import (
    EntityBase,
    EntityType,
    HiresEdge,
    FiresEdge,
    HiringEvent,
    HiringEventType,
    VFEReading,
    _uid,
)
from jobos.engines.nsaig import PolicyOptimizer, PolicyResult, SwitchLogic, SwitchRecommendation
from jobos.engines.cdee import (
    CausalGuardian,
    ATEResult,
    DynamicController,
    ControlSignal,
    SwitchHub,
    StabilityResult,
)
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


# ─── Result Types ────────────────────────────────────────

@dataclass
class HireProposal:
    """Combined assessment from both engines for a hiring decision."""
    hire_id: str = ""
    job_id: str = ""
    hiree_id: str = ""
    context_id: str | None = None
    status: str = "proposed"  # "proposed" | "active" | "rejected" | "needs_review"

    # Blueprint 1 assessment
    nsaig_assessment: dict[str, Any] = field(default_factory=dict)

    # Blueprint 2 assessment
    cdee_assessment: dict[str, Any] = field(default_factory=dict)

    # Combined
    combined_recommendation: str = ""  # "hire" | "caution" | "reject"
    expected_imperfection_reduction: float = 0.0
    reasoning: str = ""


@dataclass
class HireEvaluation:
    """Periodic evaluation of an active Hire."""
    hire_id: str = ""
    status: str = "active"
    elapsed_days: int = 0

    # Blueprint 1 evaluation
    nsaig_evaluation: dict[str, Any] = field(default_factory=dict)

    # Blueprint 2 evaluation
    cdee_evaluation: dict[str, Any] = field(default_factory=dict)

    # Combined verdict
    combined_verdict: str = ""  # "keep" | "warn" | "switch"
    reasoning: str = ""


class HiringService:
    """The core axiom orchestrator.

    Coordinates NSAIG (why to hire) and CDEE (how effective is the hire)
    to execute the full Hire → Monitor → Evaluate → Switch lifecycle.
    """

    def __init__(
        self,
        graph: GraphPort,
        db: RelationalPort,
        policy_optimizer: PolicyOptimizer | None = None,
        switch_logic: SwitchLogic | None = None,
        causal_guardian: CausalGuardian | None = None,
        controller: DynamicController | None = None,
        switch_hub: SwitchHub | None = None,
    ) -> None:
        self._graph = graph
        self._db = db
        self._policy = policy_optimizer or PolicyOptimizer()
        self._switch_logic = switch_logic or SwitchLogic()
        self._causal = causal_guardian or CausalGuardian()
        self._controller = controller or DynamicController()
        self._switch_hub = switch_hub or SwitchHub()

    async def propose_hire(
        self,
        job_id: str,
        candidates: list[dict] | None = None,
        context_id: str | None = None,
    ) -> HireProposal:
        """Propose a Hire — NSAIG proposes, CDEE validates.

        Flow:
        1. Gather current metrics for the Job
        2. NSAIG PolicyOptimizer selects best candidate (minimizes EFE)
        3. CDEE CausalGuardian estimates expected ATE
        4. CDEE Controller checks controllability
        5. Return combined proposal with both engines' assessments

        If no candidates provided, returns a proposal requesting candidates.
        """
        proposal = HireProposal(
            hire_id=_uid(),
            job_id=job_id,
            context_id=context_id,
        )

        if not candidates:
            proposal.status = "needs_review"
            proposal.reasoning = "No candidates provided. Create Capability entities first."
            return proposal

        # Gather current metrics for the Job from Neo4j
        metrics = await self._gather_job_metrics(job_id)

        # ── Blueprint 1: NSAIG proposes ─────────────────
        policy_result: PolicyResult = self._policy.select_policy(
            current_metrics=metrics,
            candidates=candidates,
        )

        proposal.nsaig_assessment = {
            "efe_score": policy_result.efe_score,
            "vfe_current": policy_result.vfe_current,
            "policy_confidence": policy_result.policy_confidence,
            "reasoning": policy_result.reasoning,
            "alternatives": policy_result.alternatives,
        }

        if policy_result.recommended_hiree_id:
            proposal.hiree_id = policy_result.recommended_hiree_id

        # ── Blueprint 2: CDEE validates ─────────────────
        # Phase 1: simplified — use estimated_impact from candidate
        candidate = next(
            (c for c in candidates if c["id"] == proposal.hiree_id), None
        )
        estimated_impact = candidate.get("estimated_impact", 0.0) if candidate else 0.0

        proposal.cdee_assessment = {
            "estimated_impact": estimated_impact,
            "controllability": True,  # Phase 1: assume controllable
            "stability_forecast": "unknown",  # No history yet
            "reasoning": (
                f"Estimated impact: {estimated_impact:.0%} imperfection reduction. "
                f"Controllability check deferred until metric data available."
            ),
        }

        # ── Combined recommendation ─────────────────────
        if policy_result.policy_confidence >= 0.5 and estimated_impact > 0.1:
            proposal.status = "proposed"
            proposal.combined_recommendation = "hire"
            proposal.expected_imperfection_reduction = estimated_impact
            proposal.reasoning = (
                f"Both engines agree. EFE={policy_result.efe_score:.3f}, "
                f"estimated impact={estimated_impact:.0%}."
            )
        elif policy_result.policy_confidence < 0.3:
            proposal.status = "needs_review"
            proposal.combined_recommendation = "caution"
            proposal.reasoning = (
                f"Low policy confidence ({policy_result.policy_confidence:.2f}). "
                f"Consider more candidates or clarifying the imperfection."
            )
        else:
            proposal.status = "proposed"
            proposal.combined_recommendation = "hire"
            proposal.expected_imperfection_reduction = estimated_impact
            proposal.reasoning = "Hire recommended with moderate confidence."

        return proposal

    async def execute_hire(
        self,
        hirer_id: str,
        hiree_id: str,
        job_id: str,
        context_id: str | None = None,
        imperfection_id: str | None = None,
    ) -> HiringEvent:
        """Commit a Hire to the graph and audit log.

        Flow:
        1. Create HIRES edge in Neo4j (hirer → hiree)
        2. If imperfection provided, create MINIMIZES edge (hiree → imperfection)
        3. Write HiringEvent to PostgreSQL audit log
        4. Record VFE reading for the job (pre-hire baseline)
        """
        now = datetime.now(timezone.utc)

        # Create HIRES edge in Neo4j
        await self._graph.create_edge(
            source_id=hirer_id,
            target_id=hiree_id,
            edge_type="HIRES",
            properties={
                "context_id": context_id or "",
                "hired_at": now.isoformat(),
                "status": "active",
                "strength": 1.0,
            },
        )

        # Create MINIMIZES edge if imperfection specified
        if imperfection_id:
            await self._graph.create_edge(
                source_id=hiree_id,
                target_id=imperfection_id,
                edge_type="MINIMIZES",
                properties={
                    "expected_delta": 0.0,
                    "causal_confidence": 0.5,
                },
            )

        # Write audit log to PostgreSQL
        event = HiringEvent(
            hirer_id=hirer_id,
            hiree_id=hiree_id,
            context_id=context_id,
            event_type=HiringEventType.HIRE,
            reason=f"Hired for job {job_id}",
            occurred_at=now,
        )
        await self._db.save_hiring_event(event)

        logger.info("Executed HIRE: %s → %s for job %s", hirer_id, hiree_id, job_id)
        return event

    async def evaluate_hire(
        self,
        hirer_id: str,
        hiree_id: str,
        job_id: str,
    ) -> HireEvaluation:
        """Periodic evaluation of an active Hire.

        Flow:
        1. CDEE Controller computes current error signal and trend
        2. CDEE SwitchHub checks Lyapunov stability
        3. NSAIG SwitchLogic checks VFE threshold
        4. Return combined assessment

        This is where 'Should we keep or switch?' is answered.
        """
        evaluation = HireEvaluation(
            hire_id=f"{hirer_id}->{hiree_id}",
        )

        # Gather metric and VFE history
        metrics = await self._gather_job_metrics(job_id)
        vfe_history = await self._gather_vfe_history(job_id)

        # ── Blueprint 2: CDEE evaluates ─────────────────
        error_history = self._compute_error_history(metrics)
        control_signal: ControlSignal = self._controller.analyze(error_history)
        stability: StabilityResult = self._switch_hub.check_stability(error_history)

        evaluation.cdee_evaluation = {
            "error_signal": control_signal.error_current,
            "error_trend": control_signal.error_trend,
            "stability": stability.status,
            "should_switch": stability.should_switch,
            "reasoning": control_signal.reasoning,
        }

        # ── Blueprint 1: NSAIG evaluates ────────────────
        switch_rec: SwitchRecommendation = self._switch_logic.analyze(vfe_history)

        evaluation.nsaig_evaluation = {
            "vfe_current": switch_rec.vfe_current,
            "vfe_trend": switch_rec.vfe_trend,
            "should_switch": switch_rec.should_switch,
            "urgency": switch_rec.urgency,
            "reasoning": switch_rec.reasoning,
        }

        # ── Combined verdict ────────────────────────────
        if stability.should_switch or switch_rec.should_switch:
            evaluation.combined_verdict = "switch"
            evaluation.reasoning = "At least one engine recommends switching."
        elif stability.status == "oscillating" or switch_rec.urgency == "warning":
            evaluation.combined_verdict = "warn"
            evaluation.reasoning = "System not converging cleanly. Monitor closely."
        else:
            evaluation.combined_verdict = "keep"
            evaluation.reasoning = "Both engines indicate the hire is effective."

        return evaluation

    async def execute_switch(
        self,
        hirer_id: str,
        current_hiree_id: str,
        new_hiree_id: str,
        job_id: str,
        reason: str = "",
        context_id: str | None = None,
    ) -> HiringEvent:
        """Execute a Switch: Fire current, Hire replacement.

        Flow:
        1. Terminate current HIRES edge
        2. Create FIRES edge
        3. Create new HIRES edge
        4. Write HiringEvent (type=switch) to audit log
        """
        now = datetime.now(timezone.utc)

        # Terminate current hire
        await self._graph.delete_edge(hirer_id, current_hiree_id, "HIRES")

        # Create FIRES edge (for audit trail in graph)
        await self._graph.create_edge(
            source_id=hirer_id,
            target_id=current_hiree_id,
            edge_type="FIRES",
            properties={
                "fired_at": now.isoformat(),
                "reason": reason,
            },
        )

        # Create new HIRES edge
        await self._graph.create_edge(
            source_id=hirer_id,
            target_id=new_hiree_id,
            edge_type="HIRES",
            properties={
                "context_id": context_id or "",
                "hired_at": now.isoformat(),
                "status": "active",
                "strength": 1.0,
            },
        )

        # Audit log
        event = HiringEvent(
            hirer_id=hirer_id,
            hiree_id=new_hiree_id,
            context_id=context_id,
            event_type=HiringEventType.SWITCH,
            reason=f"Switched from {current_hiree_id}: {reason}",
            occurred_at=now,
        )
        await self._db.save_hiring_event(event)

        logger.info(
            "Executed SWITCH: %s fired %s, hired %s for job %s",
            hirer_id, current_hiree_id, new_hiree_id, job_id,
        )
        return event

    # ─── Private Helpers ─────────────────────────────────

    async def _gather_job_metrics(self, job_id: str) -> dict[str, dict]:
        """Collect current metric state for a Job from Neo4j."""
        metric_entities = await self._graph.get_neighbors(
            job_id, edge_type="MEASURED_BY", direction="outgoing"
        )
        metrics = {}
        for m in metric_entities:
            props = m.properties
            metrics[m.id] = {
                "observed": props.get("current_value"),
                "target": props.get("target_value"),
                "op": "<=",  # default; could be derived from direction
            }
        return metrics

    async def _gather_vfe_history(self, job_id: str) -> list[float]:
        """Get VFE time-series from PostgreSQL."""
        readings = await self._db.get_vfe_history(job_id, limit=20)
        return [r.vfe_value for r in readings]

    def _compute_error_history(self, metrics: dict[str, dict]) -> list[float]:
        """Compute error signals from current metrics.

        Phase 1: single aggregated error = mean of |target - observed|/|target|.
        """
        errors = []
        for m_id, m in metrics.items():
            target = m.get("target")
            observed = m.get("observed")
            if target is not None and observed is not None and abs(target) > 1e-9:
                errors.append(abs(target - observed) / abs(target))
            elif observed is None:
                errors.append(1.0)

        if not errors:
            return [0.0]
        return [sum(errors) / len(errors)]
