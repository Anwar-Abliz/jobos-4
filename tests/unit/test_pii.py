"""Tests for PII detection and redaction.

Covers:
- detect_pii finds email addresses
- detect_pii finds phone numbers
- detect_pii finds SSN patterns
- detect_pii finds credit card numbers
- detect_pii returns empty for clean text
- redact_pii replaces all PII with [REDACTED]
- check_entity_for_pii scans statement, name, and properties
"""
from __future__ import annotations

import pytest

from jobos.kernel.pii import check_entity_for_pii, detect_pii, redact_pii
from jobos.kernel.entity import EntityBase, EntityType


class TestDetectPII:
    def test_finds_email_addresses(self):
        text = "Contact john.doe@example.com for details"
        findings = detect_pii(text)

        assert len(findings) >= 1
        types = [f["type"] for f in findings]
        assert "email" in types
        email_match = next(f for f in findings if f["type"] == "email")
        assert email_match["match"] == "john.doe@example.com"

    def test_finds_phone_numbers(self):
        text = "Call us at 555-123-4567 for support"
        findings = detect_pii(text)

        types = [f["type"] for f in findings]
        assert "phone" in types
        phone_match = next(f for f in findings if f["type"] == "phone")
        assert "555" in phone_match["match"]

    def test_finds_phone_without_dashes(self):
        text = "Phone: 5551234567"
        findings = detect_pii(text)
        types = [f["type"] for f in findings]
        assert "phone" in types

    def test_finds_ssn_patterns(self):
        text = "SSN: 123-45-6789"
        findings = detect_pii(text)

        types = [f["type"] for f in findings]
        assert "ssn" in types
        ssn_match = next(f for f in findings if f["type"] == "ssn")
        assert ssn_match["match"] == "123-45-6789"

    def test_finds_credit_card_numbers(self):
        text = "Card: 4111-1111-1111-1111"
        findings = detect_pii(text)

        types = [f["type"] for f in findings]
        assert "credit_card" in types

    def test_finds_credit_card_without_dashes(self):
        text = "Card number is 4111111111111111"
        findings = detect_pii(text)
        types = [f["type"] for f in findings]
        assert "credit_card" in types

    def test_clean_text_returns_empty(self):
        text = "Reduce processing time for order fulfillment"
        findings = detect_pii(text)
        assert findings == []

    def test_multiple_pii_in_one_text(self):
        text = "Email: test@example.com, Phone: 555-111-2222"
        findings = detect_pii(text)
        types = {f["type"] for f in findings}
        assert "email" in types
        assert "phone" in types


class TestRedactPII:
    def test_redacts_all_pii(self):
        text = "Contact john@example.com or call 555-123-4567"
        redacted = redact_pii(text)

        assert "john@example.com" not in redacted
        assert "555-123-4567" not in redacted
        assert "[REDACTED]" in redacted

    def test_redacts_ssn(self):
        text = "SSN is 123-45-6789"
        redacted = redact_pii(text)
        assert "123-45-6789" not in redacted
        assert "[REDACTED]" in redacted

    def test_clean_text_unchanged(self):
        text = "Improve customer satisfaction score"
        redacted = redact_pii(text)
        assert redacted == text


class TestCheckEntityForPII:
    def test_scans_statement(self):
        entity = EntityBase(
            entity_type=EntityType.JOB,
            statement="Contact admin@corp.com for access",
        )
        findings = check_entity_for_pii(entity)

        assert len(findings) >= 1
        assert any(f["field"] == "statement" for f in findings)

    def test_scans_name(self):
        entity = EntityBase(
            entity_type=EntityType.EXECUTOR,
            name="John Doe 555-111-2222",
        )
        findings = check_entity_for_pii(entity)

        assert len(findings) >= 1
        assert any(f["field"] == "name" for f in findings)

    def test_scans_properties(self):
        entity = EntityBase(
            entity_type=EntityType.CONTEXT,
            properties={"who": "alice@company.com", "scope": "broad"},
        )
        findings = check_entity_for_pii(entity)

        assert len(findings) >= 1
        assert any(f["field"] == "properties.who" for f in findings)

    def test_clean_entity_returns_empty(self):
        entity = EntityBase(
            entity_type=EntityType.JOB,
            name="Order Processing",
            statement="Process incoming orders efficiently",
            properties={"job_type": "core_functional"},
        )
        findings = check_entity_for_pii(entity)
        assert findings == []
