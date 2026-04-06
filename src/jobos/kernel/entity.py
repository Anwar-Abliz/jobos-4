"""JobOS 4.0 — Unified Entity Model with ECS-style Components.

Grounding Document Reference:
    "Entity: Any discrete agent, executor, or capability (human, AI, or
    software) capable of performing work." — Architectural Synthesis §1

CTO Decision 2: Unified Entity with dynamic labels.
    A single Entity node type in Neo4j, enriched with dynamic labels to
    define its current state (:Job, :Executor, :Context, etc.).

CTO Decision 3: Dual-database.
    Graph topology (Entities + edges) in Neo4j.
    Time-series metrics and audit logs in PostgreSQL.
    MetricReading, VFEReading, HiringEvent models are PostgreSQL DTOs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════

class EntityType(str, Enum):
    """Primary semantic type of an Entity.

    Maps to Neo4j dynamic labels: (:Entity:Job), (:Entity:Executor), etc.
    An Entity may hold multiple labels simultaneously (ontological superposition).
    """
    JOB = "job"
    EXECUTOR = "executor"
    CAPABILITY = "capability"
    IMPERFECTION = "imperfection"
    ASSUMPTION = "assumption"
    EVIDENCE = "evidence"
    CONTEXT = "context"
    METRIC = "metric"


class JobType(str, Enum):
    """Job classification from the ontology design document."""
    CORE_FUNCTIONAL = "core_functional"
    EMOTIONAL = "emotional"
    SOCIAL = "social"
    MANAGERIAL = "managerial"
    CONSUMPTION_CHAIN = "consumption_chain"
    RELATED = "related"


class JobNature(str, Enum):
    PROJECT = "project"
    MAINTENANCE = "maintenance"


class ExecutorKind(str, Enum):
    PERSON = "person"
    TEAM = "team"
    ORGANIZATION = "organization"
    SYSTEM = "system"
    AI_AGENT = "ai_agent"


class CapabilityKind(str, Enum):
    """Solution types from the ontology design document §E."""
    PRODUCT = "product"
    SERVICE = "service"
    PROCESS = "process"
    POLICY = "policy"
    WORKAROUND = "workaround"
    AUTOMATION = "automation"


class MetricDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class MetricType(str, Enum):
    """ODI-style metric types from the ontology design document §A."""
    TIME = "time"
    LIKELIHOOD = "likelihood"
    COST = "cost"
    EFFORT = "effort"
    VARIABILITY = "variability"
    ACCURACY = "accuracy"
    THROUGHPUT = "throughput"
    SATISFACTION = "satisfaction"
    COMPLIANCE_RISK = "compliance_risk"


class ImperfectionStatus(str, Enum):
    HYPOTHESIZED = "hypothesized"
    OBSERVED = "observed"
    MEASURED = "measured"
    RESOLVED = "resolved"


class AssumptionStatus(str, Enum):
    """From the ontology design document §F."""
    UNTESTED = "untested"
    TESTING = "testing"
    SUPPORTED = "supported"
    FALSIFIED = "falsified"
    REVISED = "revised"


class EvidenceKind(str, Enum):
    INTERVIEW = "interview"
    SURVEY = "survey"
    ANALYTICS = "analytics"
    EXPERIMENT = "experiment"
    DOC = "doc"
    EXPERT_REVIEW = "expert_review"


class HiringEventType(str, Enum):
    HIRE = "hire"
    FIRE = "fire"
    SWITCH = "switch"


class ExperimentDecision(str, Enum):
    PROCEED = "proceed"
    PIVOT = "pivot"
    STOP = "stop"


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def _uid() -> str:
    """Generate a 12-char hex UUID for entity IDs."""
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════
#  The Unified Entity Model
# ═══════════════════════════════════════════════════════════

class EntityBase(BaseModel):
    """Base model for all entities in the JobOS ontology.

    This is the single node type stored in Neo4j. The `entity_type`
    field determines which dynamic labels are applied and which
    property schema is enforced.

    Architectural Synthesis mapping:
        Entity  → Input (X) or Processing Node in the JobOS Perceptron
        Job     → Trigger / Signal (the Generative Model)
        Context → Weights / Parameters (the Markov Blanket)
        Metric  → Activation / Loss Function
    """
    id: str = Field(default_factory=_uid)
    name: str = ""
    statement: str = ""
    entity_type: EntityType
    status: str = "active"
    properties: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(
        default_factory=list,
        description="Additional Neo4j labels beyond :Entity (max 4 extra per CTO memo)"
    )
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════
#  Type-Specific Component Models (ECS pattern)
# ═══════════════════════════════════════════════════════════

class JobProperties(BaseModel):
    """Properties for entity_type='job'.

    The Job is the 'Generative Model' in Active Inference — it encodes
    the preferred states (success metrics) that the system works to maintain.
    vfe_current is the current Variational Free Energy (Imperfection as Surprise).
    """
    job_type: JobType = JobType.CORE_FUNCTIONAL
    job_nature: JobNature = JobNature.PROJECT
    level: int = 0
    parent_id: str | None = None
    preferred_states: list[str] = Field(default_factory=list)
    vfe_current: float = 0.0

    @field_validator("level")
    @classmethod
    def level_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Job level must be >= 0")
        return v


class ExecutorProperties(BaseModel):
    """Properties for entity_type='executor'."""
    executor_kind: ExecutorKind = ExecutorKind.PERSON
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    capacity: float = Field(default=1.0, ge=0.0, le=1.0)


class CapabilityProperties(BaseModel):
    """Properties for entity_type='capability'.

    dual_job_id: Ontological superposition — a completed Job that
    becomes a hireable Capability at a higher level.
    """
    capability_kind: CapabilityKind = CapabilityKind.PRODUCT
    version: str = "1.0"
    dual_job_id: str | None = None
    estimated_impact: float = Field(default=0.0, ge=0.0, le=1.0)


class ImperfectionProperties(BaseModel):
    """Properties for entity_type='imperfection'.

    Maps to the Architectural Synthesis's 'Prediction Error / Surprise'.
    The IPS score ranks imperfections by urgency for the Scheduler.

    IPS = 3*Blocker + 2*Severity + Frequency + EntropyRisk + (1 - Fixability)
    """
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    frequency: float = Field(default=0.5, ge=0.0, le=1.0)
    entropy_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    fixability: float = Field(default=0.5, ge=0.0, le=1.0)
    is_blocker: bool = False
    mode: Literal["perceived", "objective", "hybrid"] = "hybrid"
    evidence_level: Literal[
        "anecdotal", "qualitative", "quantitative", "experimental"
    ] = "anecdotal"


class AssumptionProperties(BaseModel):
    """Properties for entity_type='assumption'.

    Part of the NSAIG Belief Engine. Confidence updates follow
    Bayesian rules; risk_score and value_of_information drive
    the testing priority.
    """
    assumption_type: Literal[
        "market", "customer", "job", "solution", "channel",
        "pricing", "capability", "feasibility", "viability", "desirability"
    ] = "job"
    polarity: Literal["enabling", "limiting"] = "enabling"
    confidence_prior: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_current: float = Field(default=0.5, ge=0.0, le=1.0)
    impact_if_false: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_delta: float = 0.0


class EvidenceProperties(BaseModel):
    """Properties for entity_type='evidence'."""
    evidence_kind: EvidenceKind = EvidenceKind.ANALYTICS
    source: str = "user"
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    measured_delta: float = 0.0
    supports: bool | None = None


class ContextProperties(BaseModel):
    """Properties for entity_type='context'.

    The 5W2H structure. Maps to the Architectural Synthesis's
    'Markov Blanket' (separating internal from external states)
    and 'Weights/Parameters' in the Perceptron analogy.
    """
    who: str = ""
    why: str = ""
    what: str = ""
    where: str = ""
    when: str = ""
    how: str = ""
    constraints: str = ""
    scope: Literal["broad", "narrow"] = "broad"
    stability: Literal["stable", "volatile"] = "stable"


class MetricProperties(BaseModel):
    """Properties for entity_type='metric'.

    Maps to 'Activation / Loss Function' in the Perceptron.
    target_value is the set-point; current_value is the process variable.
    The delta (target - current) IS the Imperfection.
    """
    direction: MetricDirection = MetricDirection.MINIMIZE
    metric_type: MetricType = MetricType.SATISFACTION
    unit: str = ""
    target_value: float | None = None
    current_value: float | None = None
    measurement_method: str = ""


# ═══════════════════════════════════════════════════════════
#  Entity Property Validation (ECS System)
# ═══════════════════════════════════════════════════════════

ENTITY_PROPERTY_MODELS: dict[EntityType, type[BaseModel]] = {
    EntityType.JOB: JobProperties,
    EntityType.EXECUTOR: ExecutorProperties,
    EntityType.CAPABILITY: CapabilityProperties,
    EntityType.IMPERFECTION: ImperfectionProperties,
    EntityType.ASSUMPTION: AssumptionProperties,
    EntityType.EVIDENCE: EvidenceProperties,
    EntityType.CONTEXT: ContextProperties,
    EntityType.METRIC: MetricProperties,
}


def validate_entity(entity: EntityBase) -> EntityBase:
    """Validate that an entity's properties bag matches its type schema.

    This is the ECS 'system' that enforces component correctness.
    Raises pydantic.ValidationError if properties don't match.
    """
    model_cls = ENTITY_PROPERTY_MODELS.get(entity.entity_type)
    if model_cls:
        model_cls.model_validate(entity.properties)
    return entity


def get_typed_properties(entity: EntityBase) -> BaseModel | None:
    """Parse an entity's properties dict into the typed Pydantic model."""
    model_cls = ENTITY_PROPERTY_MODELS.get(entity.entity_type)
    if model_cls:
        return model_cls.model_validate(entity.properties)
    return None


