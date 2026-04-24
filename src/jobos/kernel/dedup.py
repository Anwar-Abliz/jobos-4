"""JobOS 4.0 — Entity De-duplication.

Uses string similarity (SequenceMatcher) to detect near-duplicate
entities by their statement text.  Phase 2 would upgrade to
embedding-based cosine similarity.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from jobos.kernel.entity import EntityBase


def similarity(a: str, b: str) -> float:
    """Compute normalized string similarity between two texts."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_duplicates(
    statements: list[str],
    threshold: float = 0.85,
) -> list[tuple[int, int, float]]:
    """Find pairs of near-duplicate statements.

    Returns list of (index_a, index_b, similarity_score) for pairs
    above the threshold.
    """
    pairs: list[tuple[int, int, float]] = []
    for i in range(len(statements)):
        for j in range(i + 1, len(statements)):
            score = similarity(statements[i], statements[j])
            if score >= threshold:
                pairs.append((i, j, round(score, 4)))
    return pairs


def deduplicate_entities(
    entities: list[EntityBase],
    threshold: float = 0.85,
) -> tuple[list[EntityBase], list[tuple[str, str, float]]]:
    """Remove near-duplicate entities based on statement similarity.

    Returns:
        (unique_entities, merged_pairs) where merged_pairs is a list
        of (kept_id, removed_id, similarity) tuples.
    """
    if not entities:
        return [], []

    statements = [e.statement for e in entities]
    dup_pairs = find_duplicates(statements, threshold)

    removed_indices: set[int] = set()
    merged: list[tuple[str, str, float]] = []

    for idx_a, idx_b, score in dup_pairs:
        if idx_b not in removed_indices:
            removed_indices.add(idx_b)
            merged.append((
                entities[idx_a].id,
                entities[idx_b].id,
                score,
            ))

    unique = [e for i, e in enumerate(entities) if i not in removed_indices]
    return unique, merged
