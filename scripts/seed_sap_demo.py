"""Seed a realistic SAP demo into the JobOS 4.0 system.

Creates:
- 1 company structure (Global Corp org hierarchy)
- 3 SAP processes (O2C, P2P, R2R) with steps and objects
- 5 governance policies (access, data, process, compliance, ai_usage)
- 2 ODI surveys with template-generated outcomes
- Sample decision traces linked to process entities
- Context snapshots with varying freshness

Usage:
    python scripts/seed_sap_demo.py

Requires running Neo4j and PostgreSQL instances. Configure via .env.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("seed_sap_demo")


async def main() -> None:
    """Connect to databases and seed the full SAP demo dataset."""
    # ── Imports (deferred so .env loads first) ───────────────
    from jobos.config import get_settings
    from jobos.adapters.neo4j.connection import Neo4jConnection
    from jobos.adapters.neo4j.entity_repo import Neo4jEntityRepo
    from jobos.adapters.postgres.connection import PostgresConnection
    from jobos.adapters.postgres.models import Base
    from jobos.adapters.postgres.metric_repo import PostgresRepo
    from jobos.adapters.sap_simulation import (
        ALL_TEMPLATES,
        DEFAULT_ORG_STRUCTURE,
    )
    from jobos.adapters.sap_simulation.ingestion_adapter import SAPIngestionAdapter
    from jobos.adapters.sap_simulation.data_generator import (
        generate_process_metrics,
    )
    from jobos.kernel.entity import EntityBase, EntityType, MetricReading, _uid
    from jobos.services.governance_service import GovernanceService
    from jobos.services.decision_service import DecisionService
    from jobos.services.survey_service import SurveyService
    from jobos.services.context_service import ContextService

    # ── Load configuration ───────────────────────────────────
    settings = get_settings()
    logger.info("JobOS SAP Demo Seeder starting...")

    # ── Connect Neo4j ────────────────────────────────────────
    neo4j_conn = Neo4jConnection(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
    )
    await neo4j_conn.connect()
    logger.info("Neo4j connected.")

    # ── Connect PostgreSQL ───────────────────────────────────
    pg_conn = PostgresConnection(settings.postgres.uri)
    await pg_conn.connect()
    logger.info("PostgreSQL connected.")

    # Ensure tables exist
    async with pg_conn.engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables ensured.")

    try:
        # Build repositories and services
        graph = Neo4jEntityRepo(neo4j_conn)
        await graph.ensure_schema()
        logger.info("Neo4j schema ensured.")

        db = PostgresRepo(pg_conn)
        sap_adapter = SAPIngestionAdapter(graph)
        governance_svc = GovernanceService(graph)
        decision_svc = DecisionService(graph, db)
        survey_svc = SurveyService(graph, db)
        context_svc = ContextService(graph, db)

        # Track created IDs for cross-linking
        process_ids: dict[str, str] = {}
        policy_ids: list[str] = []
        survey_ids: list[str] = []

        # ═══════════════════════════════════════════════════════
        #  1. ORG STRUCTURE
        # ═══════════════════════════════════════════════════════
        logger.info("--- Seeding org structure ---")
        company_id = await sap_adapter.ingest_org_structure(DEFAULT_ORG_STRUCTURE)
        logger.info("Company entity created: %s (Global Corp)", company_id)

        # ═══════════════════════════════════════════════════════
        #  2. SAP PROCESSES (O2C, P2P, R2R)
        # ═══════════════════════════════════════════════════════
        logger.info("--- Seeding SAP processes ---")
        for short_name, template in ALL_TEMPLATES.items():
            process_id = await sap_adapter.ingest_process(template)
            process_ids[short_name] = process_id

            # Link process to company org unit
            await graph.create_edge(process_id, company_id, "BELONGS_TO")

            # Generate and store sample metrics in PostgreSQL
            metrics_data = generate_process_metrics(template)
            for step_name, step_metrics in metrics_data["steps"].items():
                for kpi_name, kpi_value in step_metrics.items():
                    reading = MetricReading(
                        entity_id=process_id,
                        metric_id=f"{short_name}:{step_name}:{kpi_name}",
                        value=kpi_value,
                        unit="",
                        source="sap_simulation",
                        confidence=0.95,
                    )
                    await db.save_metric_reading(reading)

            logger.info(
                "Process '%s' created: %s (%d steps, linked to company)",
                template["name"],
                process_id,
                len(template.get("steps", [])),
            )

        # ═══════════════════════════════════════════════════════
        #  3. GOVERNANCE POLICIES
        # ═══════════════════════════════════════════════════════
        logger.info("--- Seeding governance policies ---")

        policy_definitions: list[dict[str, Any]] = [
            {
                "name": "SAP Access Control Policy",
                "policy_type": "access",
                "enforcement": "blocking",
                "owner": "IT Security",
                "rules": [
                    {
                        "rule_id": "AC-001",
                        "condition": "delete",
                        "action": "deny",
                        "scope": {
                            "entity_types": ["sap_process", "sap_org_unit"],
                            "org_units": [],
                            "sap_modules": [],
                        },
                        "priority": 10,
                    },
                    {
                        "rule_id": "AC-002",
                        "condition": "approve",
                        "action": "require_approval",
                        "scope": {
                            "entity_types": ["sap_transaction"],
                            "org_units": [],
                            "sap_modules": ["FI"],
                        },
                        "priority": 5,
                    },
                ],
            },
            {
                "name": "Data Quality Governance Policy",
                "policy_type": "data",
                "enforcement": "auditing",
                "owner": "Data Office",
                "rules": [
                    {
                        "rule_id": "DQ-001",
                        "condition": "create",
                        "action": "log",
                        "scope": {
                            "entity_types": ["sap_object"],
                            "org_units": [],
                            "sap_modules": [],
                        },
                        "priority": 3,
                    },
                ],
            },
            {
                "name": "Process Change Control Policy",
                "policy_type": "process",
                "enforcement": "blocking",
                "owner": "Process Excellence",
                "rules": [
                    {
                        "rule_id": "PC-001",
                        "condition": "modify",
                        "action": "require_approval",
                        "scope": {
                            "entity_types": ["sap_process"],
                            "org_units": [],
                            "sap_modules": ["SD", "MM", "FI"],
                        },
                        "priority": 8,
                    },
                ],
            },
            {
                "name": "Regulatory Compliance Policy",
                "policy_type": "compliance",
                "enforcement": "blocking",
                "owner": "Compliance Office",
                "rules": [
                    {
                        "rule_id": "RC-001",
                        "condition": "delete",
                        "action": "deny",
                        "scope": {
                            "entity_types": [
                                "sap_process", "sap_transaction",
                                "sap_object", "decision",
                            ],
                            "org_units": [],
                            "sap_modules": [],
                        },
                        "priority": 20,
                    },
                    {
                        "rule_id": "RC-002",
                        "condition": "create",
                        "action": "log",
                        "scope": {
                            "entity_types": ["decision"],
                            "org_units": [],
                            "sap_modules": [],
                        },
                        "priority": 15,
                    },
                ],
            },
            {
                "name": "AI Usage Governance Policy",
                "policy_type": "ai_usage",
                "enforcement": "advisory",
                "owner": "AI Ethics Board",
                "rules": [
                    {
                        "rule_id": "AI-001",
                        "condition": "approve",
                        "action": "require_approval",
                        "scope": {
                            "entity_types": ["decision"],
                            "org_units": [],
                            "sap_modules": [],
                        },
                        "priority": 12,
                    },
                ],
            },
        ]

        for pdef in policy_definitions:
            policy = await governance_svc.create_policy(
                name=pdef["name"],
                policy_type=pdef["policy_type"],
                rules=pdef["rules"],
                enforcement=pdef["enforcement"],
                owner=pdef["owner"],
            )
            policy_ids.append(policy.id)

            # Link policies to all processes via GOVERNED_BY
            for pid in process_ids.values():
                await governance_svc.link_policy(pid, policy.id)

            logger.info(
                "Policy '%s' (%s) created: %s — %d rules, linked to %d processes",
                pdef["name"],
                pdef["policy_type"],
                policy.id,
                len(pdef["rules"]),
                len(process_ids),
            )

        # ═══════════════════════════════════════════════════════
        #  4. ODI SURVEYS (2 surveys, template-generated outcomes)
        # ═══════════════════════════════════════════════════════
        logger.info("--- Seeding ODI surveys ---")

        survey_definitions = [
            {
                "name": "O2C Customer Experience Survey",
                "process_key": "O2C",
            },
            {
                "name": "P2P Procurement Efficiency Survey",
                "process_key": "P2P",
            },
        ]

        for sdef in survey_definitions:
            process_id = process_ids[sdef["process_key"]]
            survey = await survey_svc.create_survey(
                name=sdef["name"],
                process_id=process_id,
            )
            survey_ids.append(survey.id)

            # Generate outcomes using template fallback (no LLM)
            outcomes = await survey_svc.generate_outcomes(
                survey_id=survey.id,
                process_id=process_id,
            )

            # Simulate survey responses (5 respondents per outcome)
            for outcome in outcomes:
                for respondent_idx in range(5):
                    importance = round(random.uniform(5.0, 10.0), 1)
                    satisfaction = round(random.uniform(2.0, 8.0), 1)
                    await survey_svc.submit_response(
                        survey_id=survey.id,
                        outcome_id=outcome.id,
                        session_id=f"demo-respondent-{respondent_idx:02d}",
                        importance=importance,
                        satisfaction=satisfaction,
                    )

            logger.info(
                "Survey '%s' created: %s — %d outcomes, 5 responses each",
                sdef["name"],
                survey.id,
                len(outcomes),
            )

        # ═══════════════════════════════════════════════════════
        #  5. DECISION TRACES
        # ═══════════════════════════════════════════════════════
        logger.info("--- Seeding decision traces ---")

        decision_definitions = [
            {
                "actor": "process-mining-agent",
                "action": "hire",
                "target_process": "O2C",
                "rationale": (
                    "Hired automated credit check module to reduce "
                    "manual credit blocks in O2C Approve Credit step. "
                    "VFE decreased from 0.72 to 0.41 after automation."
                ),
                "vfe_before": 0.72,
                "vfe_after": 0.41,
                "alternatives": [
                    {"name": "Rule-based credit scoring", "efe": 0.55},
                    {"name": "Manual review process", "efe": 0.68},
                    {"name": "ML credit risk model", "efe": 0.38},
                ],
            },
            {
                "actor": "o2c-controller",
                "action": "switch",
                "target_process": "O2C",
                "rationale": (
                    "Switched from manual invoice creation to automated "
                    "billing due to persistent pricing discrepancies. "
                    "Triggered by invoice_accuracy breach (0.89 < 0.98 lower bound)."
                ),
                "vfe_before": 0.65,
                "vfe_after": 0.28,
                "alternatives": [
                    {"name": "Enhanced manual checks", "efe": 0.52},
                    {"name": "Automated billing engine", "efe": 0.25},
                ],
            },
            {
                "actor": "procurement-optimizer",
                "action": "hire",
                "target_process": "P2P",
                "rationale": (
                    "Hired catalog-enforced requisition system to "
                    "eliminate maverick buying. Contract coverage "
                    "expected to improve from 0.72 to 0.92."
                ),
                "vfe_before": 0.58,
                "vfe_after": 0.31,
                "alternatives": [
                    {"name": "Vendor managed inventory", "efe": 0.42},
                    {"name": "Catalog enforcement module", "efe": 0.30},
                ],
            },
            {
                "actor": "finance-controller",
                "action": "approval",
                "target_process": "R2R",
                "rationale": (
                    "Approved automated intercompany reconciliation "
                    "to replace manual clearing. Reduces close cycle "
                    "from 12 days to 5 days."
                ),
                "vfe_before": 0.80,
                "vfe_after": 0.35,
                "alternatives": [
                    {"name": "Enhanced spreadsheet process", "efe": 0.70},
                    {"name": "Third-party reconciliation SaaS", "efe": 0.40},
                    {"name": "SAP ACDOCA real-time ledger", "efe": 0.33},
                ],
            },
        ]

        for ddef in decision_definitions:
            target_id = process_ids[ddef["target_process"]]
            trace = await decision_svc.record_decision(
                actor=ddef["actor"],
                action=ddef["action"],
                target_entity_id=target_id,
                rationale=ddef["rationale"],
                context_snapshot={
                    "process": ddef["target_process"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "triggered_by": "seed_sap_demo",
                },
                policies_evaluated=policy_ids[:3],
                alternatives=ddef["alternatives"],
                vfe_before=ddef["vfe_before"],
                vfe_after=ddef["vfe_after"],
            )
            logger.info(
                "Decision trace '%s' by '%s' on %s: %s (VFE %.2f -> %.2f)",
                ddef["action"],
                ddef["actor"],
                ddef["target_process"],
                trace.decision_id,
                ddef["vfe_before"],
                ddef["vfe_after"],
            )

        # ═══════════════════════════════════════════════════════
        #  6. CONTEXT SNAPSHOTS (varying freshness)
        # ═══════════════════════════════════════════════════════
        logger.info("--- Seeding context snapshots ---")

        freshness_configs = [
            {"label": "live", "age_hours": 0.5},
            {"label": "snapshot", "age_hours": 12},
            {"label": "stale", "age_hours": 72},
        ]

        for short_name, process_id in process_ids.items():
            # Each process gets one snapshot per freshness level
            for fc in freshness_configs:
                snapshot_data = {
                    "process_short_name": short_name,
                    "freshness": fc["label"],
                    "org_structure": {
                        "company_code": "1000",
                        "company_name": "Global Corp",
                    },
                    "kpis": generate_process_metrics(ALL_TEMPLATES[short_name]),
                    "simulated_age_hours": fc["age_hours"],
                    "captured_at": (
                        datetime.now(timezone.utc)
                        - timedelta(hours=fc["age_hours"])
                    ).isoformat(),
                }

                snapshot_id = await db.save_context_snapshot(
                    entity_id=process_id,
                    snapshot_data=snapshot_data,
                    source=f"sap_simulation_{fc['label']}",
                )
                logger.info(
                    "Context snapshot for %s (%s freshness): %s",
                    short_name,
                    fc["label"],
                    snapshot_id,
                )

        # ═══════════════════════════════════════════════════════
        #  SUMMARY
        # ═══════════════════════════════════════════════════════
        logger.info("=" * 60)
        logger.info("SAP Demo Seeding Complete!")
        logger.info("=" * 60)
        logger.info("  Company entity:  %s (Global Corp)", company_id)
        logger.info("  Processes:       %d", len(process_ids))
        for sn, pid in process_ids.items():
            logger.info("    %s: %s", sn, pid)
        logger.info("  Policies:        %d", len(policy_ids))
        for pid in policy_ids:
            logger.info("    %s", pid)
        logger.info("  Surveys:         %d", len(survey_ids))
        for sid in survey_ids:
            logger.info("    %s", sid)
        logger.info("  Decision traces: %d", len(decision_definitions))
        logger.info("  Context snapshots: %d", len(process_ids) * len(freshness_configs))
        logger.info("=" * 60)

    finally:
        await neo4j_conn.close()
        await pg_conn.close()
        logger.info("Database connections closed.")


if __name__ == "__main__":
    asyncio.run(main())
