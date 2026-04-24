"""JobOS 4.0 — FastAPI Application Factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobos.api.deps import close_connections, initialize_connections
from jobos.api.middleware import CorrelationMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to Neo4j + PostgreSQL, initialize schemas.
    Shutdown: close connections gracefully.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("JobOS 4.0 starting up...")

    await initialize_connections()

    yield

    await close_connections()
    logger.info("JobOS 4.0 shut down.")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="JobOS",
        description=(
            "Neurosymbolic Job-Centric Operating System. "
            "Entity hires Entity in Context to minimize Imperfection."
        ),
        version="4.0.0",
        lifespan=lifespan,
    )

    # Middleware: correlation IDs for request tracing
    app.add_middleware(CorrelationMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from jobos.api.routes import (
        baseline,
        chat,
        context,
        decisions,
        entities,
        experience,
        extraction,
        governance,
        health,
        hierarchy,
        hiring,
        imperfections,
        ingest,
        jobs,
        metrics,
        pipeline,
        recommendation,
        sap,
        scenarios,
        segments,
        surveys,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(hierarchy.router, prefix="/api", tags=["hierarchy"])
    app.include_router(experience.router, prefix="/api", tags=["experience"])
    app.include_router(baseline.router, prefix="/api", tags=["baseline"])
    app.include_router(segments.router, prefix="/api", tags=["segments"])
    app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
    app.include_router(recommendation.router, prefix="/api", tags=["recommendation"])
    app.include_router(extraction.router, prefix="/api", tags=["extraction"])
    app.include_router(entities.router, prefix="/api", tags=["entities"])
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    app.include_router(hiring.router, prefix="/api", tags=["hiring"])
    app.include_router(imperfections.router, prefix="/api", tags=["imperfections"])
    app.include_router(metrics.router, prefix="/api", tags=["metrics"])
    app.include_router(ingest.router, prefix="/api", tags=["ingest"])
    app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
    # Context Graph routes
    app.include_router(context.router, prefix="/api", tags=["context"])
    app.include_router(sap.router, prefix="/api", tags=["sap"])
    app.include_router(decisions.router, prefix="/api", tags=["decisions"])
    app.include_router(governance.router, prefix="/api", tags=["governance"])
    app.include_router(surveys.router, prefix="/api", tags=["surveys"])

    return app
