"""JobOS 4.0 Kernel — Pure domain logic, zero I/O.

The kernel contains the mathematical core of the JobOS ontology:
- Unified Entity model with ECS-style components
- The 8 operational axioms (axioms.py)
- The 3 foundational axioms meta-layer (foundational_axioms.py)
- VFE scoring (variational free energy, replaces legacy IPS)
- Job statement linguistic validation
- SAP Context Graph entity types and property models
- Governance model and decision tracing
- ODI (Outcome-Driven Innovation) scoring
"""
# SAP Context Graph extensions — auto-registers property models on import
import jobos.kernel.sap_entities  # noqa: F401
from jobos.kernel.axioms import JobOSAxioms
from jobos.kernel.decision_trace import DecisionTrace, chain_decision
from jobos.kernel.entity import (
    ENTITY_PROPERTY_MODELS,
    AssumptionProperties,
    CapabilityProperties,
    ChoiceSet,
    ContextProperties,
    EntityBase,
    EntityType,
    EvidenceProperties,
    ExecutorProperties,
    FiresEdge,
    HiresEdge,
    HiringEvent,
    ImperfectionProperties,
    JobProperties,
    MetricProperties,
    MetricReading,
    MinimizesEdge,
    VFEReading,
    register_property_model,
    validate_entity,
)
from jobos.kernel.foundational_axioms import (
    OPERATIONAL_TO_FOUNDATIONAL,
    FoundationalAxiom,
    FoundationalSatisfaction,
    compute_foundational_satisfaction,
)
from jobos.kernel.governance import (
    AccessLevel,
    GovernanceRule,
    GovernanceScope,
    evaluate_governance,
)
from jobos.kernel.imperfection import compute_ips, compute_severity, compute_vfe, rank_imperfections
from jobos.kernel.job_statement import parse_job_statement, validate_verb
from jobos.kernel.odi import (
    compute_opportunity_score,
    map_opportunity_to_vfe,
    validate_outcome_statement,
)
from jobos.kernel.sap_entities import (
    DataSourceProperties,
    DecisionProperties,
    OutcomeProperties,
    PolicyProperties,
    SAPObjectProperties,
    SAPOrgUnitProperties,
    SAPProcessProperties,
    SAPTransactionProperties,
    SurveyProperties,
)

__all__ = [
    "EntityType",
    "EntityBase",
    "JobProperties",
    "ExecutorProperties",
    "CapabilityProperties",
    "ImperfectionProperties",
    "AssumptionProperties",
    "EvidenceProperties",
    "ContextProperties",
    "MetricProperties",
    "HiresEdge",
    "FiresEdge",
    "MinimizesEdge",
    "MetricReading",
    "VFEReading",
    "HiringEvent",
    "ChoiceSet",
    "validate_entity",
    "ENTITY_PROPERTY_MODELS",
    "register_property_model",
    "JobOSAxioms",
    "FoundationalAxiom",
    "FoundationalSatisfaction",
    "OPERATIONAL_TO_FOUNDATIONAL",
    "compute_foundational_satisfaction",
    "compute_vfe",
    "compute_ips",
    "compute_severity",
    "rank_imperfections",
    "parse_job_statement",
    "validate_verb",
    # SAP Context Graph
    "SAPProcessProperties",
    "SAPObjectProperties",
    "SAPTransactionProperties",
    "SAPOrgUnitProperties",
    "DecisionProperties",
    "PolicyProperties",
    "DataSourceProperties",
    "SurveyProperties",
    "OutcomeProperties",
    # Governance
    "AccessLevel",
    "GovernanceScope",
    "GovernanceRule",
    "evaluate_governance",
    # Decision Tracing
    "DecisionTrace",
    "chain_decision",
    # ODI
    "compute_opportunity_score",
    "map_opportunity_to_vfe",
    "validate_outcome_statement",
]
