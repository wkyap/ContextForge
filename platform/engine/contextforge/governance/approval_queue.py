"""Approval Queue — manage AI-generated proposals for human review."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from contextforge.db.postgres import PostgresClient
from contextforge.db.redis import RedisClient

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """Backend for the human governance approval queue."""

    def __init__(self, postgres: PostgresClient, redis: RedisClient) -> None:
        self._pg = postgres
        self._redis = redis

    async def submit_proposal(
        self,
        *,
        proposal_type: str,
        title: str,
        description: str,
        proposed_by: str,
        content: dict[str, Any],
        autonomy_level: int = 0,
        confidence_score: float = 0.0,
    ) -> str:
        """Submit a new proposal for review. Returns proposal ID."""
        proposal_id = str(uuid.uuid4())
        await self._pg.execute(
            """
            INSERT INTO proposals (id, type, title, description, proposed_by, content,
                                   autonomy_level, confidence_score)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            """,
            proposal_id, proposal_type, title, description, proposed_by,
            __import__("json").dumps(content), autonomy_level, confidence_score,
        )

        # Publish event
        await self._redis.publish("proposals:new", {
            "id": proposal_id,
            "type": proposal_type,
            "title": title,
            "proposed_by": proposed_by,
        })

        logger.info("Proposal submitted: %s (%s)", title, proposal_id)
        return proposal_id

    async def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """List pending proposals."""
        rows = await self._pg.fetch(
            """
            SELECT id, type, title, description, proposed_by, confidence_score, created_at
            FROM proposals
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]

    async def review_proposal(
        self,
        proposal_id: str,
        *,
        status: str,
        approver_id: str,
        reason: str = "",
    ) -> bool:
        """Approve, reject, or modify a proposal."""
        result = await self._pg.execute(
            """
            UPDATE proposals
            SET status = $2, approver_id = $3, approval_reason = $4,
                reviewed_at = $5
            WHERE id = $1 AND status = 'pending'
            """,
            proposal_id, status, approver_id, reason,
            datetime.now(UTC),
        )

        # Log to audit trail
        await self._pg.execute(
            """
            INSERT INTO audit_log (user_id, action_type, resource_type, resource_id, result, reason)
            VALUES ($1, $2, 'proposal', $3, $4, $5)
            """,
            approver_id, f"proposal_{status}", proposal_id, "success", reason,
        )

        return "UPDATE 1" in result
