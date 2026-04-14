"""JobOS 4.0 — Baseline & Switch Event Service.

Captures metric baselines per scenario, records switch events,
and evaluates phase exit criteria (go / no_go / inconclusive).
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort

logger = logging.getLogger(__name__)


class BaselineService:
    """Captures baselines, records switches, evaluates phase exit."""

    def __init__(self, graph: GraphPort, db: RelationalPort) -> None:
        self._graph = graph
        self._db = db

    async def capture_baseline(
        self,
        scenario_id: str,
        captured_by: str = "system",
    ) -> dict[str, Any]:
        """Traverse Scenario → T1 → ... → T4 tree, snapshot current metrics.

        Returns a summary of all baseline snapshots captured.
        """
        scenario = await self._graph.get_entity(scenario_id)
        if not scenario or scenario.entity_type != EntityType.SCENARIO:
            raise ValueError(f"Scenario entity not found: {scenario_id}")

        # Find T1 via TARGETS edge
        t1_jobs = await self._graph.get_neighbors(
            scenario_id, edge_type="TARGETS", direction="outgoing"
        )

        snapshots: list[dict[str, Any]] = []
        visited: set[str] = set()

        async def traverse(job_id: str) -> None:
            if job_id in visited:
                return
            visited.add(job_id)

            # Get latest metrics for this job
            metrics_list = await self._db.get_job_metrics(job_id, limit=1)
            metrics: dict[str, float] = {}
            bounds: dict[str, Any] = {}
            if metrics_list:
                latest = metrics_list[0]
                for key in ("accuracy", "speed", "throughput"):
                    if latest.get(key) is not None:
                        metrics[key] = latest[key]
                bounds = latest.get("bounds", {})

            # Save baseline snapshot
            snap_id = await self._db.save_baseline_snapshot(
                scenario_id=scenario_id,
                job_id=job_id,
                metrics=metrics,
                bounds=bounds,
                captured_by=captured_by,
            )
            snapshots.append({
                "id": snap_id,
                "job_id": job_id,
                "metrics": metrics,
                "bounds": bounds,
            })

            # Traverse children via HIRES edges
            children = await self._graph.get_neighbors(
                job_id, edge_type="HIRES", direction="outgoing"
            )
            for child in children:
                if child.entity_type == EntityType.JOB:
                    await traverse(child.id)

        for t1 in t1_jobs:
            await traverse(t1.id)

        logger.info(
            "Captured %d baseline snapshots for scenario %s",
            len(snapshots), scenario_id,
        )
        return {
            "scenario_id": scenario_id,
            "snapshots": snapshots,
            "total_jobs": len(snapshots),
        }

    async def get_summary(
        self,
        scenario_id: str,
    ) -> dict[str, Any]:
        """Compare current metrics vs baseline deltas for all jobs in scenario."""
        scenario = await self._graph.get_entity(scenario_id)
        if not scenario or scenario.entity_type != EntityType.SCENARIO:
            raise ValueError(f"Scenario entity not found: {scenario_id}")

        t1_jobs = await self._graph.get_neighbors(
            scenario_id, edge_type="TARGETS", direction="outgoing"
        )

        deltas: list[dict[str, Any]] = []
        visited: set[str] = set()

        async def traverse(job_id: str) -> None:
            if job_id in visited:
                return
            visited.add(job_id)

            baseline = await self._db.get_baseline_snapshot(scenario_id, job_id)
            current_list = await self._db.get_job_metrics(job_id, limit=1)

            if baseline and current_list:
                current = current_list[0]
                job_deltas: dict[str, float] = {}
                for key in ("accuracy", "speed", "throughput"):
                    base_val = baseline["metrics"].get(key)
                    curr_val = current.get(key)
                    if base_val is not None and curr_val is not None:
                        job_deltas[key] = curr_val - base_val
                deltas.append({
                    "job_id": job_id,
                    "baseline": baseline["metrics"],
                    "current": {k: current.get(k) for k in ("accuracy", "speed", "throughput")
                                if current.get(k) is not None},
                    "deltas": job_deltas,
                })

            children = await self._graph.get_neighbors(
                job_id, edge_type="HIRES", direction="outgoing"
            )
            for child in children:
                if child.entity_type == EntityType.JOB:
                    await traverse(child.id)

        for t1 in t1_jobs:
            await traverse(t1.id)

        return {
            "scenario_id": scenario_id,
            "comparisons": deltas,
            "total_compared": len(deltas),
        }

    async def record_switch_event(
        self,
        scenario_id: str,
        job_id: str,
        trigger_metric: str,
        trigger_value: float,
        trigger_bound: str,
        action: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Record a switch event triggered by a metric breach."""
        event_id = await self._db.save_switch_event(
            scenario_id=scenario_id,
            job_id=job_id,
            trigger_metric=trigger_metric,
            trigger_value=trigger_value,
            trigger_bound=trigger_bound,
            action=action,
            reason=reason,
        )
        logger.info(
            "Switch event %s recorded for scenario %s job %s: %s=%s (%s)",
            event_id, scenario_id, job_id, trigger_metric, trigger_value, action,
        )
        return {
            "id": event_id,
            "scenario_id": scenario_id,
            "job_id": job_id,
            "trigger_metric": trigger_metric,
            "action": action,
        }

    async def get_switch_events(
        self,
        scenario_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get switch events for a scenario."""
        return await self._db.get_switch_events(scenario_id, limit=limit)

    async def evaluate_phase(
        self,
        scenario_id: str,
    ) -> dict[str, Any]:
        """Evaluate phase exit criteria for a scenario.

        Returns go / no_go / inconclusive verdict with reasoning.

        Logic:
        - If exit_criteria is empty → inconclusive
        - If there are switch events with action='fire' → the system responded correctly
        - If there are no switch events but metrics show breaches → no_go
        - If baselines exist and deltas show improvement → go
        """
        scenario = await self._graph.get_entity(scenario_id)
        if not scenario or scenario.entity_type != EntityType.SCENARIO:
            raise ValueError(f"Scenario entity not found: {scenario_id}")

        exit_criteria = scenario.properties.get("exit_criteria", "")
        switch_events = await self._db.get_switch_events(scenario_id)
        summary = await self.get_summary(scenario_id)
        comparisons = summary.get("comparisons", [])

        reasons: list[str] = []

        if not exit_criteria:
            return {
                "scenario_id": scenario_id,
                "verdict": "inconclusive",
                "reasons": ["No exit criteria defined for this scenario."],
                "switch_events_count": len(switch_events),
                "comparisons_count": len(comparisons),
            }

        # Check for fire events (system correctly triggered switches)
        fire_events = [e for e in switch_events if e.get("action") == "fire"]
        if fire_events:
            reasons.append(
                f"{len(fire_events)} switch event(s) triggered — "
                f"system correctly detected and responded to breaches."
            )

        # Check metric deltas
        improving = 0
        degrading = 0
        for comp in comparisons:
            for metric, delta in comp.get("deltas", {}).items():
                if delta > 0:
                    improving += 1
                elif delta < 0:
                    degrading += 1

        if improving > 0:
            reasons.append(f"{improving} metric(s) showing improvement.")
        if degrading > 0:
            reasons.append(f"{degrading} metric(s) showing degradation.")

        # Determine verdict
        if not comparisons and not switch_events:
            verdict = "inconclusive"
            reasons.append("No metrics data or switch events to evaluate.")
        elif fire_events and degrading == 0:
            verdict = "go"
            reasons.append("Switches triggered correctly and no ongoing degradation.")
        elif degrading > improving:
            verdict = "no_go"
            reasons.append("More metrics degrading than improving.")
        elif improving >= degrading and (fire_events or improving > 0):
            verdict = "go"
        else:
            verdict = "inconclusive"

        return {
            "scenario_id": scenario_id,
            "verdict": verdict,
            "reasons": reasons,
            "switch_events_count": len(switch_events),
            "comparisons_count": len(comparisons),
        }
