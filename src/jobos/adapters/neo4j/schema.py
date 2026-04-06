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
