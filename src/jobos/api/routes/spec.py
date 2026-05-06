"""JobOS.ai — Pipeline Orchestrator API Routes.

Manages the SSOT handoff spec and provides pipeline stage execution endpoints.
The spec file lives at spec/jobos-ai-spec.json relative to project root.

Endpoints:
  GET  /api/spec                    — Load current handoff spec
  PUT  /api/spec                    — Save updated spec (full replace)
  PATCH /api/spec/questions/{id}    — Update a single open question (e.g., add decision)
  POST /api/spec/run/{stage_id}     — Trigger a pipeline stage
  GET  /api/spec/evaluate           — Run evaluation harness and return scores
  GET  /api/spec/tasks              — List engineering tasks by status
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# Resolve spec path relative to this file: src/jobos/api/routes/spec.py → project root / spec /
_SPEC_PATH = Path(__file__).parents[4] / "spec" / "jobos-ai-spec.json"


def _load_spec() -> dict[str, Any]:
    if not _SPEC_PATH.exists():
        raise HTTPException(404, f"Spec file not found: {_SPEC_PATH}")
    return json.loads(_SPEC_PATH.read_text(encoding="utf-8"))


def _save_spec(spec: dict[str, Any]) -> None:
    _SPEC_PATH.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@router.get("/spec")
def get_spec() -> dict[str, Any]:
    """Return the full handoff spec JSON."""
    return _load_spec()


class SpecPatch(BaseModel):
    spec: dict[str, Any]


@router.put("/spec")
def update_spec(body: SpecPatch) -> dict[str, Any]:
    """Replace the full spec (used by orchestrator after model outputs)."""
    spec = body.spec
    # Stamp updated time
    if "metadata" in spec:
        spec["metadata"]["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_spec(spec)
    return {"status": "saved", "updated": spec.get("metadata", {}).get("updated")}


class QuestionDecision(BaseModel):
    decision: str
    decided_by: str = "human"
    notes: str = ""


@router.patch("/spec/questions/{question_id}")
def decide_question(question_id: str, body: QuestionDecision) -> dict[str, Any]:
    """Record a human decision on an open question."""
    spec = _load_spec()
    questions = spec.get("open_questions", [])
    for q in questions:
        if q["id"] == question_id:
            q["decision"] = body.decision
            q["status"] = "resolved"
            q["decided_by"] = body.decided_by
            q["resolved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if body.notes:
                q["notes"] = body.notes
            _save_spec(spec)
            return {"status": "resolved", "question": q}
    raise HTTPException(404, f"Question {question_id} not found")


class StageRunRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


@router.post("/spec/run/{stage_id}")
def run_stage(stage_id: str, body: StageRunRequest) -> dict[str, Any]:
    """Trigger a pipeline stage.

    For 'engineering' and 'evaluation' stages: runs pytest and returns results.
    For 'research', 'synthesis', 'decision': marks stage as triggered and
    returns the context package for the relevant model call.
    """
    spec = _load_spec()
    stages = spec.get("pipeline", {}).get("stages", [])
    stage = next((s for s in stages if s["id"] == stage_id), None)
    if stage is None:
        raise HTTPException(404, f"Stage '{stage_id}' not found")

    if stage_id == "evaluation":
        result = _run_evaluation(spec, body.dry_run)
    elif stage_id == "engineering":
        result = _run_tests(body.dry_run)
    else:
        # Return context package for human/model consumption
        result = _build_context_package(spec, stage_id)

    # Update stage in spec
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stage["last_run"] = now
    stage["last_run_result"] = result.get("summary", result)
    if result.get("status") == "green":
        stage["status"] = "done"
    _save_spec(spec)

    return {"stage": stage_id, "ran_at": now, "result": result}


@router.get("/spec/evaluate")
def evaluate_spec() -> dict[str, Any]:
    """Run the full evaluation harness and return a scoring report."""
    spec = _load_spec()
    return _run_evaluation(spec, dry_run=False)


@router.get("/spec/tasks")
def get_tasks(status: str | None = None) -> dict[str, Any]:
    """List engineering tasks, optionally filtered by status."""
    spec = _load_spec()
    tasks = spec.get("engineering_tasks", [])
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    by_status: dict[str, list] = {}
    for t in spec.get("engineering_tasks", []):
        s = t.get("status", "unknown")
        by_status.setdefault(s, []).append(t)
    return {
        "total": len(tasks),
        "filtered": tasks,
        "by_status": by_status,
    }


@router.get("/spec/context-package/{stage_id}")
def get_context_package(stage_id: str) -> dict[str, Any]:
    """Return the context package for a given stage — ready to pass to Gemini or Claude."""
    spec = _load_spec()
    stages = spec.get("pipeline", {}).get("stages", [])
    stage = next((s for s in stages if s["id"] == stage_id), None)
    if stage is None:
        raise HTTPException(404, f"Stage '{stage_id}' not found")
    return _build_context_package(spec, stage_id)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _run_tests(dry_run: bool) -> dict[str, Any]:
    """Run pytest on the tests/unit/ directory."""
    if dry_run:
        return {"status": "dry_run", "summary": "Tests not run (dry_run=true)"}

    project_root = _SPEC_PATH.parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/", "-q", "--tb=no"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=120,
    )
    lines = (result.stdout + result.stderr).strip().split("\n")
    summary_line = next((l for l in reversed(lines) if "passed" in l or "failed" in l or "error" in l), "")

    passed = 0
    failed = 0
    for part in summary_line.split(","):
        part = part.strip()
        if "passed" in part:
            try:
                passed = int(part.split()[0])
            except ValueError:
                pass
        if "failed" in part:
            try:
                failed = int(part.split()[0])
            except ValueError:
                pass

    status = "green" if failed == 0 and passed > 0 else "red"
    return {
        "status": status,
        "passed": passed,
        "failed": failed,
        "summary_line": summary_line,
        "return_code": result.returncode,
    }


def _run_evaluation(spec: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Run the evaluation plan checks from the spec."""
    from jobos.kernel.t3_dsl import parse_constraint, validate_statement

    if dry_run:
        return {"status": "dry_run", "checks": []}

    checks = []
    plan = spec.get("evaluation_plan", {}).get("tests", [])
    schema_dir = _SPEC_PATH.parents[1] / "src" / "jobos" / "schemas"

    # EVAL-01: All DSL examples in spec parse
    dsl_examples = spec.get("agent_catalog", {}).get("t3_dsl_examples", [])
    dsl_pass = sum(1 for s in dsl_examples if parse_constraint(s) is not None)
    checks.append({
        "id": "EVAL-01",
        "name": "dsl_grammar_check",
        "passed": dsl_pass,
        "total": len(dsl_examples),
        "pct": round(100 * dsl_pass / max(len(dsl_examples), 1), 1),
        "status": "pass" if dsl_pass == len(dsl_examples) else "fail",
    })

    # EVAL-02: Crosswalk coverage — every T-2 has a mapping or no_equivalent
    t2_ids = {e["id"] for e in spec.get("managerial_catalog", {}).get("t2", [])}
    mapped = {c["managerial"] for c in spec.get("crosswalk", [])}
    coverage = len(mapped & t2_ids)
    checks.append({
        "id": "EVAL-02",
        "name": "crosswalk_roundtrip",
        "covered": coverage,
        "total": len(t2_ids),
        "pct": round(100 * coverage / max(len(t2_ids), 1), 1),
        "status": "pass" if coverage >= len(t2_ids) else "partial",
        "note": "Partial is acceptable while research phase is in_progress",
    })

    # EVAL-05: Run unit tests
    test_result = _run_tests(dry_run=False)
    checks.append({
        "id": "EVAL-05",
        "name": "schema_unit_tests",
        "passed": test_result["passed"],
        "failed": test_result["failed"],
        "pct": 100.0 if test_result["failed"] == 0 else round(
            100 * test_result["passed"] / max(test_result["passed"] + test_result["failed"], 1), 1
        ),
        "status": "pass" if test_result["status"] == "green" else "fail",
    })

    # EVAL-06: T-3 DSL example coverage of enum variants
    from jobos.kernel.t3_dsl import TimeUnit, RateType
    all_units = set(u.value for u in TimeUnit)
    all_rates = set(r.value for r in RateType)
    seen_units: set[str] = set()
    seen_rates: set[str] = set()
    for stmt in dsl_examples:
        c = parse_constraint(stmt)
        if c is not None and hasattr(c, "unit"):
            seen_units.add(c.unit.value if hasattr(c.unit, "value") else c.unit)
        if c is not None and hasattr(c, "rate_type"):
            seen_rates.add(c.rate_type.value if hasattr(c.rate_type, "value") else c.rate_type)
    unit_cov = len(seen_units & all_units) / max(len(all_units), 1)
    rate_cov = len(seen_rates & all_rates) / max(len(all_rates), 1)
    checks.append({
        "id": "EVAL-06",
        "name": "t3_coverage",
        "units_covered": sorted(seen_units),
        "units_pct": round(unit_cov * 100, 1),
        "rates_covered": sorted(seen_rates),
        "rates_pct": round(rate_cov * 100, 1),
        "status": "pass" if unit_cov >= 0.5 and rate_cov >= 0.2 else "partial",
    })

    overall = "green" if all(c["status"] == "pass" for c in checks) else (
        "yellow" if all(c["status"] in ("pass", "partial") for c in checks) else "red"
    )
    return {
        "status": overall,
        "summary": {"total_checks": len(checks), "passed": sum(1 for c in checks if c["status"] == "pass")},
        "checks": checks,
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _build_context_package(spec: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """Build a compact context package for model consumption."""
    stage = next((s for s in spec.get("pipeline", {}).get("stages", []) if s["id"] == stage_id), {})
    return {
        "stage_id": stage_id,
        "stage_description": stage.get("description", ""),
        "spec_version": spec.get("metadata", {}).get("version"),
        "open_questions": [
            q for q in spec.get("open_questions", [])
            if q.get("stage") == stage_id and q.get("status") == "open"
        ],
        "acceptance_criteria": [
            ac for ac in spec.get("acceptance_criteria", [])
            if ac.get("stage") == stage_id
        ],
        "current_outputs": {
            "managerial_catalog": spec.get("managerial_catalog", {}),
            "agent_catalog": spec.get("agent_catalog", {}),
            "crosswalk": spec.get("crosswalk", []),
        },
        "evidence": spec.get("evidence", []),
        "engineering_tasks_pending": [
            t for t in spec.get("engineering_tasks", [])
            if t.get("status") in ("pending", "in_progress")
        ],
        "prompt_contract": (
            "Research: fill open_questions slots using evidence. Output valid JSON deltas to managerial_catalog and agent_catalog. "
            "Engineering: implement engineering_tasks with status=pending. Output code, schemas, tests. "
            "Both: respect acceptance_criteria as merge gates."
        ),
    }
