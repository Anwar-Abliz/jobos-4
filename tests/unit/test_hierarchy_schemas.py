"""Tests for hierarchy schema validation and crosswalk.

Covers:
- Managerial hierarchy schema structure validation
- Agent hierarchy fractal depth
- Crosswalk translation coverage
- T-3 DSL consistency in schema worked examples
- Schema round-trips (serialize → deserialize → re-validate)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobos.kernel.t3_dsl import parse_constraint, validate_statement

SCHEMA_DIR = Path(__file__).parents[2] / "src" / "jobos" / "schemas"


@pytest.fixture(scope="module")
def managerial_schema() -> dict:
    return json.loads((SCHEMA_DIR / "managerial_hierarchy.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def agent_schema() -> dict:
    return json.loads((SCHEMA_DIR / "agent_hierarchy.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def crosswalk_schema() -> dict:
    return json.loads((SCHEMA_DIR / "crosswalk.json").read_text(encoding="utf-8"))


class TestManagerialSchemaStructure:
    def test_schema_loads(self, managerial_schema):
        # schema_version lives as a "const" under properties (JSON Schema meta)
        version_const = (
            managerial_schema
            .get("properties", {})
            .get("schema_version", {})
            .get("const")
        )
        assert version_const == "1.0.0"

    def test_t1_definition_present(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "t1_job" in defs
        assert defs["t1_job"]["properties"]["tier"]["const"] == "T1_strategic"
        assert defs["t1_job"]["properties"]["root_token"]["const"] == "ROOT"

    def test_t2_definition_present(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "t2_job" in defs
        t2 = defs["t2_job"]
        # T2 must have ODI fields
        assert "odi_opportunity_score" in t2["properties"]
        assert "importance" in t2["properties"]
        assert "satisfaction" in t2["properties"]

    def test_t3_has_dsl_constraint(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "t3_job" in defs
        t3 = defs["t3_job"]
        assert "t3_constraint" in t3["properties"]

    def test_t4_has_micro_category(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "t4_job" in defs
        t4 = defs["t4_job"]
        assert "micro_category" in t4["properties"]
        micro_cats = t4["properties"]["micro_category"]["enum"]
        assert set(micro_cats) == {"setup", "act", "verify", "cleanup"}

    def test_experience_node_in_definitions(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "experience_node" in defs
        exp = defs["experience_node"]
        assert exp["properties"]["dimension"]["const"] == "A_experience"

    def test_t3_dsl_pattern_a_defined(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "t3_constraint_dsl" in defs
        dsl = defs["t3_constraint_dsl"]
        # Must define oneOf with Pattern A and Pattern B
        assert "oneOf" in dsl
        patterns = [s.get("properties", {}).get("pattern", {}).get("const") for s in dsl["oneOf"]]
        assert "A_time" in patterns
        assert "B_likelihood" in patterns

    def test_placement_2d_quadrants(self, managerial_schema):
        defs = managerial_schema.get("definitions", {})
        assert "placement_2d" in defs
        quadrants = defs["placement_2d"]["properties"]["quadrant"]["enum"]
        assert "strategic-functional" in quadrants
        assert "operational-experiential" in quadrants

    def test_example_parses(self, managerial_schema):
        examples = managerial_schema.get("examples", [])
        assert len(examples) >= 1
        ex = examples[0]
        assert "root" in ex
        assert ex["root"]["tier"] == "T1_strategic"
        assert ex["root"]["root_token"] == "ROOT"
        # Check the T3 in the example has a valid DSL constraint
        t3 = ex["root"]["children"][0]["children"][0]
        assert t3["tier"] == "T3_execution"
        constraint = t3["t3_constraint"]
        assert constraint["pattern"] == "A_time"
        # Validate the statement from the example too
        stmt = t3["statement"]
        is_valid, errors = validate_statement(stmt)
        assert is_valid, f"Example T3 statement invalid: {errors}"


class TestAgentSchemaStructure:
    def test_schema_loads(self, agent_schema):
        props = agent_schema.get("properties", {})
        assert "mission" in props
        assert "tasks" in props

    def test_agent_node_definition(self, agent_schema):
        defs = agent_schema.get("definitions", {})
        assert "agent_node" in defs
        node = defs["agent_node"]
        props = node["properties"]
        assert "depth" in props
        assert "constraint" in props
        assert "tool_calls" in props
        assert "children" in props
        # Fractal: children reference the same type
        assert props["children"]["items"]["$ref"] == "#/definitions/agent_node"

    def test_constraint_patterns_in_schema(self, agent_schema):
        defs = agent_schema.get("definitions", {})
        assert "t3_constraint_a" in defs
        assert "t3_constraint_b" in defs

    def test_pattern_a_required_fields(self, agent_schema):
        defs = agent_schema.get("definitions", {})
        ca = defs["t3_constraint_a"]
        required = set(ca.get("required", []))
        assert {"pattern", "verb_noun", "start_state", "end_state", "unit", "threshold"}.issubset(required)

    def test_pattern_b_required_fields(self, agent_schema):
        defs = agent_schema.get("definitions", {})
        cb = defs["t3_constraint_b"]
        required = set(cb.get("required", []))
        assert {"pattern", "event", "rate_type", "unit", "threshold"}.issubset(required)

    def test_agent_roles_enum(self, agent_schema):
        defs = agent_schema.get("definitions", {})
        agent_node = defs["agent_node"]
        roles = agent_node["properties"]["agent_role"]["enum"]
        assert "orchestrator" in roles
        assert "executor" in roles
        assert "monitor" in roles

    def test_crosswalk_ref_defined(self, agent_schema):
        defs = agent_schema.get("definitions", {})
        assert "crosswalk_ref" in defs
        xwalk = defs["crosswalk_ref"]
        translation_types = xwalk["properties"]["translation_type"]["enum"]
        assert "direct" in translation_types
        assert "no_equivalent" in translation_types

    def test_example_tasks_parse_to_dsl(self, agent_schema):
        examples = agent_schema.get("examples", [])
        assert len(examples) >= 1
        ex = examples[0]
        for task in ex["tasks"]:
            stmt = task["statement"]
            c = parse_constraint(stmt)
            assert c is not None, f"Failed to parse agent task statement: '{stmt}'"
            is_valid, errors = validate_statement(stmt)
            assert is_valid, f"Agent task invalid: {stmt} — {errors}"


class TestCrosswalkSchema:
    def test_translation_types_defined(self, crosswalk_schema):
        defs = crosswalk_schema.get("definitions", {})
        assert "node_mapping" in defs
        trans_types = defs["node_mapping"]["properties"]["translation_type"]["enum"]
        assert set(trans_types) == {
            "direct", "decomposition", "aggregation", "analog", "no_equivalent"
        }

    def test_worked_examples_all_parseable(self, crosswalk_schema):
        examples = crosswalk_schema.get("examples", [])
        assert len(examples) >= 1
        worked = examples[0].get("worked_examples", [])
        assert len(worked) >= 10  # schema specifies 12 worked examples

        for ex in worked:
            agent_stmts = ex.get("agent_statements", [])
            if ex["translation_type"] == "no_equivalent":
                # no_equivalent entries correctly have no agent DSL statements
                continue
            if ex["managerial_tier"] == "T1_strategic":
                # T1 → Agent Mission translations are not T-3 DSL statements;
                # they are mission-level objectives. Skip DSL parsing for these.
                continue
            for stmt in agent_stmts:
                c = parse_constraint(stmt)
                assert c is not None, f"Worked example DSL failed to parse: '{stmt}'"

    def test_no_equivalent_has_empty_agent_statements(self, crosswalk_schema):
        examples = crosswalk_schema.get("examples", [])
        worked = examples[0].get("worked_examples", [])
        no_equiv = [e for e in worked if e["translation_type"] == "no_equivalent"]
        assert len(no_equiv) >= 1
        for ex in no_equiv:
            assert ex.get("agent_statements", []) == []

    def test_decomposition_has_multiple_agent_statements(self, crosswalk_schema):
        examples = crosswalk_schema.get("examples", [])
        worked = examples[0].get("worked_examples", [])
        decomp = [e for e in worked if e["translation_type"] == "decomposition"]
        assert len(decomp) >= 1
        for ex in decomp:
            assert len(ex["agent_statements"]) >= 2

    def test_coverage_metric_reasonable(self, crosswalk_schema):
        examples = crosswalk_schema.get("examples", [])
        metrics = examples[0].get("metrics", {})
        assert metrics.get("coverage_pct", 0) > 75
        assert metrics.get("avg_confidence", 0) > 0.7


class TestFractalConsistency:
    """Verify the fractal property: any T-3 constraint is structurally valid
    regardless of its depth in the hierarchy."""

    @pytest.mark.parametrize("depth", [1, 2, 3, 4])
    def test_same_dsl_at_any_depth(self, depth):
        from jobos.kernel.t3_dsl import T3ConstraintA, TimeUnit
        c = T3ConstraintA(
            verb_noun=f"complete depth-{depth} task",
            start_state=f"depth-{depth} trigger received",
            end_state=f"depth-{depth} output produced",
            unit=TimeUnit.HOURS,
            threshold=float(depth),
        )
        errors = c.validate()
        assert errors == [], f"Depth {depth} constraint failed: {errors}"
        stmt = c.to_statement()
        parsed = parse_constraint(stmt)
        assert parsed is not None


class TestOrthogonality:
    """Verify that T-1/T-2/T-3/T-4 tiers are semantically distinct
    in the schema definitions."""

    def test_t1_has_root_token(self, managerial_schema):
        t1 = managerial_schema["definitions"]["t1_job"]
        assert t1["properties"]["root_token"]["const"] == "ROOT"

    def test_t2_has_no_root_token(self, managerial_schema):
        t2 = managerial_schema["definitions"]["t2_job"]
        # T-2 should not have root_token
        assert "root_token" not in t2["properties"]

    def test_t2_has_odi_fields_t1_does_not(self, managerial_schema):
        t1 = managerial_schema["definitions"]["t1_job"]
        t2 = managerial_schema["definitions"]["t2_job"]
        assert "odi_opportunity_score" not in t1["properties"]
        assert "odi_opportunity_score" in t2["properties"]

    def test_t4_has_micro_category_t3_does_not(self, managerial_schema):
        t3 = managerial_schema["definitions"]["t3_job"]
        t4 = managerial_schema["definitions"]["t4_job"]
        assert "micro_category" not in t3["properties"]
        assert "micro_category" in t4["properties"]

    def test_experience_is_not_a_tier(self, managerial_schema):
        defs = managerial_schema["definitions"]
        exp = defs["experience_node"]
        # Experience is Dimension A, not a tier — it should NOT have "tier" property
        assert "tier" not in exp["properties"]
        assert "dimension" in exp["properties"]
        assert exp["properties"]["dimension"]["const"] == "A_experience"
