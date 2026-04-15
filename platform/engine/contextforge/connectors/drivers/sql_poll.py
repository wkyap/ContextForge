"""Generic SQL polling connector — periodically run a SELECT and emit rows.

Uses `asyncpg` (already an engine dependency) to talk to any Postgres-compatible
database, including TimescaleDB. Optionally tracks a monotonic `cursor_column`
so each poll only fetches rows newer than the last seen value — useful for
incremental ingestion of audit/event tables.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import asyncpg

from contextforge.connectors.base import ConnectorBase, Record
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


class SQLPollConnector(ConnectorBase):
    source_kind = "sql_poll"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name=name, config=config)
        self._pool: asyncpg.Pool | None = None
        self._cursor_value: Any = config.get("cursor_start")

    async def connect(self) -> None:
        if "dsn" not in self.config:
            raise ValueError("sql_poll connector requires 'dsn' in config")
        if "query" not in self.config:
            raise ValueError("sql_poll connector requires 'query' in config")
        self._pool = await asyncpg.create_pool(
            dsn=self.config["dsn"],
            min_size=1,
            max_size=int(self.config.get("pool_max", 2)),
        )
        logger.info(
            "SQL poll connector %s ready (interval=%ss, cursor_column=%s)",
            self.name,
            self.config.get("interval_s", 60),
            self.config.get("cursor_column"),
        )

    async def stream(self) -> AsyncIterator[Record]:
        if self._pool is None:
            raise RuntimeError("connect() must be called before stream()")
        query: str = self.config["query"]
        interval: float = float(self.config.get("interval_s", 60))
        cursor_column: str | None = self.config.get("cursor_column")

        while True:
            try:
                async with self._pool.acquire() as conn:
                    if cursor_column and self._cursor_value is not None:
                        rows = await conn.fetch(query, self._cursor_value)
                    else:
                        rows = await conn.fetch(query)
                for row in rows:
                    payload = dict(row)
                    if cursor_column and cursor_column in payload:
                        new_val = payload[cursor_column]
                        if self._cursor_value is None or new_val > self._cursor_value:
                            self._cursor_value = new_val
                    yield Record(
                        payload=payload,
                        source=f"sql://{self.name}",
                        metadata={"row_count": len(rows)},
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("sql_poll %s query failed: %s", self.name, exc)
                yield Record(
                    payload={"error": str(exc)},
                    source=f"sql://{self.name}",
                    metadata={"status": "error"},
                )
            await asyncio.sleep(interval)

    async def close(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                logger.exception("Error closing SQL pool for %s", self.name)
            self._pool = None


get_connector_registry().register(SQLPollConnector)
