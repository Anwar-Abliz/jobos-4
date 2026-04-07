"""JobOS 4.0 — PostgreSQL Connection Manager (async SQLAlchemy)."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class PostgresConnection:
    """Manages the async SQLAlchemy engine and session factory."""

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._engine: AsyncEngine | None = None
        self._session_factory: sessionmaker | None = None

    async def connect(self) -> None:
        """Initialize the engine, session factory, and verify connectivity."""
        self._engine = create_async_engine(
            self._uri,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
        self._session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        # Verify the connection actually works
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected: %s", self._uri.split("@")[-1])

    async def close(self) -> None:
        """Dispose the engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            logger.info("PostgreSQL connection closed.")

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("PostgreSQL not connected. Call connect() first.")
        return self._engine

    def session(self) -> AsyncSession:
        """Create a new async session."""
        if self._session_factory is None:
            raise RuntimeError("PostgreSQL not connected. Call connect() first.")
        return self._session_factory()

    async def verify_connectivity(self) -> bool:
        """Health check."""
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("PostgreSQL connectivity check failed: %s", e)
            return False
