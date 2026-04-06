"""NSAIG — Neuro-Symbolic Active Inference Graph (Blueprint 1).

The 'Belief & Strategy Engine' — answers 'WHY we hire'.

Components:
    BeliefEngine     — Symbolic axiom evaluation (LTN placeholder)
    PolicyOptimizer  — Active Inference policy selection (discrete POMDP)
    SwitchLogic      — VFE threshold monitoring → Fire decision
"""
from jobos.engines.nsaig.belief_engine import BeliefEngine, AxiomSatisfaction
from jobos.engines.nsaig.policy_optimizer import PolicyOptimizer, PolicyResult
from jobos.engines.nsaig.switch_logic import SwitchLogic, SwitchRecommendation

__all__ = [
    "BeliefEngine",
    "AxiomSatisfaction",
    "PolicyOptimizer",
    "PolicyResult",
    "SwitchLogic",
    "SwitchRecommendation",
]