# ═══════════════════════════════════════════════════════════
#  Edge / Relationship Models (Neo4j edges)
# ═══════════════════════════════════════════════════════════

class HiresEdge(BaseModel):
    """The core axiom edge: Entity HIRES Entity.

    'Signal Propagation' in the JobOS Perceptron.
    strength maps to the LTN fuzzy predicate truth value Hires(E1, E2) ∈ [0,1].
    """
    hirer_id: str
    hiree_id: str
    context_id: str | None = None
    hired_at: datetime = Field(default_factory=_now)
    status: Literal["active", "completed", "terminated"] = "active"
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    policy_id: str | None = None


class FiresEdge(BaseModel):
    """The Switch: Entity terminates a Hiring relationship.

    counterfactual_delta: CDEE's causal estimate of what would
    happen if this entity were replaced (from CausalGuardian).
    """
    firer_id: str
    firee_id: str
    context_id: str | None = None
    fired_at: datetime = Field(default_factory=_now)
    reason: str = ""
    counterfactual_delta: float = 0.0


class MinimizesEdge(BaseModel):
    """Capability MINIMIZES Imperfection — the causal claim.

    This is the CDEE's core edge. causal_confidence is the
    Average Treatment Effect estimate from the Causal Guardian.
    """
    capability_id: str
    imperfection_id: str
    expected_delta: float = 0.0
    observed_delta: float | None = None
    causal_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PartOfEdge(BaseModel):
    """Job hierarchy: child PART_OF parent."""
    child_id: str
    parent_id: str


