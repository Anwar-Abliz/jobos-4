"""JobOS 4.0 — Dependency Injection.

Provides FastAPI dependencies for services, ports, and engines.
Wired to real Neo4j and PostgreSQL adapters via config.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from jobos.config import get_settings
from jobos.adapters.neo4j.connection import Neo4jConnection
from jobos.adapters.neo4j.entity_repo import Neo4jEntityRepo
from jobos.adapters.postgres.connection import PostgresConnection
from jobos.adapters.postgres.metric_repo import PostgresRepo
from jobos.engines.nsaig import PolicyOptimizer, SwitchLogic, BeliefEngine
from jobos.engines.cdee import CausalGuardian, DynamicController, SwitchHub
from jobos.ports.graph_port import GraphPort
from jobos.ports.relational_port import RelationalPort
from jobos.services.entity_service import EntityService
from jobos.services.hiring_service import HiringService
from jobos.services.imperfection_service import ImperfectionService
from jobos.services.metric_service import MetricService
from jobos.adapters.openai.llm_adapter import OpenAIAdapter
from jobos.pipeline.chat_turn import ChatTurnPipeline
from jobos.services.hierarchy_service import HierarchyService
from jobos.services.pilot_service import PilotService
from jobos.services.experience_service import ExperienceService
from jobos.services.baseline_service import BaselineService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  Connection Singletons (initialized in app lifespan)
# ═══════════════════════════════════════════════════════════

_neo4j_conn: Neo4jConnection | None = None
_postgres_conn: PostgresConnection | None = None
_graph_port: GraphPort | None = None
_relational_port: RelationalPort | None = None
_llm: OpenAIAdapter | None = None


async def initialize_connections() -> None:
    """Initialize database connections. Called from app lifespan."""
    global _neo4j_conn, _postgres_conn, _graph_port, _relational_port, _llm

    settings = get_settings()

    # Neo4j
    _neo4j_conn = Neo4jConnection(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
    )
    try:
        await _neo4j_conn.connect()
        _graph_port = Neo4jEntityRepo(_neo4j_conn)
        schema_count = await _graph_port.ensure_schema()
        logger.info("Neo4j ready (%d schema statements)", schema_count)
    except Exception as e:
        logger.warning("Neo4j connection failed: %s — running without graph DB", e)
        _neo4j_conn = None
        _graph_port = None

    # PostgreSQL
    _postgres_conn = PostgresConnection(uri=settings.postgres.uri)
    try:
        await _postgres_conn.connect()
        _relational_port = PostgresRepo(_postgres_conn)
        logger.info("PostgreSQL ready")
    except Exception as e:
        logger.warning("PostgreSQL connection failed: %s — running without relational DB", e)
        _postgres_conn = None
        _relational_port = None

    # LLM (optional)
    if settings.llm.enabled and settings.llm.api_key:
        try:
            _llm = OpenAIAdapter(
                api_key=settings.llm.api_key,
                model=settings.llm.model,
                base_url=settings.llm.base_url,
            )
            health = await _llm.check_connectivity()
            if health.get("ok"):
                logger.info("LLM ready: %s", health.get("model"))
            else:
                logger.warning("LLM health check failed: %s", health.get("error"))
                _llm = None
        except Exception as e:
            logger.warning("LLM initialization failed: %s", e)
            _llm = None
    else:
        logger.info("LLM disabled (set LLM_ENABLED=true and OPENAI_API_KEY to enable)")


async def close_connections() -> None:
    """Close database connections. Called from app lifespan."""
    if _neo4j_conn:
        await _neo4j_conn.close()
    if _postgres_conn:
        await _postgres_conn.close()


# ═══════════════════════════════════════════════════════════
#  Port Getters
# ═══════════════════════════════════════════════════════════

def get_graph_port() -> GraphPort:
    if _graph_port is None:
        raise RuntimeError(
            "Graph port not initialized. Is Neo4j running? Check NEO4J_URI in .env"
        )
    return _graph_port


def get_relational_port() -> RelationalPort:
    if _relational_port is None:
        raise RuntimeError(
            "Relational port not initialized. Is PostgreSQL running? Check POSTGRES_URI in .env"
        )
    return _relational_port


# ═══════════════════════════════════════════════════════════
#  Engine Singletons
# ═══════════════════════════════════════════════════════════

@lru_cache
def get_belief_engine() -> BeliefEngine:
    return BeliefEngine()


@lru_cache
def get_policy_optimizer() -> PolicyOptimizer:
    return PolicyOptimizer()


@lru_cache
def get_switch_logic() -> SwitchLogic:
    return SwitchLogic()


@lru_cache
def get_causal_guardian() -> CausalGuardian:
    return CausalGuardian()


@lru_cache
def get_controller() -> DynamicController:
    return DynamicController()


@lru_cache
def get_switch_hub() -> SwitchHub:
    return SwitchHub()


# ═══════════════════════════════════════════════════════════
#  Service Factories
# ═══════════════════════════════════════════════════════════

def get_entity_service() -> EntityService:
    return EntityService(graph=get_graph_port())


def get_hiring_service() -> HiringService:
    return HiringService(
        graph=get_graph_port(),
        db=get_relational_port(),
        policy_optimizer=get_policy_optimizer(),
        switch_logic=get_switch_logic(),
        causal_guardian=get_causal_guardian(),
        controller=get_controller(),
        switch_hub=get_switch_hub(),
    )


def get_imperfection_service() -> ImperfectionService:
    return ImperfectionService(graph=get_graph_port())


def get_metric_service() -> MetricService:
    return MetricService(
        graph=get_graph_port(),
        db=get_relational_port(),
    )


# ═══════════════════════════════════════════════════════════
#  Chat Pipeline
# ═══════════════════════════════════════════════════════════

def get_chat_pipeline() -> ChatTurnPipeline:
    return ChatTurnPipeline(
        graph=get_graph_port(),
        db=get_relational_port(),
        llm=_llm,
    )


# ═══════════════════════════════════════════════════════════
#  Hierarchy Service
# ═══════════════════════════════════════════════════════════

def get_hierarchy_service() -> HierarchyService:
    return HierarchyService(
        graph=get_graph_port(),
        llm=_llm,
    )


def get_pilot_service() -> PilotService:
    return PilotService(graph=get_graph_port())


def get_experience_service() -> ExperienceService:
    return ExperienceService(
        graph=get_graph_port(),
        db=get_relational_port(),
        llm=_llm,
    )


def get_baseline_service() -> BaselineService:
    return BaselineService(
        graph=get_graph_port(),
        db=get_relational_port(),
    )
