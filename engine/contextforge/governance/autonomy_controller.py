"""Autonomy Level Controller — manage per-function autonomy gradation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from contextforge.db.postgres import PostgresClient
from contextforge.db.redis import RedisClient

logger = logging.getLogger(__name__)

# Level definitions
LEVELS = {
    0: "Full Human Control — all actions require approval",
    1: "Human-in-the-Loop — AI proposes, human approves",
    2: "Human-on-the-Loop — AI executes, human notified",
    3: "Autonomous with Spot Checks — AI executes, random audits",
    4: "Full Autonomy — AI executes independently",
}

# Promotion thresholds
PROMOTION_THRESHOLDS = {
    0: {"min_proposals": 5, "min_approval_rate": 0.80},
    1: {"min_proposals": 10, "min_approval_rate": 0.90},
    2: {"min_proposals": 20, "min_approval_rate": 0.95},
    3: {"min_proposals": 50, "min_approval_rate": 0.98},
}


class AutonomyController:
    """Manage autonomy levels for AI functions."""

    def __init__(self, postgres: PostgresClient, redis: RedisClient) -> None:
        self._pg = postgres
        self._redis = redis

    async def get_level(self, function_name: str) -> dict[str, Any]:
        """Get the current autonomy level for a function."""
        row = await self._pg.fetchrow(
            "SELECT * FROM autonomy_levels WHERE function_name = $1",
            function_name,
        )
        if row:
            return dict(row)
        # Create default entry at level 0
        await self._pg.execute(
            "INSERT INTO autonomy_levels (function_name) VALUES ($1) ON CONFLICT DO NOTHING",
            function_name,
        )
        return {"function_name": function_name, "autonomy_level": 0}

    async def record_decision(
        self, function_name: str, *, approved: bool
    ) -> None:
        """Record an approval/rejection for a function."""
        if approved:
            await self._pg.execute(
                """
                UPDATE autonomy_levels
                SET proposal_count = proposal_count + 1,
                    approval_count = approval_count + 1,
                    approval_rate = (approval_count + 1)::float / (proposal_count + 1)
                WHERE function_name = $1
                """,
                function_name,
            )
        else:
            await self._pg.execute(
                """
                UPDATE autonomy_levels
                SET proposal_count = proposal_count + 1,
                    approval_rate = approval_count::float / (proposal_count + 1),
                    last_rejection_at = $2
                WHERE function_name = $1
                """,
                function_name, datetime.now(timezone.utc),
            )

    async def check_promotion(self, function_name: str) -> bool:
        """Check if a function qualifies for autonomy level promotion."""
        level_data = await self.get_level(function_name)
        current = level_data.get("autonomy_level", 0)
        if current >= 4:
            return False

        thresholds = PROMOTION_THRESHOLDS.get(current)
        if not thresholds:
            return False

        return (
            level_data.get("proposal_count", 0) >= thresholds["min_proposals"]
            and level_data.get("approval_rate", 0) >= thresholds["min_approval_rate"]
        )

    async def promote(
        self, function_name: str, *, promoted_by: str
    ) -> dict[str, Any]:
        """Promote a function to the next autonomy level."""
        await self._pg.execute(
            """
            UPDATE autonomy_levels
            SET autonomy_level = autonomy_level + 1,
                promoted_at = $2,
                promoted_by = $3
            WHERE function_name = $1 AND autonomy_level < 4
            """,
            function_name, datetime.now(timezone.utc), promoted_by,
        )
        new_level = await self.get_level(function_name)

        await self._redis.publish("autonomy:level_changed", {
            "function": function_name,
            "new_level": new_level.get("autonomy_level"),
            "promoted_by": promoted_by,
        })

        logger.info("Promoted %s to level %s", function_name, new_level.get("autonomy_level"))
        return new_level
