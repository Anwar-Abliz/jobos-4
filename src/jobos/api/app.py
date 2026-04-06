"""JobOS 4.0 — FastAPI Application Factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobos.api.deps import initialize_connections, close_connections

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from jobos.api.routes import entities, jobs, hiring, imperfections, metrics, health
    app.include_router(health.router, tags=["health"])
    app.include_router(entities.router, prefix="/api", tags=["entities"])
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    app.include_router(hiring.router, prefix="/api", tags=["hiring"])
    app.include_router(imperfections.router, prefix="/api", tags=["imperfections"])
    app.include_router(metrics.router, prefix="/api", tags=["metrics"])

    return app
