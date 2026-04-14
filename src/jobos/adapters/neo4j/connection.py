"""JobOS 4.0 — Neo4j Connection Manager."""
from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import SessionExpired, ServiceUnavailable

logger = logging.getLogger(__name__)

# AuraDB drops idle TCP connections after ~30s on some network paths.
# Keep connections alive and retire them well before that window.
_MAX_CONNECTION_LIFETIME = 25        # seconds — retire before AuraDB's idle timeout
_KEEP_ALIVE = True
_MAX_POOL_SIZE = 10
_CONNECTION_ACQUISITION_TIMEOUT = 30  # seconds to wait for a free connection


class Neo4jConnection:
    """Manages the async Neo4j driver lifecycle."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Initialize the driver and verify connectivity."""
        self._driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
            max_connection_lifetime=_MAX_CONNECTION_LIFETIME,
            keep_alive=_KEEP_ALIVE,
            max_connection_pool_size=_MAX_POOL_SIZE,
            connection_acquisition_timeout=_CONNECTION_ACQUISITION_TIMEOUT,
        )
        await self._driver.verify_connectivity()
        logger.info("Neo4j connected: %s", self._uri)

    async def close(self) -> None:
        """Close the driver."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed.")

    @property
    def driver(self) -> AsyncDriver:
        if self._driver is None:
            raise RuntimeError("Neo4j not connected. Call connect() first.")
        return self._driver

    async def run(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as dicts.

        Retries once on SessionExpired / ServiceUnavailable — these are raised
        when the driver picks a stale connection from the pool. The driver
        automatically creates a fresh connection on retry.
        """
        for attempt in range(2):
            try:
                async with self.driver.session() as session:
                    result = await session.run(query, params or {})
                    records = await result.data()
                    return records
            except (SessionExpired, ServiceUnavailable) as exc:
                if attempt == 0:
                    logger.warning("Neo4j connection stale, retrying: %s", exc)
                    continue
                raise

        return []  # unreachable, satisfies type checker

    async def verify_connectivity(self) -> bool:
        """Health check."""
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("Neo4j connectivity check failed: %s", e)
            return False
