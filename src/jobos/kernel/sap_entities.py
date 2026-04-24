"""JobOS 4.0 — SAP Context Graph Property Models.

Pydantic property models for SAP-shaped entity types added to the
Context Graph platform: processes, objects, transactions, org units,
decisions, policies, data sources, surveys, and ODI outcomes.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════

class SAPModule(str, Enum):
    SD = "SD"
    MM = "MM"
    FI = "FI"
    CO = "CO"
    PP = "PP"
    PM = "PM"
    QM = "QM"
    WM = "WM"
    HR = "HR"
    PS = "PS"


class ProcessType(str, Enum):
    E2E = "e2e"
    SUB = "sub"
    VARIANT = "variant"


class ContextFreshness(str, Enum):
    LIVE = "live"
    SNAPSHOT = "snapshot"
    STALE = "stale"


class OrgUnitType(str, Enum):
    COMPANY_CODE = "company_code"
    PLANT = "plant"
    SALES_ORG = "sales_org"
    PURCHASING_ORG = "purchasing_org"
    STORAGE_LOCATION = "storage_location"
    PROFIT_CENTER = "profit_center"
    COST_CENTER = "cost_center"


class DecisionType(str, Enum):
    HIRE = "hire"
    FIRE = "fire"
    SWITCH = "switch"
    APPROVAL = "approval"
    ESCALATION = "escalation"


class PolicyType(str, Enum):
    ACCESS = "access"
    DATA = "data"
    PROCESS = "process"
    COMPLIANCE = "compliance"
    AI_USAGE = "ai_usage"


class PolicyEnforcement(str, Enum):
    ADVISORY = "advisory"
    BLOCKING = "blocking"
    AUDITING = "auditing"


class DataSourceType(str, Enum):
    MOCK = "mock"
    ODATA = "odata"
    RFC = "rfc"
    CDS_VIEW = "cds_view"
    FILE_IMPORT = "file_import"


class SurveyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class OutcomeDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


# ═══════════════════════════════════════════════════════════
#  Property Models
# ═══════════════════════════════════════════════════════════

class SAPProcessProperties(BaseModel):
    """Properties for entity_type='sap_process'."""
    sap_module: SAPModule | None = None
    process_type: ProcessType = ProcessType.E2E
    automation_level: float = Field(default=0.0, ge=0.0, le=1.0)
    throughput_per_day: float | None = None
    cycle_time_hours: float | None = None
    context_freshness: ContextFreshness = ContextFreshness.SNAPSHOT


class SAPObjectProperties(BaseModel):
    """Properties for entity_type='sap_object'."""
    object_type: str = ""
    sap_table: str = ""
    key_fields: list[str] = Field(default_factory=list)
    data_volume: int | None = None


class SAPTransactionProperties(BaseModel):
    """Properties for entity_type='sap_transaction'."""
    tcode: str = ""
    fiori_app_id: str = ""
    process_step: str = ""
    automation_candidate: bool = False


class SAPOrgUnitProperties(BaseModel):
    """Properties for entity_type='sap_org_unit'."""
    unit_type: OrgUnitType = OrgUnitType.COMPANY_CODE
    sap_code: str = ""
    parent_unit_id: str | None = None
    country: str = ""
    currency: str = ""


class DecisionProperties(BaseModel):
    """Properties for entity_type='decision'."""
    decision_type: DecisionType = DecisionType.APPROVAL
    actor: str = ""
    rationale: str = ""
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    alternatives_considered: list[dict[str, Any]] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    traceable: bool = True


class PolicyProperties(BaseModel):
    """Properties for entity_type='policy'."""
    policy_type: PolicyType = PolicyType.ACCESS
    rules: list[dict[str, Any]] = Field(default_factory=list)
    enforcement: PolicyEnforcement = PolicyEnforcement.ADVISORY
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    owner: str = ""
    version: str = "1.0"


class DataSourceProperties(BaseModel):
    """Properties for entity_type='data_source'."""
    source_type: DataSourceType = DataSourceType.MOCK
    refresh_frequency: str = ""
    last_ingestion: datetime | None = None
    data_quality_score: float = Field(default=1.0, ge=0.0, le=1.0)


class SurveyProperties(BaseModel):
    """Properties for entity_type='survey'."""
    survey_type: Literal["odi", "custom"] = "odi"
    status: SurveyStatus = SurveyStatus.DRAFT
    total_outcomes: int = 0
    response_count: int = 0
    target_segment_id: str = ""


class OutcomeProperties(BaseModel):
    """Properties for entity_type='outcome'."""
    survey_id: str = ""
    context_label: str = ""
    direction: OutcomeDirection = OutcomeDirection.MINIMIZE
    importance_mean: float | None = None
    satisfaction_mean: float | None = None
    opportunity_score: float | None = None
    llm_generated: bool = False


class LessonProperties(BaseModel):
    """Properties for entity_type='lesson' — captured lessons learned."""
    lesson_type: Literal["success", "failure", "insight"] = "insight"
    job_id: str = ""
    context: str = ""
    impact: str = ""
    recommendation: str = ""


# ═══════════════════════════════════════════════════════════
#  Registration
# ═══════════════════════════════════════════════════════════

def register_sap_property_models() -> None:
    """Register SAP/Context Graph property models into ENTITY_PROPERTY_MODELS."""
    from jobos.kernel.entity import EntityType, register_property_model

    register_property_model(EntityType.SAP_PROCESS, SAPProcessProperties)
    register_property_model(EntityType.SAP_OBJECT, SAPObjectProperties)
    register_property_model(EntityType.SAP_TRANSACTION, SAPTransactionProperties)
    register_property_model(EntityType.SAP_ORG_UNIT, SAPOrgUnitProperties)
    register_property_model(EntityType.DECISION, DecisionProperties)
    register_property_model(EntityType.POLICY, PolicyProperties)
    register_property_model(EntityType.DATA_SOURCE, DataSourceProperties)
    register_property_model(EntityType.SURVEY, SurveyProperties)
    register_property_model(EntityType.OUTCOME, OutcomeProperties)
    register_property_model(EntityType.LESSON, LessonProperties)


# Auto-register on import
register_sap_property_models()
