"""Parse ODI-style CSV files into structured job hierarchies.

Detects CSV files with tier-based columns (e.g. "tier 1", "tier 2", "tier 3", "tier 4")
and parses them directly into HierarchyJob + HierarchyEdge lists, bypassing LLM generation.
"""
from __future__ import annotations

import csv
import io
import logging
import re

from jobos.kernel.entity import _uid

logger = logging.getLogger(__name__)

# Column name patterns that indicate a tier hierarchy
TIER_PATTERNS = [
    re.compile(r"tier\s*1", re.IGNORECASE),
    re.compile(r"tier\s*2", re.IGNORECASE),
    re.compile(r"tier\s*3", re.IGNORECASE),
    re.compile(r"tier\s*4", re.IGNORECASE),
]

TIER_KEYS = ["T1_strategic", "T2_core", "T3_execution", "T4_micro"]


def detect_hierarchy_csv(text: str) -> bool:
    """Check if the CSV text has tier-based columns indicating a job hierarchy."""
    first_line = text.split("\n", 1)[0].lower()
    # Need at least tier 1 and tier 2 columns
    has_t1 = bool(TIER_PATTERNS[0].search(first_line))
    has_t2 = bool(TIER_PATTERNS[1].search(first_line))
    return has_t1 and has_t2


def parse_hierarchy_csv(text: str) -> dict | None:
    """Parse an ODI-style tier CSV into jobs and edges.

    Returns a dict with keys: domain, jobs, edges, summary
    or None if parsing fails.
    """
    # Strip BOM if present
    if text.startswith("\ufeff"):
        text = text[1:]

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return None

    # Detect which columns map to which tiers
    tier_col_indices: list[int | None] = [None, None, None, None]
    for col_idx, col_name in enumerate(header):
        col_lower = col_name.strip().lower()
        for tier_idx, pattern in enumerate(TIER_PATTERNS):
            if pattern.search(col_lower):
                tier_col_indices[tier_idx] = col_idx
                break

    if tier_col_indices[0] is None:
        return None  # No T1 column found

    # Parse rows — carry forward parent values across rows
    jobs: list[dict] = []
    edges: list[dict] = []
    job_id_map: dict[str, str] = {}  # statement -> id (dedup)

    # Track current parent at each tier level
    current_parents: list[str | None] = [None, None, None, None]
    domain = ""
    tier_counts = {"T1_strategic": 0, "T2_core": 0, "T3_execution": 0, "T4_micro": 0}

    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue

        for tier_idx in range(4):
            col_idx = tier_col_indices[tier_idx]
            if col_idx is None or col_idx >= len(row):
                continue

            cell = row[col_idx].strip()
            if not cell:
                continue

            # Clean up numbered prefixes like "1.Plan and preparation" or "1.1 ..."
            statement = re.sub(r"^[\d.]+\s*", "", cell).strip()
            if not statement:
                continue

            tier_key = TIER_KEYS[tier_idx]

            # Dedup: reuse existing job_id for same statement
            if statement in job_id_map:
                job_id = job_id_map[statement]
            else:
                job_id = _uid()
                job_id_map[statement] = job_id

                # Detect if T4 is a metric statement (starts with Minimize/Maximize/etc.)
                metrics_hint: list[str] = []
                category = ""
                if tier_idx == 3:
                    # T4 micro-jobs in ODI CSVs are often metric statements
                    metrics_hint = [statement]
                    category = "metric_outcome"

                jobs.append({
                    "id": job_id,
                    "tier": tier_key,
                    "statement": statement,
                    "category": category,
                    "rationale": "",
                    "metrics_hint": metrics_hint,
                    "executor_type": "HUMAN",
                })
                tier_counts[tier_key] += 1

            # Set this as current parent for lower tiers
            current_parents[tier_idx] = job_id
            # Clear children tiers' parents (new branch)
            for lower in range(tier_idx + 1, 4):
                current_parents[lower] = None

            # Create edge to parent tier
            if tier_idx > 0:
                parent_id = current_parents[tier_idx - 1]
                if parent_id and not any(
                    e["parent_id"] == parent_id and e["child_id"] == job_id
                    for e in edges
                ):
                    edges.append({
                        "parent_id": parent_id,
                        "child_id": job_id,
                        "strength": 1.0,
                    })

            # Use T1 statement as domain
            if tier_idx == 0 and not domain:
                domain = statement

    if not jobs:
        return None

    return {
        "domain": domain,
        "jobs": jobs,
        "edges": edges,
        "summary": {
            **tier_counts,
            "total_jobs": len(jobs),
        },
    }
