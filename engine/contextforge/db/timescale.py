"""TimescaleDB async connection pool (asyncpg).

TimescaleDB is PostgreSQL with extensions, so we reuse the same asyncpg
driver.  This module adds convenience helpers for time-series operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class TimescaleClient:
    """Async TimescaleDB client backed by asyncpg."""

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size
        )
        logger.info("TimescaleDB pool connected (%s)", self._dsn.split("@")[-1])

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("TimescaleDB pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("TimescaleClient not connected — call connect() first")
        return self._pool

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def execute(self, query: str, *args: Any) -> str:
        return await self.pool.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        return await self.pool.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        return await self.pool.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self.pool.fetchval(query, *args)

    # ── Telemetry helpers ─────────────────────────────────────────────────────

    async def insert_telemetry(
        self,
        *,
        time: datetime,
        entity_id: str,
        channel_id: str,
        parameter: str,
        value: float,
        unit: str,
        quality: str = "valid",
    ) -> None:
        await self.execute(
            """
            INSERT INTO entity_telemetry (time, entity_id, channel_id, parameter, value, unit, quality)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (time, entity_id, parameter) DO UPDATE
                SET value = EXCLUDED.value, quality = EXCLUDED.quality
            """,
            time, entity_id, channel_id, parameter, value, unit, quality,
        )

    async def insert_telemetry_batch(
        self, rows: list[tuple[datetime, str, str, str, float, str, str]]
    ) -> None:
        await self.pool.executemany(
            """
            INSERT INTO entity_telemetry (time, entity_id, channel_id, parameter, value, unit, quality)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (time, entity_id, parameter) DO UPDATE
                SET value = EXCLUDED.value, quality = EXCLUDED.quality
            """,
            rows,
        )

    # ── Aggregation queries ──────────────────────────────────────────────────

    async def query_latest(
        self, entity_id: str, parameter: str
    ) -> asyncpg.Record | None:
        """Get the most recent telemetry reading."""
        return await self.fetchrow(
            """
            SELECT time, entity_id, parameter, value, unit, quality
            FROM entity_telemetry
            WHERE entity_id = $1 AND parameter = $2
            ORDER BY time DESC
            LIMIT 1
            """,
            entity_id, parameter,
        )

    async def query_range(
        self,
        entity_id: str,
        parameter: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[asyncpg.Record]:
        """Get raw telemetry in a time range."""
        return await self.fetch(
            """
            SELECT time, value, unit, quality
            FROM entity_telemetry
            WHERE entity_id = $1 AND parameter = $2
              AND time >= $3 AND time < $4
            ORDER BY time
            """,
            entity_id, parameter, start, end,
        )

    async def query_aggregated(
        self,
        entity_id: str,
        parameter: str,
        *,
        start: datetime,
        end: datetime,
        bucket: str = "5 minutes",
    ) -> list[asyncpg.Record]:
        """Get time-bucketed aggregates (uses continuous aggregate if 5min)."""
        if bucket == "5 minutes":
            return await self.fetch(
                """
                SELECT bucket, avg_value, min_value, max_value, sample_count
                FROM entity_telemetry_5min
                WHERE entity_id = $1 AND parameter = $2
                  AND bucket >= $3 AND bucket < $4
                ORDER BY bucket
                """,
                entity_id, parameter, start, end,
            )
        return await self.fetch(
            f"""
            SELECT time_bucket($5::interval, time) AS bucket,
                   AVG(value) AS avg_value,
                   MIN(value) AS min_value,
                   MAX(value) AS max_value,
                   COUNT(*)   AS sample_count
            FROM entity_telemetry
            WHERE entity_id = $1 AND parameter = $2
              AND time >= $3 AND time < $4
            GROUP BY bucket
            ORDER BY bucket
            """,
            entity_id, parameter, start, end, bucket,
        )

    async def trend_analysis(
        self,
        entity_id: str,
        parameter: str,
        *,
        start: datetime,
        end: datetime,
        bucket: str = "1 hour",
    ) -> list[asyncpg.Record]:
        """Compute trend with moving average and rate of change."""
        return await self.fetch(
            f"""
            WITH bucketed AS (
                SELECT time_bucket($5::interval, time) AS bucket,
                       AVG(value) AS avg_value
                FROM entity_telemetry
                WHERE entity_id = $1 AND parameter = $2
                  AND time >= $3 AND time < $4
                GROUP BY bucket
            )
            SELECT bucket,
                   avg_value,
                   AVG(avg_value) OVER (ORDER BY bucket ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_avg_3,
                   avg_value - LAG(avg_value) OVER (ORDER BY bucket) AS delta,
                   CASE
                     WHEN LAG(avg_value) OVER (ORDER BY bucket) > 0
                     THEN (avg_value - LAG(avg_value) OVER (ORDER BY bucket))
                           / LAG(avg_value) OVER (ORDER BY bucket) * 100
                     ELSE NULL
                   END AS pct_change
            FROM bucketed
            ORDER BY bucket
            """,
            entity_id, parameter, start, end, bucket,
        )

    async def get_entity_parameters(self, entity_id: str) -> list[asyncpg.Record]:
        """List all distinct parameters recorded for an entity."""
        return await self.fetch(
            """
            SELECT DISTINCT parameter, unit,
                   MIN(time) AS first_seen, MAX(time) AS last_seen,
                   COUNT(*) AS total_readings
            FROM entity_telemetry
            WHERE entity_id = $1
            GROUP BY parameter, unit
            ORDER BY parameter
            """,
            entity_id,
        )

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            val = await self.fetchval("SELECT 1")
            return val == 1
        except Exception:
            logger.exception("TimescaleDB health check failed")
            return False
