"""Tests for the decision trace model."""
from __future__ import annotations

from jobos.kernel.decision_trace import DecisionTrace, chain_decision


class TestDecisionTrace:
    def test_creation(self):
        trace = DecisionTrace(
            actor="system",
            action="hire",
            target_entity_id="entity123",
            rationale="Lowest EFE",
        )
        assert trace.decision_id  # auto-generated
        assert trace.actor == "system"
        assert trace.action == "hire"
        assert trace.vfe_before is None
        assert trace.lineage == []

    def test_with_context(self):
        trace = DecisionTrace(
            actor="user1",
            action="switch",
            target_entity_id="e1",
            context_snapshot={"vfe": 0.5, "metric": "accuracy"},
            policies_evaluated=["policy1", "policy2"],
            alternatives=[{"id": "alt1", "efe": 0.3}],
            vfe_before=0.7,
            vfe_after=0.3,
        )
        assert trace.context_snapshot["vfe"] == 0.5
        assert len(trace.policies_evaluated) == 2
        assert len(trace.alternatives) == 1
        assert trace.vfe_before == 0.7


class TestChainDecision:
    def test_chain(self):
        parent = DecisionTrace(
            actor="system",
            action="hire",
            target_entity_id="e1",
        )
        child = DecisionTrace(
            actor="system",
            action="switch",
            target_entity_id="e2",
        )
        chained = chain_decision(parent, child)
        assert chained.lineage == [parent.decision_id]
        assert chained is child

    def test_deep_chain(self):
        d1 = DecisionTrace(actor="a", action="hire", target_entity_id="e1")
        d2 = DecisionTrace(actor="a", action="evaluate", target_entity_id="e1")
        d3 = DecisionTrace(actor="a", action="switch", target_entity_id="e1")

        chain_decision(d1, d2)
        chain_decision(d2, d3)

        assert d3.lineage == [d1.decision_id, d2.decision_id]
