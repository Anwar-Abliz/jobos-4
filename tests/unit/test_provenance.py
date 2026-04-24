"""Tests for entity provenance tracking.

Covers:
- EntityBase defaults to provenance='user'
- provenance can be set to various values
- provenance_source field
- Backward compat: entities without provenance deserialize fine
"""
from __future__ import annotations

import pytest

from jobos.kernel.entity import EntityBase, EntityType


class TestEntityProvenance:
    """Provenance field on EntityBase."""

    def test_default_provenance_is_user(self):
        entity = EntityBase(entity_type=EntityType.JOB)
        assert entity.provenance == "user"

    @pytest.mark.parametrize("prov", ["llm", "template", "import", "system", "sop_ingest"])
    def test_provenance_accepts_valid_values(self, prov: str):
        entity = EntityBase(entity_type=EntityType.JOB, provenance=prov)
        assert entity.provenance == prov

    def test_provenance_source_default_empty(self):
        entity = EntityBase(entity_type=EntityType.JOB)
        assert entity.provenance_source == ""

    def test_provenance_source_can_be_set(self):
        entity = EntityBase(
            entity_type=EntityType.JOB,
            provenance="llm",
            provenance_source="gpt-4.1-mini",
        )
        assert entity.provenance_source == "gpt-4.1-mini"

    def test_backward_compat_without_provenance(self):
        """Entities serialized before provenance was added should still load."""
        raw = {
            "id": "abc123def456",
            "entity_type": "job",
            "name": "Legacy entity",
            "statement": "Manage workflow",
            "status": "active",
            "properties": {},
            "labels": [],
        }
        entity = EntityBase.model_validate(raw)
        assert entity.provenance == "user"
        assert entity.provenance_source == ""

    def test_provenance_roundtrip(self):
        entity = EntityBase(
            entity_type=EntityType.ASSUMPTION,
            provenance="import",
            provenance_source="pilot_v2.yaml",
        )
        dumped = entity.model_dump()
        restored = EntityBase.model_validate(dumped)
        assert restored.provenance == "import"
        assert restored.provenance_source == "pilot_v2.yaml"