class QualifiesEdge(BaseModel):
    """Context QUALIFIES Job or Imperfection."""
    context_id: str
    target_id: str


class MeasuredByEdge(BaseModel):
    """Job MEASURED_BY Metric."""
    job_id: str
    metric_id: str


class OccursInEdge(BaseModel):
    """Imperfection OCCURS_IN Job."""
    imperfection_id: str
    job_id: str


class ImpactsEdge(BaseModel):
    """Imperfection IMPACTS Metric."""
    imperfection_id: str
    metric_id: str


class AboutEdge(BaseModel):
    """Assumption ABOUT any Entity (polymorphic target)."""
    assumption_id: str
    target_id: str


class SupportsEdge(BaseModel):
    """Evidence SUPPORTS Assumption."""
    evidence_id: str
    assumption_id: str


class RefutesEdge(BaseModel):
    """Evidence REFUTES Assumption."""
    evidence_id: str
    assumption_id: str


class DualAsEdge(BaseModel):
    """Ontological superposition: completed Job DUAL_AS Capability."""
    job_id: str
    capability_id: str


# ═══════════════════════════════════════════════════════════
#  PostgreSQL DTO Models
# ═══════════════════════════════════════════════════════════

class MetricReading(BaseModel):
    """A single metric observation — stored in PostgreSQL.

    This is the 'sensory data' that feeds both the NSAIG Sensory Graph
    and the CDEE Dynamic Controller.
    """
    id: str = Field(default_factory=_uid)
    entity_id: str
    metric_id: str
    value: float
    unit: str = ""
    source: str = "user"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=_now)


class VFEReading(BaseModel):
    """Variational Free Energy snapshot — stored in PostgreSQL.

    The NSAIG's core signal: how 'surprised' is the system by
    the current state of a Job? Rising VFE → hire is failing.
    """
    id: str = Field(default_factory=_uid)
    job_id: str
    vfe_value: float
    efe_value: float | None = None
    policy_id: str | None = None
    measured_at: datetime = Field(default_factory=_now)


class HiringEvent(BaseModel):
    """Immutable audit record of a Hire/Fire/Switch — stored in PostgreSQL.

    policy_snapshot: NSAIG policy state at decision time.
    causal_estimate: CDEE causal analysis snapshot.
    Together these provide full explainability for every hiring decision.
    """
    id: str = Field(default_factory=_uid)
    hirer_id: str
    hiree_id: str
    context_id: str | None = None
    event_type: HiringEventType
    reason: str = ""
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    causal_estimate: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=_now)


class ExperimentRecord(BaseModel):
    """Experiment result — stored in PostgreSQL."""
    id: str = Field(default_factory=_uid)
    assumption_id: str
    method: str
    hypothesis: str
    success_criteria: dict[str, Any] = Field(default_factory=dict)
    failure_criteria: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    decision: ExperimentDecision | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
