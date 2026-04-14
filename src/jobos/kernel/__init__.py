"""JobOS 4.0 Kernel — Pure domain logic, zero I/O.

The kernel contains the mathematical core of the JobOS ontology:
- Unified Entity model with ECS-style components
- The 6 non-negotiable axioms
- VFE scoring (variational free energy, replaces legacy IPS)
- Job statement linguistic validation
"""
from jobos.kernel.entity import (
    EntityType,
    EntityBase,
    JobProperties,
    ExecutorProperties,
    CapabilityProperties,
    ImperfectionProperties,
    AssumptionProperties,
    EvidenceProperties,
    ContextProperties,
    MetricProperties,
    HiresEdge,
    FiresEdge,
    MinimizesEdge,
    MetricReading,
    VFEReading,
    HiringEvent,
    validate_entity,
    ENTITY_PROPERTY_MODELS,
)
from jobos.kernel.axioms import JobOSAxioms
from jobos.kernel.imperfection import compute_vfe, compute_ips, compute_severity, rank_imperfections
from jobos.kernel.job_statement import parse_job_statement, validate_verb

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
    "validate_entity",
    "ENTITY_PROPERTY_MODELS",
    "JobOSAxioms",
    "compute_vfe",
    "compute_ips",
    "compute_severity",
    "rank_imperfections",
    "parse_job_statement",
    "validate_verb",
]
