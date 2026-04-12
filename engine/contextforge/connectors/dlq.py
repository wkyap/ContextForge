"""Connector dead-letter queue.

Records that fail to write to a sink (or that crash a connector mid-stream)
are persisted here. The supervisor calls :meth:`DLQRepository.write` from the
sink-failure path; operators inspect / replay rows via the REST endpoints in
``api/v1/connectors.py``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from contextforge.connectors.base import Record

logger = logging.getLogger(__name__)


@dataclass
class DLQEntry:
    """A single dead-letter record."""

    id: int
    connector_name: str
    sink_name: str | None
    source: str | None
    payload: dict[str, Any]
    metadata: dict[str, Any]
    error: str
    record_ts: float | None
    failed_at: str
    status: str
    replayed_at: str | None


class DLQRepository:
    """Persist failed connector records to the ``connector_dlq`` table."""

    def __init__(self, postgres: Any) -> None:
        self._pg = postgres

    async def write(
        self,
        *,
        connector_name: str,
        record: Record,
        error: str,
        sink_name: str | None = None,
    ) -> None:
        """Write a failed record to the DLQ.

        Failures here are logged and swallowed — the DLQ must never crash
        the supervisor's ingestion loop.
        """
        try:
            await self._pg.execute(
                """INSERT INTO connector_dlq
                   (connector_name, sink_name, source, payload, metadata,
                    error, record_ts)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                [
                    connector_name,
                    sink_name,
                    record.source,
                    json.dumps(record.payload),
                    json.dumps(record.metadata or {}),
                    error,
                    record.timestamp,
                ],
            )
        except Exception:
            logger.exception(
                "DLQ write failed for connector %s — record dropped", connector_name
            )

    async def list_entries(
        self,
        *,
        connector_name: str | None = None,
        status: str | None = "pending",
        limit: int = 100,
        offset: int = 0,
    ) -> list[DLQEntry]:
        """List DLQ rows, newest first."""
        where: list[str] = []
        params: list[Any] = []
        idx = 1
        if connector_name is not None:
            where.append(f"connector_name = ${idx}")
            params.append(connector_name)
            idx += 1
        if status is not None:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = (
            "SELECT id, connector_name, sink_name, source, payload, metadata, "
            "error, record_ts, failed_at::text, status, replayed_at::text "
            f"FROM connector_dlq {clause} "
            f"ORDER BY failed_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        )
        params.extend([limit, offset])
        rows = await self._pg.fetch(sql, *params)
        return [
            DLQEntry(
                id=r["id"],
                connector_name=r["connector_name"],
                sink_name=r["sink_name"],
                source=r["source"],
                payload=_decode_json(r["payload"]),
                metadata=_decode_json(r["metadata"]),
                error=r["error"],
                record_ts=r["record_ts"],
                failed_at=r["failed_at"],
                status=r["status"],
                replayed_at=r["replayed_at"],
            )
            for r in rows
        ]

    async def count(self, *, connector_name: str | None = None) -> int:
        if connector_name is None:
            row = await self._pg.fetch_one(
                "SELECT COUNT(*) AS n FROM connector_dlq WHERE status = 'pending'"
            )
        else:
            row = await self._pg.fetch_one(
                "SELECT COUNT(*) AS n FROM connector_dlq "
                "WHERE status = 'pending' AND connector_name = $1",
                connector_name,
            )
        return int(row["n"]) if row else 0

    async def mark_status(self, entry_id: int, status: str) -> None:
        """Update an entry's status (e.g. ``replayed`` or ``ignored``)."""
        await self._pg.execute(
            """UPDATE connector_dlq
               SET status = $2,
                   replayed_at = CASE WHEN $2 = 'replayed' THEN NOW() ELSE replayed_at END
               WHERE id = $1""",
            [entry_id, status],
        )


def _decode_json(value: Any) -> dict[str, Any]:
    """asyncpg returns JSONB as already-decoded dicts; tolerate strings too."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}
