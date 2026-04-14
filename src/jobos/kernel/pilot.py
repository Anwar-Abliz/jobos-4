"""JobOS 4.0 — Pilot Definition Models.

Pydantic models for parsing pilot definition files (YAML / JSON)
from the JTBD agent's pilot directory. These are domain-agnostic
input schemas that feed into PilotService for graph seeding.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PilotMetric(BaseModel):
    """A single Dimension B metric from a pilot definition."""
    name: str
    description: str = ""
    target: str = ""
    switch_trigger_threshold: str = ""


class PilotRisk(BaseModel):
    """A risk-mitigation pair from a pilot definition."""
    risk: str
    mitigation: str = ""


class PilotDefinition(BaseModel):
    """Parsed pilot definition, normalised from YAML or JSON input.

    Covers the common schema shared by both pilot file formats:
    metadata, job hierarchy (T1–T3), dimension B metrics,
    dimension A experience markers, hypothesis, and risks.
    """
    pilot_id: str
    segment: str
    status: str = "draft"

    tier_1_strategic: str = ""
    tier_2_core: str = ""
    tier3_steps: list[str] = Field(default_factory=list)

    dimension_b_metrics: list[PilotMetric] = Field(default_factory=list)
    dimension_a_config: dict[str, Any] = Field(default_factory=dict)

    hypothesis: str = ""
    exit_criteria: str = ""
    risks: list[PilotRisk] = Field(default_factory=list)

    data_sources: list[str] = Field(default_factory=list)
    connectors: list[str] = Field(default_factory=list)


def parse_pilot_file(path: str | Path) -> PilotDefinition:
    """Auto-detect YAML/JSON and parse a pilot definition file.

    Normalises the varying field layouts into a single PilotDefinition.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")

    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError("PyYAML is required to parse YAML pilot files") from exc
        raw: dict[str, Any] = yaml.safe_load(text) or {}
    else:
        raw = json.loads(text)

    return _normalize_raw(raw)


def _normalize_raw(raw: dict[str, Any]) -> PilotDefinition:
    """Convert raw dict (from YAML or JSON) into PilotDefinition."""
    meta = raw.get("metadata", {})

    # Job hierarchy
    hier = raw.get("job_hierarchy", {})

    # T3 steps — handle both list-of-dicts and dict-of-steps formats
    raw_t3 = raw.get("tier3_steps", [])
    t3_steps: list[str] = []
    if isinstance(raw_t3, list):
        for item in raw_t3:
            if isinstance(item, dict):
                # e.g. {"step_1": "Define localization scope..."}
                for v in item.values():
                    t3_steps.append(str(v))
            else:
                t3_steps.append(str(item))
    elif isinstance(raw_t3, dict):
        # e.g. {"step_1": "...", "step_2": "..."}
        for key in sorted(raw_t3.keys()):
            t3_steps.append(str(raw_t3[key]))

    # Dimension B metrics
    raw_metrics = raw.get("dimension_b_metrics", {})
    dim_b: list[PilotMetric] = []
    if isinstance(raw_metrics, list):
        for m in raw_metrics:
            dim_b.append(PilotMetric(**m))
    # else: empty dict or other — leave empty

    # Dimension A
    raw_dim_a = raw.get("dimension_a_experience_markers", {})
    dim_a_config: dict[str, Any] = {}
    if isinstance(raw_dim_a, dict):
        for key, val in raw_dim_a.items():
            if isinstance(val, list) and val:
                dim_a_config[key] = val
            elif isinstance(val, str) and val.strip():
                dim_a_config[key] = [val]
            # Skip empty strings/lists

    # Risks
    raw_risks = raw.get("risks_and_mitigations", [])
    risks: list[PilotRisk] = []
    if isinstance(raw_risks, list):
        for r in raw_risks:
            if isinstance(r, dict):
                risks.append(PilotRisk(**r))

    return PilotDefinition(
        pilot_id=meta.get("pilot_id", ""),
        segment=meta.get("segment", ""),
        status=meta.get("status", "draft"),
        tier_1_strategic=hier.get("tier_1_strategic_why", ""),
        tier_2_core=hier.get("tier_2_core_what", ""),
        tier3_steps=t3_steps,
        dimension_b_metrics=dim_b,
        dimension_a_config=dim_a_config,
        hypothesis=raw.get("hypothesis_under_test", ""),
        exit_criteria=raw.get("exit_criteria_for_phase_1", ""),
        risks=risks,
        data_sources=raw.get("data_sources") or [],
        connectors=raw.get("connectors") or [],
    )
