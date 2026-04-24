"""JobOS 4.0 — PII Detection and Redaction.

Detects personally identifiable information in entity text fields
and provides redaction utilities.  Used as a safety check during
entity creation to warn when sensitive data may be stored.
"""
from __future__ import annotations

import re
from typing import Any

from jobos.kernel.entity import EntityBase

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    ),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
    ),
    "ip_address": re.compile(
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
    ),
}

_REDACTED = "[REDACTED]"


def detect_pii(text: str) -> list[dict[str, Any]]:
    """Scan text for PII patterns.

    Returns list of {type, match, start, end} for each detected item.
    """
    findings: list[dict[str, Any]] = []
    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append({
                "type": pii_type,
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
            })
    return findings


def redact_pii(text: str) -> str:
    """Replace all detected PII with [REDACTED]."""
    result = text
    for pattern in PII_PATTERNS.values():
        result = pattern.sub(_REDACTED, result)
    return result


def check_entity_for_pii(entity: EntityBase) -> list[dict[str, Any]]:
    """Check an entity's text fields for PII.

    Scans: statement, name, and any string values in properties.
    """
    findings: list[dict[str, Any]] = []

    for field_name in ("statement", "name"):
        text = getattr(entity, field_name, "")
        if text:
            for f in detect_pii(text):
                f["field"] = field_name
                findings.append(f)

    for key, value in entity.properties.items():
        if isinstance(value, str) and value:
            for f in detect_pii(value):
                f["field"] = f"properties.{key}"
                findings.append(f)

    return findings
