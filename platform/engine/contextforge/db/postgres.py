"""PostgreSQL async connection pool (asyncpg)."""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class PostgresClient:
    """Thin async wrapper around an asyncpg connection pool."""

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._pool is not None:
            return

        async def _init_connection(conn: asyncpg.Connection) -> None:
            """Register JSON codec so Python dicts/lists map to JSONB columns."""
            await conn.set_type_codec(
                "jsonb", encoder=json.dumps, decoder=json.loads,
                schema="pg_catalog",
            )
            await conn.set_type_codec(
                "json", encoder=json.dumps, decoder=json.loads,
                schema="pg_catalog",
            )

        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size,
            init=_init_connection,
        )
        logger.info("PostgreSQL pool connected (%s)", self._dsn.split("@")[-1])

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresClient not connected — call connect() first")
        return self._pool

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def execute(self, query: str, *args: Any) -> str:
        # Support both execute(q, a, b) and execute(q, [a, b])
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = tuple(args[0])
        result: str = await self.pool.execute(query, *args)
        return result

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = tuple(args[0])
        rows: list[asyncpg.Record] = await self.pool.fetch(query, *args)
        return rows

    async def fetch_one(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Alias for fetchrow — used by CareerForge routes."""
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = tuple(args[0])
        return await self.pool.fetchrow(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = tuple(args[0])
        return await self.pool.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = tuple(args[0])
        return await self.pool.fetchval(query, *args)

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            val = await self.fetchval("SELECT 1")
            return bool(val == 1)
        except Exception:
            logger.exception("PostgreSQL health check failed")
            return False
