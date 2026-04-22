"""JobOS 4.0 — Application Configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Neo4jSettings:
    uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user: str = os.getenv("NEO4J_USER", "neo4j")
    password: str = os.getenv("NEO4J_PASSWORD", "changeme")


def _resolve_postgres_uri() -> str:
    """Resolve PostgreSQL URI with asyncpg driver prefix.

    Render provides DATABASE_URL as postgresql://, but SQLAlchemy async
    requires postgresql+asyncpg://. This handles both POSTGRES_URI and
    DATABASE_URL env vars.
    """
    uri = os.getenv("POSTGRES_URI", os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://jobos:jobos@localhost:5432/jobos"
    ))
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+asyncpg://", 1)
    elif uri.startswith("postgresql://") and "+asyncpg" not in uri:
        uri = uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    return uri


@dataclass(frozen=True)
class PostgresSettings:
    uri: str = _resolve_postgres_uri()


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    api_key: str = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    base_url: str = os.getenv("LLM_BASE_URL", "")
    model: str = os.getenv("LLM_MODEL", "gpt-4.1-mini")


@dataclass(frozen=True)
class SAPSettings:
    simulation_enabled: bool = os.getenv("SAP_SIMULATION_ENABLED", "true").lower() == "true"
    default_org_structure: str = os.getenv("SAP_DEFAULT_ORG", "DEFAULT")
    ingestion_batch_size: int = int(os.getenv("SAP_INGESTION_BATCH_SIZE", "100"))


@dataclass(frozen=True)
class GovernanceSettings:
    enforcement_mode: str = os.getenv("GOVERNANCE_ENFORCEMENT", "advisory")
    audit_all_decisions: bool = os.getenv("GOVERNANCE_AUDIT_ALL", "true").lower() == "true"


@dataclass(frozen=True)
class ContextSettings:
    freshness_threshold_hours: float = float(os.getenv("CONTEXT_FRESHNESS_THRESHOLD", "24.0"))
    max_decay_hours: float = float(os.getenv("CONTEXT_MAX_DECAY_HOURS", "168.0"))
    auto_snapshot_enabled: bool = os.getenv("CONTEXT_AUTO_SNAPSHOT", "false").lower() == "true"


@dataclass(frozen=True)
class JobOSSettings:
    debug: bool = os.getenv("JOBOS_DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("JOBOS_LOG_LEVEL", "INFO")
    entropy_residual_severity: float = float(os.getenv("ENTROPY_RESIDUAL_SEVERITY", "0.05"))
    entropy_residual_risk: float = float(os.getenv("ENTROPY_RESIDUAL_RISK", "0.3"))
    neo4j: Neo4jSettings = Neo4jSettings()
    postgres: PostgresSettings = PostgresSettings()
    llm: LLMSettings = LLMSettings()
    sap: SAPSettings = SAPSettings()
    governance: GovernanceSettings = GovernanceSettings()
    context: ContextSettings = ContextSettings()


def get_settings() -> JobOSSettings:
    return JobOSSettings()
