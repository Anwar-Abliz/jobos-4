"""JobOS 4.0 — Experience Space (Dimension A).

Dimension A: Experience Space represents the identity, emotional, and social
layer of Jobs. These are NOT functional outcomes — they capture how the executor
or customer WANTS TO FEEL after the job is done.

Experience is an orthogonal dimension, not a tier. The four tiers (T1–T4) are
all functional; Experience nodes sit alongside them as Dimension A data.

Linguistic marker: Experience statements start with "To Be" or "Feel" (Axiom 5).
Neo4j label: :Experience (applied alongside :Entity for these nodes).
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ─── Experience Categories (Dimension A) ────────────────

class ExperienceCategory(str, Enum):
    """Categories for Dimension A Experience nodes.

    These are NOT tier sub-categories — they classify the orthogonal
    experience dimension that accompanies functional jobs.
    """
    CONFIDENCE = "confidence"           # Feel confident, in control
    RECOGNITION = "recognition"         # Be seen as competent/valuable
    GROWTH = "growth"                   # Feel like I'm developing
    CONNECTION = "connection"           # Feel connected to team/purpose
    RELIEF = "relief"                   # Avoid anxiety, embarrassment, overload


# ─── Experience Node Model ───────────────────────────────

class ExperienceProperties(BaseModel):
    """Properties for an Experience Space node (:Entity:Experience).

    Experience nodes represent the desired felt states that accompany
    a functional job — the emotional and identity dimension.

    identity_phrases:  Free-form phrases about identity ("be seen as...", "known for...")
    emotion_phrases:   Emotion descriptors ("confident", "relieved", "proud")
    provenance:        Source of this experience data (interview, survey, observation)
    job_id:            The functional job this experience is associated with.
    version:           Version number for experience marker history.
    source:            Origin of the markers ("llm", "manual", "override").
    confidence:        LLM confidence in the generated markers (0.0–1.0).
    role_archetype:    Target persona archetype (e.g. "linguist", "manager").
    """
    identity_phrases: list[str] = Field(default_factory=list)
    emotion_phrases: list[str] = Field(default_factory=list)
    provenance: str = ""
    job_id: str = ""
    version: int = 1
    source: Literal["manual", "llm", "override"] = "manual"
    confidence: float = 0.0
    role_archetype: str = ""


# ─── Linguistic Validator ────────────────────────────────

# Matches "feel" or "to be" as complete words at the start of the string.
# Prevents "feeling" or "tolerable" etc. from matching.
_EXPERIENTIAL_RE = re.compile(
    r"^(to\s+be\b|feel\b)",
    re.IGNORECASE,
)


def validate_experiential_statement(text: str) -> bool:
    """Axiom 5 (Dimension A): Return True if text starts with 'To Be' or 'Feel'.

    Uses word-boundary matching: "feeling" does NOT match "feel" since
    the "feel" must be followed by a word boundary (space, end of string, etc.).
    Case-insensitive. Leading whitespace is stripped.

    Examples:
        validate_experiential_statement("To Be seen as a leader")  → True
        validate_experiential_statement("Feel confident in my work")  → True
        validate_experiential_statement("feel connected to purpose")  → True
        validate_experiential_statement("feeling good")  → False ("feeling" ≠ "feel")
        validate_experiential_statement("Define success criteria")  → False (functional)
        validate_experiential_statement("")  → False
    """
    if not text or not text.strip():
        return False
    return bool(_EXPERIENTIAL_RE.match(text.strip()))


def extract_emotion_keywords(text: str) -> list[str]:
    """Extract candidate emotion keywords from an experiential statement.

    Strips the 'To Be' / 'Feel' prefix and tokenises the remainder.
    Returns non-empty lowercase alpha tokens as emotion candidates.

    Phase 1: Simple tokenisation. Phase 2: NLP NER with emotion taxonomy.
    """
    if not text or not text.strip():
        return []

    stripped = text.strip()
    m = _EXPERIENTIAL_RE.match(stripped)
    if not m:
        # Not an experiential statement — return empty
        return []

    remainder = stripped[m.end():].strip()
    tokens = re.findall(r"[a-zA-Z]+", remainder)
    return [t.lower() for t in tokens if len(t) > 2]
