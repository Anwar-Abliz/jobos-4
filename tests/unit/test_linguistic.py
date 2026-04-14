"""Tests for Axiom 5 Linguistic Validator — Experiential Branch.

Focuses on:
- validate_experiential_statement (experience.py)
- Axiom 5 experiential path in axioms.py
- Edge cases: casing, punctuation, leading whitespace
- Parity note: TypeScript validators.ts mirrors these rules client-side.
"""
from __future__ import annotations

import pytest

from jobos.kernel.axioms import AxiomViolation, JobOSAxioms
from jobos.kernel.experience import (
    ExperienceProperties,
    extract_emotion_keywords,
    validate_experiential_statement,
)


# ─── validate_experiential_statement ────────────────────

class TestValidateExperientialStatement:
    def test_to_be_lowercase(self):
        assert validate_experiential_statement("to be a trusted partner") is True

    def test_to_be_titlecase(self):
        assert validate_experiential_statement("To Be seen as competent") is True

    def test_to_be_uppercase(self):
        assert validate_experiential_statement("TO BE confident") is True

    def test_feel_lowercase(self):
        assert validate_experiential_statement("feel connected to the team") is True

    def test_feel_titlecase(self):
        assert validate_experiential_statement("Feel relieved by the outcome") is True

    def test_feel_uppercase(self):
        assert validate_experiential_statement("FEEL proud of the delivery") is True

    def test_leading_whitespace_stripped(self):
        assert validate_experiential_statement("   Feel confident   ") is True
        assert validate_experiential_statement("   To Be seen   ") is True

    def test_empty_string_returns_false(self):
        assert validate_experiential_statement("") is False

    def test_whitespace_only_returns_false(self):
        assert validate_experiential_statement("   ") is False

    def test_functional_verb_returns_false(self):
        assert validate_experiential_statement("Define confidence metrics") is False
        assert validate_experiential_statement("Build a pipeline") is False

    def test_passive_returns_false(self):
        assert validate_experiential_statement("It would be nice to feel calm") is False

    def test_to_be_without_object_still_valid(self):
        # "To Be" alone is technically valid syntax (though semantically incomplete)
        assert validate_experiential_statement("To Be") is True

    def test_feel_without_object_still_valid(self):
        assert validate_experiential_statement("Feel") is True

    def test_to_without_be_returns_false(self):
        # "To build" is functional, not experiential
        assert validate_experiential_statement("To build faster") is False

    def test_feeling_prefix_returns_false(self):
        # "feeling" is not "feel" — must be exact word
        assert validate_experiential_statement("feeling confident") is False


# ─── Axiom 5 experiential=True path ─────────────────────

class TestAxiom5Experiential:
    def test_to_be_passes_axiom_5(self):
        assert JobOSAxioms.validate_linguistic_structure(
            "To Be the most reliable vendor", experiential=True
        ) is True

    def test_feel_passes_axiom_5(self):
        assert JobOSAxioms.validate_linguistic_structure(
            "Feel empowered to make decisions", experiential=True
        ) is True

    def test_action_verb_rejected_as_experiential(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("Build trust", experiential=True)
        assert exc_info.value.axiom == 5

    def test_empty_experiential_raises(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("", experiential=True)
        assert exc_info.value.axiom == 5

    def test_passive_phrase_rejected_as_experiential(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure(
                "Being seen as trustworthy is important", experiential=True
            )
        assert exc_info.value.axiom == 5

    def test_functional_path_unchanged_by_new_code(self):
        """Ensure functional path still works after the experiential branch was added."""
        assert JobOSAxioms.validate_linguistic_structure("Define the roadmap") is True
        assert JobOSAxioms.validate_linguistic_structure(
            "Define the roadmap", experiential=False
        ) is True

    def test_error_message_mentions_prefixes(self):
        with pytest.raises(AxiomViolation) as exc_info:
            JobOSAxioms.validate_linguistic_structure("Identify impact", experiential=True)
        desc = exc_info.value.description
        assert "To Be" in desc or "Feel" in desc


# ─── extract_emotion_keywords ────────────────────────────

class TestExtractEmotionKeywords:
    def test_to_be_extracts_keywords(self):
        result = extract_emotion_keywords("To Be seen as a trusted and reliable partner")
        assert "seen" in result
        assert "trusted" in result
        assert "reliable" in result
        assert "partner" in result

    def test_feel_extracts_keywords(self):
        result = extract_emotion_keywords("Feel confident and in control")
        assert "confident" in result
        assert "control" in result

    def test_short_words_excluded(self):
        result = extract_emotion_keywords("To Be a true expert")
        # "a" and similar short words (<=2 chars) should be excluded
        assert "a" not in result

    def test_empty_returns_empty(self):
        assert extract_emotion_keywords("") == []

    def test_non_experiential_returns_empty(self):
        # "Define" is not an experiential prefix — returns empty
        assert extract_emotion_keywords("Define the success criteria") == []

    def test_case_normalized_to_lowercase(self):
        result = extract_emotion_keywords("To Be CONFIDENT in delivery")
        assert "confident" in result


# ─── ExperienceProperties model ─────────────────────────

class TestExperienceProperties:
    def test_default_fields_are_empty(self):
        ep = ExperienceProperties()
        assert ep.identity_phrases == []
        assert ep.emotion_phrases == []
        assert ep.provenance == ""
        assert ep.job_id == ""

    def test_can_set_all_fields(self):
        ep = ExperienceProperties(
            identity_phrases=["trusted advisor", "reliable partner"],
            emotion_phrases=["confident", "empowered"],
            provenance="customer_interview_2024",
            job_id="job_abc123",
        )
        assert len(ep.identity_phrases) == 2
        assert "confident" in ep.emotion_phrases
        assert ep.provenance == "customer_interview_2024"
        assert ep.job_id == "job_abc123"


# ─── Parity note (TypeScript mirror) ────────────────────

class TestTypeScriptParityNote:
    """
    These tests document the exact parity expected between Python validators
    and the TypeScript validators.ts client-side implementation.

    The TypeScript `validateExperientialStatement` function should return
    the same boolean as `validate_experiential_statement` for these inputs.
    """

    PARITY_CASES = [
        # (statement, expected_python, typescript_parity_expected)
        ("To Be seen as a leader", True, True),
        ("Feel confident in my work", True, True),
        ("feel connected", True, True),
        ("TO BE present", True, True),
        ("Define metrics", False, False),
        ("Build something", False, False),
        ("", False, False),
        ("   ", False, False),
        ("feeling good", False, False),
        ("to build trust", False, False),
    ]

    @pytest.mark.parametrize("statement,expected,_ts_note", PARITY_CASES)
    def test_python_parity_cases(self, statement, expected, _ts_note):
        assert validate_experiential_statement(statement) == expected
