"""Neo4j async driver wrapper."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async Neo4j client."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: AsyncDriver | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._driver is not None:
            return
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        await self._driver.verify_connectivity()
        logger.info("Neo4j connected (%s)", self._uri)

    async def disconnect(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")

    @property
    def driver(self) -> AsyncDriver:
        if self._driver is None:
            raise RuntimeError("Neo4jClient not connected — call connect() first")
        return self._driver

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        *,
        database: str = "neo4j",
    ) -> list[dict[str, Any]]:
        """Run a Cypher query and return all records as dicts."""
        async with self.driver.session(database=database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        *,
        database: str = "neo4j",
    ) -> list[dict[str, Any]]:
        """Run a write transaction."""
        async with self.driver.session(database=database) as session:

            async def _tx(tx: Any) -> list[dict[str, Any]]:
                result = await tx.run(query, parameters or {})
                data: list[dict[str, Any]] = await result.data()
                return data

            rows: list[dict[str, Any]] = await session.execute_write(_tx)
            return rows

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            records = await self.execute_cypher("RETURN 1 AS ok")
            return len(records) == 1 and records[0].get("ok") == 1
        except Exception:
            logger.exception("Neo4j health check failed")
            return False
