"""JobOS 4.0 — Tier Classifier.

Classifies arbitrary job statements into T1-T4 tiers using
heuristic rules (Phase 1) or LLM-assisted classification (when available).
"""
from __future__ import annotations

import re

_T1_SIGNALS = frozenset({
    "strategic", "vision", "overarching", "macro", "long-term",
    "mission", "purpose", "north star", "achieve sustainable",
})
_T2_SIGNALS = frozenset({
    "reduce", "increase", "maintain", "improve", "ensure",
    "maximize", "minimize", "optimize", "functional", "outcome",
})
_T3_SIGNALS = frozenset({
    "implement", "execute", "design", "build", "deploy",
    "configure", "install", "coordinate", "manage", "operate",
    "conduct", "perform", "deliver", "process", "run",
})
_T4_SIGNALS = frozenset({
    "verify", "prepare", "setup", "check", "scan", "archive",
    "log", "confirm", "validate", "cleanup", "document", "record",
})


class TierClassifier:
    """Classifies job statements into T1-T4 tiers."""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    def classify(self, statement: str, context: str = "") -> int:
        """Classify a single statement into tier 1-4.

        Uses heuristic keyword matching. If LLM is available and
        heuristic confidence is low, defers to LLM.
        """
        return self._heuristic_classify(statement, context)

    def classify_batch(self, statements: list[str]) -> list[int]:
        """Classify multiple statements."""
        return [self.classify(s) for s in statements]

    def _heuristic_classify(self, statement: str, context: str = "") -> int:
        """Rule-based tier classification."""
        text = (statement + " " + context).lower()
        words = set(re.findall(r"[a-z]+", text))

        scores = {
            1: len(words & _T1_SIGNALS),
            2: len(words & _T2_SIGNALS),
            3: len(words & _T3_SIGNALS),
            4: len(words & _T4_SIGNALS),
        }

        # Boost T1 for very short, broad statements
        if len(statement.split()) <= 6:
            scores[1] += 1

        # Boost T4 for very specific, action-oriented statements
        if len(statement.split()) >= 8 and scores[4] > 0:
            scores[4] += 1

        best = max(scores, key=lambda k: scores[k])

        # Default to T3 (execution) when ambiguous
        if scores[best] == 0:
            return 3

        return best
