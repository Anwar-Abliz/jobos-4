"""CDEE — Causal-Dynamic Execution Engine (Blueprint 2).

The 'Execution & Control Engine' — answers 'HOW effective is our hire'.

Components:
    CausalGuardian    — SCM construction + ATE estimation (dowhy placeholder)
    DynamicController — State-space feedback (PID-inspired)
    SwitchHub         — Lyapunov stability check → Fire decision
"""
from jobos.engines.cdee.causal_guardian import CausalGuardian, ATEResult, CounterfactualResult
from jobos.engines.cdee.controller import DynamicController, ControlSignal, ControllabilityResult
from jobos.engines.cdee.switch_hub import SwitchHub, StabilityResult

__all__ = [
    "CausalGuardian",
    "ATEResult",
    "CounterfactualResult",
    "DynamicController",
    "ControlSignal",
    "ControllabilityResult",
    "SwitchHub",
    "StabilityResult",
]
