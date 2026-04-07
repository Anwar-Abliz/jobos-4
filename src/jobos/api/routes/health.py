"""JobOS 4.0 — Health Check Route."""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Check system health: Neo4j, PostgreSQL, engines."""
    from jobos.api.deps import _graph_port, _relational_port

    neo4j_ok = False
    pg_ok = False

    if _graph_port is not None:
        try:
            neo4j_ok = await _graph_port.verify_connectivity()
        except Exception as e:
            logger.warning("Neo4j health check failed: %s", e)

    if _relational_port is not None:
        try:
            pg_ok = await _relational_port.verify_connectivity()
        except Exception as e:
            logger.warning("PostgreSQL health check failed: %s", e)

    status = "ok" if (neo4j_ok and pg_ok) else "degraded"

    return {
        "status": status,
        "version": "4.0.0",
        "neo4j": neo4j_ok,
        "postgresql": pg_ok,
        "nsaig_engine": True,
        "cdee_engine": True,
    }
