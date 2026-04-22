"""Tests for SAP Context Graph entity property models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from jobos.kernel.entity import EntityType, EntityBase, ENTITY_PROPERTY_MODELS, validate_entity
from jobos.kernel.sap_entities import (
    SAPProcessProperties,
    SAPObjectProperties,
    SAPTransactionProperties,
    SAPOrgUnitProperties,
    DecisionProperties,
    PolicyProperties,
    DataSourceProperties,
    SurveyProperties,
    OutcomeProperties,
    SAPModule,
    ProcessType,
    ContextFreshness,
    OrgUnitType,
    DecisionType,
    PolicyType,
    PolicyEnforcement,
    DataSourceType,
    SurveyStatus,
    OutcomeDirection,
)


class TestEntityTypeRegistration:
    def test_new_entity_types_exist(self):
        assert EntityType.SAP_PROCESS.value == "sap_process"
        assert EntityType.SAP_OBJECT.value == "sap_object"
        assert EntityType.SAP_TRANSACTION.value == "sap_transaction"
        assert EntityType.SAP_ORG_UNIT.value == "sap_org_unit"
        assert EntityType.DECISION.value == "decision"
        assert EntityType.POLICY.value == "policy"
        assert EntityType.DATA_SOURCE.value == "data_source"
        assert EntityType.SURVEY.value == "survey"
        assert EntityType.OUTCOME.value == "outcome"

    def test_property_models_registered(self):
        for et in [
            EntityType.SAP_PROCESS,
            EntityType.SAP_OBJECT,
            EntityType.SAP_TRANSACTION,
            EntityType.SAP_ORG_UNIT,
            EntityType.DECISION,
            EntityType.POLICY,
            EntityType.DATA_SOURCE,
            EntityType.SURVEY,
            EntityType.OUTCOME,
        ]:
            assert et in ENTITY_PROPERTY_MODELS, f"{et} not registered"


class TestSAPProcessProperties:
    def test_defaults(self):
        props = SAPProcessProperties()
        assert props.sap_module is None
        assert props.process_type == ProcessType.E2E
        assert props.automation_level == 0.0
        assert props.context_freshness == ContextFreshness.SNAPSHOT

    def test_serialize_deserialize(self):
        props = SAPProcessProperties(
            sap_module=SAPModule.SD,
            process_type=ProcessType.SUB,
            automation_level=0.7,
            throughput_per_day=500.0,
            cycle_time_hours=24.0,
            context_freshness=ContextFreshness.LIVE,
        )
        data = props.model_dump()
        restored = SAPProcessProperties.model_validate(data)
        assert restored.sap_module == SAPModule.SD
        assert restored.automation_level == 0.7

    def test_automation_level_bounds(self):
        with pytest.raises(ValidationError):
            SAPProcessProperties(automation_level=1.5)
        with pytest.raises(ValidationError):
            SAPProcessProperties(automation_level=-0.1)

    def test_entity_validation(self):
        entity = EntityBase(
            entity_type=EntityType.SAP_PROCESS,
            properties={"sap_module": "SD", "process_type": "e2e"},
        )
        validate_entity(entity)


class TestSAPObjectProperties:
    def test_defaults(self):
        props = SAPObjectProperties()
        assert props.object_type == ""
        assert props.key_fields == []

    def test_serialize_deserialize(self):
        props = SAPObjectProperties(
            object_type="Material",
            sap_table="MARA",
            key_fields=["MATNR"],
            data_volume=1000000,
        )
        data = props.model_dump()
        restored = SAPObjectProperties.model_validate(data)
        assert restored.sap_table == "MARA"
        assert restored.data_volume == 1000000


class TestSAPTransactionProperties:
    def test_defaults(self):
        props = SAPTransactionProperties()
        assert props.tcode == ""
        assert props.automation_candidate is False

    def test_serialize_deserialize(self):
        props = SAPTransactionProperties(
            tcode="VA01",
            fiori_app_id="F2342",
            process_step="Create Sales Order",
            automation_candidate=True,
        )
        data = props.model_dump()
        restored = SAPTransactionProperties.model_validate(data)
        assert restored.tcode == "VA01"


class TestSAPOrgUnitProperties:
    def test_defaults(self):
        props = SAPOrgUnitProperties()
        assert props.unit_type == OrgUnitType.COMPANY_CODE

    def test_serialize_deserialize(self):
        props = SAPOrgUnitProperties(
            unit_type=OrgUnitType.PLANT,
            sap_code="1000",
            country="DE",
            currency="EUR",
        )
        data = props.model_dump()
        restored = SAPOrgUnitProperties.model_validate(data)
        assert restored.unit_type == OrgUnitType.PLANT


class TestDecisionProperties:
    def test_defaults(self):
        props = DecisionProperties()
        assert props.decision_type == DecisionType.APPROVAL
        assert props.traceable is True

    def test_serialize_deserialize(self):
        props = DecisionProperties(
            decision_type=DecisionType.HIRE,
            actor="system",
            rationale="Best EFE score",
            context_snapshot={"vfe": 0.3},
            alternatives_considered=[{"id": "abc", "efe": 0.5}],
            policy_ids=["pol1"],
        )
        data = props.model_dump()
        restored = DecisionProperties.model_validate(data)
        assert restored.decision_type == DecisionType.HIRE
        assert len(restored.alternatives_considered) == 1


class TestPolicyProperties:
    def test_defaults(self):
        props = PolicyProperties()
        assert props.policy_type == PolicyType.ACCESS
        assert props.enforcement == PolicyEnforcement.ADVISORY

    def test_serialize_deserialize(self):
        props = PolicyProperties(
            policy_type=PolicyType.AI_USAGE,
            rules=[{"action": "deny", "condition": "pii_access"}],
            enforcement=PolicyEnforcement.BLOCKING,
            owner="admin",
            version="2.0",
        )
        data = props.model_dump()
        restored = PolicyProperties.model_validate(data)
        assert restored.enforcement == PolicyEnforcement.BLOCKING


class TestDataSourceProperties:
    def test_defaults(self):
        props = DataSourceProperties()
        assert props.source_type == DataSourceType.MOCK
        assert props.data_quality_score == 1.0

    def test_quality_bounds(self):
        with pytest.raises(ValidationError):
            DataSourceProperties(data_quality_score=1.5)


class TestSurveyProperties:
    def test_defaults(self):
        props = SurveyProperties()
        assert props.survey_type == "odi"
        assert props.status == SurveyStatus.DRAFT

    def test_serialize_deserialize(self):
        props = SurveyProperties(
            survey_type="custom",
            status=SurveyStatus.ACTIVE,
            total_outcomes=20,
            response_count=50,
            target_segment_id="seg1",
        )
        data = props.model_dump()
        restored = SurveyProperties.model_validate(data)
        assert restored.total_outcomes == 20


class TestOutcomeProperties:
    def test_defaults(self):
        props = OutcomeProperties()
        assert props.direction == OutcomeDirection.MINIMIZE
        assert props.llm_generated is False

    def test_serialize_deserialize(self):
        props = OutcomeProperties(
            survey_id="survey1",
            context_label="Order Processing",
            direction=OutcomeDirection.MAXIMIZE,
            importance_mean=8.5,
            satisfaction_mean=4.2,
            opportunity_score=12.8,
            llm_generated=True,
        )
        data = props.model_dump()
        restored = OutcomeProperties.model_validate(data)
        assert restored.opportunity_score == 12.8
