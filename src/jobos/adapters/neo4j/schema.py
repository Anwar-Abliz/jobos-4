"""JobOS 4.0 — Neo4j Schema Initialization.

Creates constraints and indexes for the unified Entity model.
All operations are idempotent (IF NOT EXISTS).
"""
from __future__ import annotations

import logging

from jobos.adapters.neo4j.connection import Neo4jConnection

logger = logging.getLogger(__name__)

# ─── Schema Statements ───────────────────────────────────

SCHEMA_STATEMENTS: list[str] = [
    # Uniqueness constraint on Entity.id
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",

    # Indexes for common query patterns
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
    "CREATE INDEX entity_status_idx IF NOT EXISTS FOR (e:Entity) ON (e.status)",
    "CREATE INDEX entity_type_status_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type, e.status)",

    # Job hierarchy indexes (Axiom 6: Singularity+ / root_token enforcement)
    "CREATE INDEX job_tier_idx IF NOT EXISTS FOR (e:Entity) ON (e.tier)",
    "CREATE INDEX job_scope_idx IF NOT EXISTS FOR (e:Entity) ON (e.scope_id)",

    # Experience Space (Dimension A — :Experience label nodes)
    "CREATE INDEX experience_job_idx IF NOT EXISTS FOR (e:Experience) ON (e.job_id)",

    # Slug-based lookups for Segment and Scenario entities
    "CREATE INDEX segment_slug_idx IF NOT EXISTS FOR (e:Segment) ON (e.slug)",
    "CREATE INDEX scenario_slug_idx IF NOT EXISTS FOR (e:Scenario) ON (e.slug)",

    # SAP Context Graph indexes
    "CREATE INDEX sap_process_module_idx IF NOT EXISTS FOR (e:Sap_process) ON (e.entity_type)",
    "CREATE INDEX sap_object_type_idx IF NOT EXISTS FOR (e:Sap_object) ON (e.entity_type)",
    "CREATE INDEX sap_org_unit_type_idx IF NOT EXISTS FOR (e:Sap_org_unit) ON (e.entity_type)",
    "CREATE INDEX decision_actor_idx IF NOT EXISTS FOR (e:Decision) ON (e.entity_type)",
    "CREATE INDEX policy_type_idx IF NOT EXISTS FOR (e:Policy) ON (e.entity_type)",
    "CREATE INDEX survey_status_idx IF NOT EXISTS FOR (e:Survey) ON (e.entity_type)",
]

# Fulltext index requires separate handling (may fail on Community Edition)
FULLTEXT_STATEMENTS: list[str] = [
    "CREATE FULLTEXT INDEX entity_statement_ft IF NOT EXISTS FOR (e:Entity) ON EACH [e.statement]",
]


async def ensure_schema(conn: Neo4jConnection) -> int:
    """Initialize Neo4j schema. Returns count of statements executed.

    Idempotent — safe to call on every startup.
    """
    count = 0
    for stmt in SCHEMA_STATEMENTS:
        try:
            await conn.run(stmt)
            count += 1
        except Exception as e:
            logger.warning("Schema statement skipped: %s — %s", stmt[:60], e)

    for stmt in FULLTEXT_STATEMENTS:
        try:
            await conn.run(stmt)
            count += 1
        except Exception as e:
            logger.debug("Fulltext index skipped (may require Enterprise): %s", e)

    logger.info("Neo4j schema initialized: %d statements executed", count)
    return count
