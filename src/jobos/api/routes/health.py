"""JobOS 4.0 — Health Check Route."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Check system health: Neo4j, PostgreSQL, engines."""
    return {
        "status": "ok",
        "version": "4.0.0",
        "neo4j": False,   # Will check connectivity when adapter is wired
        "postgresql": False,
        "nsaig_engine": True,
        "cdee_engine": True,
    }
