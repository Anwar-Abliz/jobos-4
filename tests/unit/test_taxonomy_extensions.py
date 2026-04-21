"""Tests for taxonomy extensions: ContextProperties, ChoiceSet, bi-temporal fields.

Covers:
- ContextProperties with constraint/catalyst factors
- ContextProperties backward compatibility (without new fields)
- ChoiceSet model creation
- EntityBase with and without bi-temporal fields
"""
from __future__ import annotations

from datetime import datetime, timezone

from jobos.kernel.entity import (
    ContextProperties,
    ChoiceSet,
    EntityBase,
    EntityType,
    HiringEvent,
    HiringEventType,
)


class TestContextPropertiesExtensions:
    def test_constraint_factors(self):
        props = ContextProperties(
            who="team-a",
            constraint_factors=[
                {"name": "budget", "type": "financial", "severity": 0.8, "description": "Limited Q3 budget"},
            ],
        )
        assert len(props.constraint_factors) == 1
        assert props.constraint_factors[0]["name"] == "budget"

    def test_catalyst_factors(self):
        props = ContextProperties(
            who="team-a",
            catalyst_factors=[
                {"name": "new_hire", "type": "resource", "impact": 0.6, "description": "Senior engineer joining"},
            ],
        )
        assert len(props.catalyst_factors) == 1
        assert props.catalyst_factors[0]["impact"] == 0.6

    def test_backward_compat_without_new_fields(self):
        """ContextProperties created without new fields should default to empty lists."""
        props = ContextProperties(who="team-b", why="testing")
        assert props.constraint_factors == []
        assert props.catalyst_factors == []
        assert props.who == "team-b"

    def test_both_factors_together(self):
        props = ContextProperties(
            constraint_factors=[{"name": "c1", "type": "t", "severity": 0.5, "description": "d"}],
            catalyst_factors=[{"name": "k1", "type": "t", "impact": 0.9, "description": "d"}],
        )
        assert len(props.constraint_factors) == 1
        assert len(props.catalyst_factors) == 1


class TestChoiceSet:
    def test_creation_minimal(self):
        cs = ChoiceSet(job_id="j1")
        assert cs.job_id == "j1"
        assert cs.context_id is None
        assert cs.candidates == []
        assert cs.selection_criteria == {}
        assert isinstance(cs.generated_at, datetime)

    def test_creation_full(self):
        cs = ChoiceSet(
            job_id="j1",
            context_id="ctx1",
            candidates=[
                {"id": "c1", "estimated_impact": 0.9},
                {"id": "c2", "estimated_impact": 0.4},
            ],
            selection_criteria={"method": "efe_minimization"},
        )
        assert cs.context_id == "ctx1"
        assert len(cs.candidates) == 2
        assert cs.selection_criteria["method"] == "efe_minimization"


class TestBiTemporalFields:
    def test_entity_without_bitemporal_fields(self):
        """EntityBase created without bi-temporal fields defaults to None."""
        e = EntityBase(entity_type=EntityType.JOB, statement="Define scope")
        assert e.event_time is None
        assert e.ingestion_time is None

    def test_entity_with_bitemporal_fields(self):
        now = datetime.now(timezone.utc)
        e = EntityBase(
            entity_type=EntityType.JOB,
            statement="Define scope",
            event_time=now,
            ingestion_time=now,
        )
        assert e.event_time == now
        assert e.ingestion_time == now

    def test_entity_serialization_roundtrip(self):
        now = datetime.now(timezone.utc)
        e = EntityBase(
            entity_type=EntityType.JOB,
            statement="Define scope",
            event_time=now,
        )
        data = e.model_dump()
        e2 = EntityBase.model_validate(data)
        assert e2.event_time == now
        assert e2.ingestion_time is None


class TestHiringEventChoiceSetSnapshot:
    def test_hiring_event_without_choice_set(self):
        event = HiringEvent(
            hirer_id="h1",
            hiree_id="h2",
            event_type=HiringEventType.HIRE,
        )
        assert event.choice_set_snapshot == {}

    def test_hiring_event_with_choice_set(self):
        event = HiringEvent(
            hirer_id="h1",
            hiree_id="h2",
            event_type=HiringEventType.HIRE,
            choice_set_snapshot={"candidates": ["c1", "c2"], "selected": "c1"},
        )
        assert event.choice_set_snapshot["selected"] == "c1"
