"""Audit Trail — complete decision history and compliance logging."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from contextforge.db.postgres import PostgresClient

logger = logging.getLogger(__name__)


class AuditTrail:
    """Query and write to the audit log for compliance."""

    def __init__(self, postgres: PostgresClient) -> None:
        self._pg = postgres

    async def log_action(
        self,
        *,
        user_id: str = "system",
        action_type: str,
        resource_type: str,
        resource_id: str | None = None,
        change_details: dict[str, Any] | None = None,
        result: str = "success",
        reason: str = "",
        correlation_id: str | None = None,
    ) -> str:
        """Write an audit log entry. Returns the log entry ID."""
        import json
        import uuid

        entry_id = str(uuid.uuid4())
        await self._pg.execute(
            """
            INSERT INTO audit_log (id, user_id, action_type, resource_type, resource_id,
                                   change_details, result, reason, correlation_id)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
            """,
            entry_id, user_id, action_type, resource_type, resource_id,
            json.dumps(change_details or {}), result, reason,
            correlation_id,
        )
        return entry_id

    async def query(
        self,
        *,
        user_id: str | None = None,
        action_type: str | None = None,
        resource_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit log with filters."""
        conditions = ["1=1"]
        params: list[Any] = []
        idx = 1

        if user_id:
            conditions.append(f"user_id = ${idx}")
            params.append(user_id)
            idx += 1
        if action_type:
            conditions.append(f"action_type = ${idx}")
            params.append(action_type)
            idx += 1
        if resource_type:
            conditions.append(f"resource_type = ${idx}")
            params.append(resource_type)
            idx += 1
        if since:
            conditions.append(f"timestamp >= ${idx}")
            params.append(since)
            idx += 1

        params.append(limit)

        rows = await self._pg.fetch(
            f"""
            SELECT id, timestamp, user_id, action_type, resource_type,
                   resource_id, result, reason
            FROM audit_log
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp DESC
            LIMIT ${idx}
            """,
            *params,
        )
        return [dict(r) for r in rows]
