"""Tests for T-3 DSL constraint language.

Covers:
- Pattern A (time minimization) parsing
- Pattern B (likelihood minimization) parsing
- Statement rendering (round-trip)
- Validation rules
- infer_pattern() heuristics
- translate_t2_to_t3_dsl() translation
- from_dict() deserialization
- Edge cases: malformed input, missing fields, threshold sanity
"""
from __future__ import annotations

import pytest

from jobos.kernel.t3_dsl import (
    T3ConstraintA,
    T3ConstraintB,
    T3Pattern,
    TimeUnit,
    RateType,
    RateUnit,
    parse_constraint,
    validate_statement,
    render_statement,
    from_dict,
    infer_pattern,
    translate_t2_to_t3_dsl,
)


class TestPatternAParsing:
    def test_canonical_statement(self):
        stmt = (
            "Minimize the time to qualify a lead "
            "from first contact to CRM stage updated, "
            "measured in hours, target ≤ 4"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert isinstance(c, T3ConstraintA)
        assert c.pattern == T3Pattern.A_TIME
        assert "qualify a lead" in c.verb_noun
        assert c.unit == TimeUnit.HOURS
        assert c.threshold == 4.0

    def test_with_le_ascii(self):
        stmt = (
            "Minimize the time to process a purchase order "
            "from PO submitted to supplier notified, "
            "measured in business_days, target <= 2"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert isinstance(c, T3ConstraintA)
        assert c.threshold == 2.0
        assert c.unit == TimeUnit.BUSINESS_DAYS

    def test_minutes_unit(self):
        stmt = (
            "Minimize the time to enrich a lead record "
            "from CRM creation to ICP score computed, "
            "measured in minutes, target ≤ 15"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert c.unit == TimeUnit.MINUTES
        assert c.threshold == 15.0

    def test_calendar_days(self):
        stmt = (
            "Minimize the time to resolve a billing dispute "
            "from dispute opened to credit issued, "
            "measured in calendar_days, target ≤ 5"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert c.unit == TimeUnit.CALENDAR_DAYS

    def test_round_trip(self):
        original = T3ConstraintA(
            verb_noun="onboard a new user account",
            start_state="user email verified",
            end_state="user account active with first login recorded",
            unit=TimeUnit.HOURS,
            threshold=4.0,
            baseline=24.0,
        )
        stmt = original.to_statement()
        parsed = parse_constraint(stmt)
        assert parsed is not None
        assert isinstance(parsed, T3ConstraintA)
        assert parsed.verb_noun == original.verb_noun
        assert parsed.threshold == original.threshold
        assert parsed.unit == original.unit


class TestPatternBParsing:
    def test_canonical_statement(self):
        stmt = (
            "Minimize the likelihood of invoice processing error due to PO mismatch, "
            "measured as error_rate in percent, target ≤ 0.5"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert isinstance(c, T3ConstraintB)
        assert c.pattern == T3Pattern.B_LIKELIHOOD
        assert "invoice processing error" in c.event
        assert c.rate_type == RateType.ERROR_RATE
        assert c.unit == RateUnit.PERCENT
        assert c.threshold == 0.5

    def test_breach_rate(self):
        stmt = (
            "Minimize the likelihood of SLA breach on P1 tickets, "
            "measured as breach_rate in per_1000, target ≤ 5"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert isinstance(c, T3ConstraintB)
        assert c.rate_type == RateType.BREACH_RATE
        assert c.unit == RateUnit.PER_1000
        assert c.threshold == 5.0

    def test_churn_rate(self):
        stmt = (
            "Minimize the likelihood of customer churn within 90 days, "
            "measured as churn_rate in percent, target ≤ 3"
        )
        c = parse_constraint(stmt)
        assert c is not None
        assert isinstance(c, T3ConstraintB)
        assert c.rate_type == RateType.CHURN_RATE

    def test_round_trip(self):
        original = T3ConstraintB(
            event="contract renewal lapse due to delayed stakeholder sign-off",
            rate_type=RateType.FAILURE_RATE,
            unit=RateUnit.PERCENT,
            threshold=2.0,
            baseline=15.0,
        )
        stmt = original.to_statement()
        parsed = parse_constraint(stmt)
        assert parsed is not None
        assert isinstance(parsed, T3ConstraintB)
        assert parsed.threshold == original.threshold
        assert parsed.rate_type == original.rate_type


class TestValidation:
    def test_valid_pattern_a(self):
        stmt = (
            "Minimize the time to close a deal "
            "from qualification completed to contract signed, "
            "measured in hours, target ≤ 48"
        )
        is_valid, errors = validate_statement(stmt)
        assert is_valid
        assert errors == []

    def test_valid_pattern_b(self):
        stmt = (
            "Minimize the likelihood of data sync failure between CRM and billing, "
            "measured as failure_rate in percent, target ≤ 0.1"
        )
        is_valid, errors = validate_statement(stmt)
        assert is_valid

    def test_invalid_no_pattern(self):
        stmt = "Reduce customer churn in the SMB segment"
        is_valid, errors = validate_statement(stmt)
        assert not is_valid
        assert len(errors) >= 1
        assert "Pattern A" in errors[0] or "Pattern B" in errors[0]

    def test_constraint_a_zero_threshold(self):
        c = T3ConstraintA(
            verb_noun="process an order",
            start_state="order placed",
            end_state="order shipped",
            unit=TimeUnit.HOURS,
            threshold=0.0,
        )
        errors = c.validate()
        assert any("threshold" in e for e in errors)

    def test_constraint_b_zero_threshold_ok(self):
        # threshold=0 is valid for B — it means "eliminate completely"
        c = T3ConstraintB(
            event="data loss incident",
            rate_type=RateType.FAILURE_RATE,
            unit=RateUnit.PERCENT,
            threshold=0.0,
        )
        errors = c.validate()
        # No error for threshold=0 in Pattern B
        assert all("threshold" not in e for e in errors)

    def test_constraint_a_baseline_sanity(self):
        # Warn when baseline is already better than target
        c = T3ConstraintA(
            verb_noun="review a ticket",
            start_state="ticket created",
            end_state="ticket reviewed",
            unit=TimeUnit.MINUTES,
            threshold=30.0,
            baseline=15.0,  # already better than target!
        )
        errors = c.validate()
        assert any("baseline" in e for e in errors)

    def test_constraint_a_missing_verb_noun(self):
        c = T3ConstraintA(
            verb_noun="",
            start_state="task started",
            end_state="task done",
            unit=TimeUnit.HOURS,
            threshold=2.0,
        )
        errors = c.validate()
        assert any("verb_noun" in e for e in errors)


class TestInferPattern:
    def test_time_signals(self):
        assert infer_pattern("Reduce the time it takes to qualify a lead") == T3Pattern.A_TIME
        assert infer_pattern("Speed up cycle time for invoice processing") == T3Pattern.A_TIME
        assert infer_pattern("Minimize time to provision access") == T3Pattern.A_TIME

    def test_likelihood_signals(self):
        assert infer_pattern("Minimize the likelihood of data entry errors") == T3Pattern.B_LIKELIHOOD
        assert infer_pattern("Reduce error rates in order processing") == T3Pattern.B_LIKELIHOOD
        assert infer_pattern("Ensure compliance with GDPR regulations") == T3Pattern.B_LIKELIHOOD
        assert infer_pattern("Prevent unauthorized access to customer data") == T3Pattern.B_LIKELIHOOD


class TestTranslateT2:
    def test_time_outcome_returns_pattern_a(self):
        constraints = translate_t2_to_t3_dsl(
            "Reduce the time it takes to onboard a new customer",
            importance=8.0,
            baseline_time=72.0,
        )
        assert len(constraints) >= 1
        assert isinstance(constraints[0], T3ConstraintA)
        assert constraints[0].threshold < 72.0  # must improve on baseline

    def test_risk_outcome_returns_pattern_b(self):
        constraints = translate_t2_to_t3_dsl(
            "Minimize errors in invoice processing",
            importance=7.0,
            baseline_rate=3.0,
        )
        assert len(constraints) >= 1
        assert isinstance(constraints[0], T3ConstraintB)
        assert constraints[0].threshold < 3.0  # must improve on baseline

    def test_no_baseline(self):
        constraints = translate_t2_to_t3_dsl(
            "Reduce time to close a support ticket",
            importance=6.0,
        )
        assert len(constraints) >= 1
        assert constraints[0].threshold > 0


class TestFromDict:
    def test_pattern_a_from_dict(self):
        data = {
            "pattern": "A_time",
            "verb_noun": "resolve a ticket",
            "start_state": "ticket assigned",
            "end_state": "ticket closed",
            "unit": "hours",
            "threshold": 8.0,
            "baseline": 24.0,
        }
        c = from_dict(data)
        assert c is not None
        assert isinstance(c, T3ConstraintA)
        assert c.threshold == 8.0
        assert c.baseline == 24.0

    def test_pattern_b_from_dict(self):
        data = {
            "pattern": "B_likelihood",
            "event": "inventory count mismatch at cycle audit",
            "rate_type": "defect_rate",
            "unit": "percent",
            "threshold": 0.5,
            "measurement_window": "rolling_30d",
        }
        c = from_dict(data)
        assert c is not None
        assert isinstance(c, T3ConstraintB)
        assert c.event == "inventory count mismatch at cycle audit"
        assert c.measurement_window == "rolling_30d"

    def test_invalid_pattern_returns_none(self):
        data = {"pattern": "C_unknown", "event": "something bad"}
        c = from_dict(data)
        assert c is None

    def test_missing_required_field_returns_none(self):
        data = {
            "pattern": "A_time",
            "verb_noun": "do something",
            # missing start_state, end_state, unit, threshold
        }
        c = from_dict(data)
        assert c is None


class TestRenderStatement:
    def test_pattern_a_render(self):
        c = T3ConstraintA(
            verb_noun="generate a financial forecast",
            start_state="forecast period defined",
            end_state="forecast published to stakeholder dashboard",
            unit=TimeUnit.BUSINESS_DAYS,
            threshold=3.0,
        )
        stmt = render_statement(c)
        assert "Minimize the time to" in stmt
        assert "generate a financial forecast" in stmt
        assert "business_days" in stmt
        assert "3.0" in stmt

    def test_pattern_b_render(self):
        c = T3ConstraintB(
            event="unauthorized data access event passing undetected",
            rate_type=RateType.MISS_RATE,
            unit=RateUnit.PERCENT,
            threshold=0.01,
        )
        stmt = render_statement(c)
        assert "Minimize the likelihood of" in stmt
        assert "miss_rate" in stmt
        assert "0.01" in stmt


class TestIndustryExamples:
    """End-to-end examples from the crosswalk schema worked examples."""

    @pytest.mark.parametrize("statement", [
        "Minimize the time to qualify a lead from first contact to CRM stage updated, measured in hours, target ≤ 4",
        "Minimize the likelihood of invoice processing error due to PO field mismatch, measured as error_rate in percent, target ≤ 0.1",
        "Minimize the time to resolve a P2 support ticket from ticket assignment to resolution confirmed, measured in hours, target ≤ 8",
        "Minimize the likelihood of a cross-border transaction processed without sanctions screening, measured as breach_rate in per_10000, target ≤ 1",
        "Minimize the time to provision all required software licenses from IT ticket creation to first login confirmed, measured in hours, target ≤ 4",
        "Minimize the likelihood of inventory count discrepancy > 1% detected at cycle audit, measured as defect_rate in percent, target ≤ 0.5",
        "Minimize the time to complete financial close reconciliation from period end to CFO sign-off, measured in business_days, target ≤ 3",
        "Minimize the likelihood of a material reconciliation error detected post-close, measured as error_rate in per_1000, target ≤ 1",
        "Minimize the time to complete a deal qualification from discovery call to CRM stage update, measured in hours, target ≤ 24",
        "Minimize the likelihood of a qualified lead going uncontacted for > 1 business day, measured as miss_rate in percent, target ≤ 2",
    ])
    def test_industry_examples_parse(self, statement: str):
        c = parse_constraint(statement)
        assert c is not None, f"Failed to parse: {statement}"
        is_valid, errors = validate_statement(statement)
        assert is_valid, f"Invalid: {statement} — errors: {errors}"
